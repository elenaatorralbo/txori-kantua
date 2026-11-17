import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from txori_kantua.api import create_app
from txori_kantua.storage import Store
from txori_kantua.messaging.events import new_detection

SPEC=yaml.safe_load((Path(__file__).parents[2]/'contracts/openapi.yaml').read_text())
ROOT={'$schema':'https://json-schema.org/draft/2020-12/schema',**SPEC}
REGISTRY=Registry().with_resource('urn:api',Resource.from_contents(ROOT))


def contract(value,name):
    Draft202012Validator({'$ref':'urn:api#/components/schemas/'+name},registry=REGISTRY).validate(value)


@pytest.fixture
def app(tmp_path):
    path=tmp_path/'db'; store=Store(path)
    for i in range(3):
        store.insert('detection',new_detection(station_id='station-01',scientific_name='Turdus merula',
            confidence=.8,observed_at='2026-11-17T10:00:00Z',window_end='2026-11-17T10:00:03Z',
            model_name='BirdNET',model_version='synthetic-test'))
    store.close()
    return create_app(path).test_client()


QUERY={'from':'2026-11-17T00:00:00Z','to':'2026-11-18T00:00:00Z'}


def test_empty_pages_and_pagination(app):
    response=app.get('/api/v1/environment',query_string=QUERY)
    assert response.status_code==200
    contract(response.json,'EnvironmentPage'); assert response.json['items']==[]
    ids=[]; cursor=None
    for _ in range(3):
        q={**QUERY,'limit':1}
        if cursor: q['cursor']=cursor
        response=app.get('/api/v1/detections',query_string=q)
        assert response.status_code==200
        contract(response.json,'DetectionPage')
        ids.append(response.json['items'][0]['event_id']); cursor=response.json['next_cursor']
    assert cursor is None and len(set(ids))==3


@pytest.mark.parametrize('extra',[
    {'from':'2026-11-19T00:00:00Z'},{'limit':'501'},{'limit':'0'},
    {'limit':'-1'},{'cursor':'garbage'},{'min_confidence':'NaN'},
    {'min_confidence':'inf'},{'to':'2027-01-01T00:00:00Z'},
    {'from':'2026-02-30T00:00:00Z'},{'station_id':"' OR 1=1"},
])
def test_bad_parameters(app,extra):
    response=app.get('/api/v1/detections',query_string={**QUERY,**extra})
    assert response.status_code==400
    contract(response.json,'ErrorResponse')


def test_cursor_cannot_move_between_queries(app):
    first=app.get('/api/v1/detections',query_string={**QUERY,'limit':1}).json
    response=app.get('/api/v1/detections',query_string={**QUERY,'limit':1,
        'station_id':'another','cursor':first['next_cursor']})
    assert response.status_code==400
    assert response.json['error']['code']=='INVALID_CURSOR'


def test_daily_health_and_error_contracts(app):
    response=app.get('/api/v1/summaries/daily',query_string={'from_date':'2026-11-17','to_date':'2026-11-18'})
    assert response.status_code==200
    contract(response.json,'DailySummaryList')
    assert response.json['items'][0]['detections_total']==3
    contract(app.get('/api/v1/health').json,'Health')
    contract(app.get('/unknown').json,'ErrorResponse')
    assert app.post('/api/v1/detections').status_code==405


def test_missing_storage_is_503_not_empty(tmp_path):
    client=create_app(tmp_path/'absent').test_client()
    assert client.get('/api/v1/health').status_code==503
    response=client.get('/api/v1/detections',query_string=QUERY)
    assert response.status_code==503
    contract(response.json,'ErrorResponse')
    assert not (tmp_path/'absent').exists()


def test_internal_failure_is_json_and_does_not_leak(app,monkeypatch):
    from txori_kantua import api
    def fail(*args): raise RuntimeError('secret database path')
    monkeypatch.setattr(api,'connect_reader',fail)
    response=app.get('/api/v1/detections',query_string=QUERY)
    assert response.status_code==500
    contract(response.json,'ErrorResponse')
    assert 'secret' not in response.get_data(as_text=True)


def test_environment_time_range_and_failed_reading_are_preserved(tmp_path):
    from txori_kantua.messaging.events import new_environment,reading
    path=tmp_path/'db'; store=Store(path)
    for stamp in ['2026-11-16T23:59:59Z','2026-11-17T10:00:00Z','2026-11-18T00:00:00Z']:
        store.insert('environment',new_environment(station_id='station-01',observed_at=stamp,
            readings={'temperature':reading(18,'degC'),'light':reading(None,'raw','unavailable')}))
    store.close()
    response=create_app(path).test_client().get('/api/v1/environment',query_string=QUERY)
    contract(response.json,'EnvironmentPage')
    assert len(response.json['items'])==1
    assert response.json['items'][0]['readings']['light']['value'] is None
