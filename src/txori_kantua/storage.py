"""Single-writer SQLite metadata store. Readers use mode=ro; audio is rejected."""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .aggregates import daily_summaries, day_bounds, local_date
from .messaging.contracts import decode, encode
from .messaging.timestamps import from_epoch_ms, now_timestamp, to_epoch_ms

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
 event_id TEXT PRIMARY KEY, kind TEXT NOT NULL,
 station_id TEXT NOT NULL, observed_at_ms INTEGER NOT NULL,
 received_at_ms INTEGER NOT NULL, payload TEXT NOT NULL,
 species TEXT, confidence REAL
);
CREATE INDEX IF NOT EXISTS events_time ON events(kind, observed_at_ms, event_id);
CREATE INDEX IF NOT EXISTS station_time ON events(station_id, kind, observed_at_ms, event_id);
CREATE TABLE IF NOT EXISTS daily_summaries (
 station_id TEXT NOT NULL, day TEXT NOT NULL, payload TEXT NOT NULL, sealed INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(station_id,day)
);
CREATE TABLE IF NOT EXISTS availability_transitions (
 station_id TEXT NOT NULL, service TEXT NOT NULL, observed_at_ms INTEGER NOT NULL,
 status TEXT NOT NULL, received_at_ms INTEGER NOT NULL,
 PRIMARY KEY(station_id, service, observed_at_ms, status)
);
CREATE VIEW IF NOT EXISTS detections AS
 SELECT event_id,station_id,observed_at_ms,received_at_ms,species AS scientific_name,confidence,payload
 FROM events WHERE kind='detection';
CREATE VIEW IF NOT EXISTS environment_events AS SELECT * FROM events WHERE kind='environment';
CREATE VIEW IF NOT EXISTS health_events AS SELECT * FROM events WHERE kind='health';
CREATE VIEW IF NOT EXISTS environment_readings AS
 SELECT e.event_id,e.station_id,e.observed_at_ms,j.key AS metric,
 json_extract(j.value,'$.value') AS value,json_extract(j.value,'$.unit') AS unit,
 json_extract(j.value,'$.quality') AS quality
 FROM events e,json_each(e.payload,'$.readings') j WHERE e.kind='environment';
"""


def connect_reader(path):
    connection = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True, timeout=2)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA query_only=ON')
    return connection


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.db = sqlite3.connect(self.path, timeout=2)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript(SCHEMA)

    def close(self):
        self.db.close()

    def ingest(self, topic, payload, *, received_at=None):
        kind, event = decode(topic, payload)
        return self.insert(kind, event, received_at=received_at)

    def insert(self, kind, event, *, received_at=None):
        payload = encode(kind, event).decode('utf-8')
        observed = to_epoch_ms(event['observed_at'])
        received = to_epoch_ms(received_at or now_timestamp())
        with self.db:
            if kind == 'availability':
                cur = self.db.execute('INSERT OR IGNORE INTO availability_transitions VALUES (?,?,?,?,?)',
                    (event['station_id'],event['service'],observed,event['status'],received))
            else:
                # A UUID collision with another event is not silently accepted.
                old = self.db.execute('SELECT kind,payload FROM events WHERE event_id=?',
                                      (event['event_id'],)).fetchone()
                if old:
                    if old['kind'] != kind or old['payload'] != payload:
                        raise ValueError('event_id reused for a different observation')
                    return False
                day = local_date(event['observed_at']).isoformat()
                archived = self.db.execute('SELECT sealed FROM daily_summaries WHERE station_id=? AND day=?',
                                           (event['station_id'],day)).fetchone()
                if archived and archived['sealed']:
                    raise ValueError('day is archived; late correction requires offline reconstruction')
                cur = self.db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?)',
                    (event['event_id'],kind,event['station_id'],observed,received,payload,
                     event.get('species',{}).get('scientific_name'),event.get('confidence')))
                # Invalidate projection when a late observation arrives before purge.
                self.db.execute('DELETE FROM daily_summaries WHERE station_id=? AND day=?',
                                (event['station_id'],local_date(event['observed_at']).isoformat()))
            return cur.rowcount == 1

    def backup(self, destination):
        # VACUUM INTO refuses an existing nonempty file; no accidental overwrite.
        self.db.execute('VACUUM INTO ?', (str(destination),))

    def project_day(self, station, day):
        archived = self.db.execute('SELECT payload,sealed FROM daily_summaries WHERE station_id=? AND day=?',
                                   (station,day.isoformat())).fetchone()
        if archived and archived['sealed']:
            return [json.loads(archived['payload'])]
        start,end = day_bounds(day)
        records = self.db.execute('SELECT kind,payload FROM events WHERE station_id=? '
            'AND observed_at_ms>=? AND observed_at_ms<? ORDER BY observed_at_ms,event_id',
            (station,to_epoch_ms(start),to_epoch_ms(end)))
        groups = {'detection':[], 'environment':[], 'health':[]}
        for row in records:
            groups[row['kind']].append(json.loads(row['payload']))
        summaries = daily_summaries(station_id=station,from_date=day,to_date=day+timedelta(days=1),
            detections=groups['detection'], environment=groups['environment'], other_events=groups['health'])
        if summaries:
            with self.db:
                self.db.execute('INSERT OR REPLACE INTO daily_summaries (station_id,day,payload) VALUES (?,?,?)',
                                (station,day.isoformat(),json.dumps(summaries[0],allow_nan=False)))
        return summaries

    def maintain(self, *, now=None):
        """Project at most one expired local day per call, then bounded purge."""
        now = now or datetime.now(timezone.utc)
        for kind,days in [('environment',30),('health',30),('detection',90)]:
            rows = self.db.execute('SELECT station_id,observed_at_ms FROM events WHERE kind=? '
                'AND observed_at_ms<? ORDER BY observed_at_ms LIMIT 1000',
                (kind,to_epoch_ms(now-timedelta(days=days))))
            for row in rows:
                day=local_date(from_epoch_ms(row['observed_at_ms']))
                exists=self.db.execute('SELECT 1 FROM daily_summaries WHERE station_id=? AND day=?',
                                      (row['station_id'],day.isoformat())).fetchone()
                if not exists:
                    self.project_day(row['station_id'],day)
                    return self.purge(now=now)
        return self.purge(now=now)

    def purge(self, *, now=None, batch_size=1000):
        """Bounded purge; never remove raw data without a saved daily projection.

        Projections must be prepared first with project_day. Return deferred count
        so the service can schedule missing projections without unbounded work.
        """
        if not 1 <= batch_size <= 10000:
            raise ValueError('batch_size must be between 1 and 10000')
        now = now or datetime.now(timezone.utc)
        deleted = deferred = 0
        with self.db:
            for kind,days in [('environment',30),('health',30),('detection',90)]:
                cutoff = to_epoch_ms(now-timedelta(days=days))
                rows = self.db.execute('SELECT event_id,station_id,observed_at_ms FROM events '
                    'WHERE kind=? AND observed_at_ms<? ORDER BY observed_at_ms LIMIT ?',
                    (kind,cutoff,batch_size)).fetchall()
                for row in rows:
                    day = local_date(from_epoch_ms(row['observed_at_ms'])).isoformat()
                    exists = self.db.execute('SELECT 1 FROM daily_summaries WHERE station_id=? AND day=?',
                                             (row['station_id'],day)).fetchone()
                    if exists:
                        self.db.execute('UPDATE daily_summaries SET sealed=1 WHERE station_id=? AND day=?',
                                        (row['station_id'],day))
                        self.db.execute('DELETE FROM events WHERE event_id=?',(row['event_id'],))
                        deleted += 1
                    else:
                        deferred += 1
            self.db.execute('DELETE FROM availability_transitions WHERE rowid IN '
                '(SELECT rowid FROM availability_transitions WHERE received_at_ms<? LIMIT ?)',
                (to_epoch_ms(now-timedelta(days=90)),batch_size))
        return {'deleted':deleted,'deferred':deferred}


def api_event(row):
    event = json.loads(row['payload'])
    event.pop('schema_version')
    event['observed_at'] = from_epoch_ms(row['observed_at_ms'])
    if 'window_end' in event:
        event['window_end'] = from_epoch_ms(to_epoch_ms(event['window_end']))
    event['received_at'] = from_epoch_ms(row['received_at_ms'])
    return event
