"""Read-only Flask API matching contracts/openapi.yaml."""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import sqlite3
import uuid
from contextlib import closing
from datetime import date, timedelta

from flask import Flask, g, jsonify, request
from .aggregates import daily_summaries, day_bounds
from .messaging.errors import MessagingError
from .messaging.timestamps import now_timestamp, to_epoch_ms
from .storage import api_event, connect_reader


class BadQuery(ValueError):
    def __init__(self, code, message):
        self.code, self.message = code, message


def fail(message, code='INVALID_PARAMETER'):
    raise BadQuery(code,message)


#: Query parameters accepted per route. Anything else is a 400, so a typo such
#: as ``limt=5`` is not silently ignored.
ALLOWED_PARAMS = {
    '/api/v1/health': set(),
    '/api/v1/detections': {'from','to','station_id','limit','cursor','species','min_confidence'},
    '/api/v1/environment': {'from','to','station_id','limit','cursor'},
    '/api/v1/summaries/daily': {'from_date','to_date','station_id'},
}


def create_app(database):
    app = Flask(__name__)

    @app.before_request
    def assign_request_id():
        # One identifier per request: the error body, the header and the log agree.
        g.request_id = str(uuid.uuid4())
        allowed = ALLOWED_PARAMS.get(request.path)
        if allowed is not None:
            unknown = sorted(set(request.args) - allowed)
            if unknown:
                fail('unknown parameter: '+', '.join(unknown))

    @app.after_request
    def finish(response):
        response.headers['X-Request-Id'] = g.get('request_id','')
        # Data changes continuously: no cache may serve it.
        response.headers['Cache-Control'] = 'no-store'
        return response

    def error(code,message,status):
        return jsonify(error={'code':code,'message':message,'request_id':g.get('request_id') or str(uuid.uuid4())}),status

    @app.errorhandler(BadQuery)
    def bad_query(exc):
        return error(exc.code,exc.message,400)

    @app.errorhandler(sqlite3.Error)
    def unavailable(exc):
        return error('STORAGE_UNAVAILABLE','storage is not available',503)

    @app.errorhandler(404)
    def not_found(exc):
        return error('NOT_FOUND','endpoint not found',404)

    @app.errorhandler(405)
    def method_not_allowed(exc):
        return error('METHOD_NOT_ALLOWED','method not allowed',405)

    @app.errorhandler(Exception)
    def internal_error(exc):
        # Exception text may include SQL, paths or rejected input.
        request_id=g.get('request_id') or str(uuid.uuid4())
        app.logger.error('request failed request_id=%s class=%s',request_id,type(exc).__name__)
        return jsonify(error={'code':'INTERNAL_ERROR','message':'request could not be completed',
                              'request_id':request_id}),500

    def station_filter():
        station = request.args.get('station_id')
        if station is not None and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,31}',station) is None:
            fail('invalid station_id')
        if any(len(request.args.getlist(k)) != 1 for k in request.args):
            fail('duplicate parameters are not allowed')
        return station

    @app.get('/api/v1/health')
    def health():
        try:
            with closing(connect_reader(database)) as db:
                db.execute('SELECT event_id FROM events LIMIT 1').fetchall()
            state,code = 'ok',200
        except sqlite3.Error:
            state,code = 'unavailable',503
        return jsonify(status=state,storage=state,api_version='1.0.0',time=now_timestamp()),code

    def page(kind):
        station = station_filter()
        try:
            start,end = (to_epoch_ms(request.args[k]) for k in ('from','to'))
        except (KeyError,MessagingError,TypeError):
            fail('from and to must be UTC timestamps')
        if start >= end:
            fail('from must precede to','INVALID_RANGE')
        if end-start > 31*86400000:
            fail('range exceeds 31 days','RANGE_TOO_LARGE')
        raw_limit = request.args.get('limit','100')
        if not re.fullmatch(r'[0-9]{1,3}',raw_limit) or not 1 <= int(raw_limit) <= 500:
            fail('limit must be between 1 and 500')
        limit = int(raw_limit)
        clauses = ['kind=?','observed_at_ms>=?','observed_at_ms<?']
        params = [kind,start,end]
        if station:
            clauses.append('station_id=?'); params.append(station)
        if kind == 'detection':
            species = request.args.get('species')
            if species is not None:
                if not re.fullmatch(r'[A-Z][a-z]+(?: [a-z-]+){1,2}',species):
                    fail('invalid species')
                clauses.append('species=?'); params.append(species)
            if 'min_confidence' in request.args:
                try:
                    confidence = float(request.args['min_confidence'])
                except ValueError:
                    fail('min_confidence must be between 0 and 1')
                if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                    fail('min_confidence must be between 0 and 1')
                clauses.append('confidence>=?'); params.append(confidence)
        signature = hashlib.sha256(json.dumps([params,limit],sort_keys=True).encode()).hexdigest()
        cursor = request.args.get('cursor')
        if cursor is not None:
            try:
                if not 1 <= len(cursor) <= 512:
                    raise ValueError()
                token = json.loads(base64.b64decode(cursor+'='*(-len(cursor)%4),altchars=b'-_',validate=True))
                if (not isinstance(token,list) or len(token)!=3 or token[0]!=signature
                        or type(token[1]) is not int or not isinstance(token[2],str)
                        or str(uuid.UUID(token[2])) != token[2]):
                    raise ValueError()
                clauses.append('(observed_at_ms,event_id)>(?,?)'); params.extend(token[1:])
            except (ValueError,TypeError,UnicodeDecodeError):
                fail('cursor is malformed or belongs to a different query','INVALID_CURSOR')
        with closing(connect_reader(database)) as db:
            rows = db.execute('SELECT * FROM events WHERE '+' AND '.join(clauses)+
                ' ORDER BY observed_at_ms,event_id LIMIT ?',params+[limit+1]).fetchall()
        next_cursor = None
        if len(rows)>limit:
            last = rows[limit-1]
            next_cursor = base64.urlsafe_b64encode(json.dumps(
                [signature,last['observed_at_ms'],last['event_id']]).encode()).decode().rstrip('=')
        return jsonify(items=[api_event(row) for row in rows[:limit]],next_cursor=next_cursor)

    @app.get('/api/v1/detections')
    def detections():
        return page('detection')

    @app.get('/api/v1/environment')
    def environment():
        return page('environment')

    @app.get('/api/v1/summaries/daily')
    def summaries():
        station = station_filter()
        try:
            raw = [request.args[k] for k in ('from_date','to_date')]
            if any(not re.fullmatch(r'\d{4}-\d{2}-\d{2}',s) for s in raw):
                raise ValueError()
            start,end = map(date.fromisoformat,raw)
            day_bounds(end)  # reject the unrepresentable day after 9999-12-31
        except (KeyError,ValueError,OverflowError):
            fail('from_date and to_date must be ISO dates')
        if start>=end:
            fail('from_date must precede to_date','INVALID_RANGE')
        if (end-start).days>92:
            fail('range exceeds 92 days','RANGE_TOO_LARGE')
        result=[]
        with closing(connect_reader(database)) as db:
            stations = [station] if station else [r[0] for r in db.execute(
                'SELECT station_id FROM events UNION SELECT station_id FROM daily_summaries')]
            for sid in stations:
                cached={r['day']:json.loads(r['payload']) for r in db.execute(
                    'SELECT day,payload FROM daily_summaries WHERE station_id=? AND day>=? AND day<?',
                    (sid,start.isoformat(),end.isoformat()))}
                # Stream per day to bound working memory independently of requested range.
                day=start
                while day<end:
                    if day.isoformat() in cached:
                        result.append(cached[day.isoformat()])
                    else:
                        a,b=day_bounds(day)
                        groups={'detection':[],'environment':[],'health':[]}
                        for row in db.execute('SELECT kind,payload FROM events WHERE station_id=? '
                            'AND observed_at_ms>=? AND observed_at_ms<?',(sid,to_epoch_ms(a),to_epoch_ms(b))):
                            groups[row['kind']].append(json.loads(row['payload']))
                        result.extend(daily_summaries(station_id=sid,from_date=day,to_date=day+timedelta(days=1),
                            detections=groups['detection'],environment=groups['environment'],other_events=groups['health']))
                    day+=timedelta(days=1)
        return jsonify(items=sorted(result,key=lambda x:(x['date'],x['station_id'])))

    return app


def main():
    """Production server (waitress), loopback only by default. Entry point ``txori-api``."""
    import logging
    from waitress import serve
    logging.basicConfig(level=os.environ.get('TXORI_LOG_LEVEL','INFO'))
    database=os.environ.get('TXORI_DATABASE','/var/lib/txori-kantua/events.sqlite')
    host=os.environ.get('TXORI_API_HOST','127.0.0.1')
    port=int(os.environ.get('TXORI_API_PORT','8080'))
    serve(create_app(database),host=host,port=port,threads=4,ident=None)


if __name__=='__main__': main()
