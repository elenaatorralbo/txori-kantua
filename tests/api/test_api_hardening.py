"""Request identifiers, caching and unknown parameters in the read API (issue #20)."""
from pathlib import Path

import pytest
from txori_kantua.api import ALLOWED_PARAMS, create_app
from txori_kantua.storage import Store

QUERY = {'from': '2026-11-17T00:00:00Z', 'to': '2026-11-18T00:00:00Z'}


@pytest.fixture
def client(tmp_path):
    path = tmp_path / 'db'
    Store(path).close()
    return create_app(path).test_client()


@pytest.mark.parametrize('path, query', [
    ('/api/v1/detections', {**QUERY, 'limt': '5'}),
    ('/api/v1/environment', {**QUERY, 'species': 'Turdus merula'}),
    ('/api/v1/summaries/daily', {'from_date': '2026-11-17', 'to_date': '2026-11-18', 'limit': '5'}),
    ('/api/v1/health', {'verbose': '1'}),
])
def test_unknown_parameters_are_rejected_not_ignored(client, path, query):
    response = client.get(path, query_string=query)
    assert response.status_code == 400
    assert response.json['error']['code'] == 'INVALID_PARAMETER'
    assert 'unknown parameter' in response.json['error']['message']


def test_known_parameters_still_work(client):
    assert client.get('/api/v1/detections', query_string={**QUERY, 'limit': '5'}).status_code == 200
    assert client.get('/api/v1/health').status_code == 200


def test_error_request_id_matches_the_header(client):
    response = client.get('/api/v1/detections', query_string={**QUERY, 'limit': '0'})
    assert response.status_code == 400
    assert response.json['error']['request_id'] == response.headers['X-Request-Id']


def test_every_response_has_its_own_request_id_and_is_not_cached(client):
    a, b = client.get('/api/v1/health'), client.get('/api/v1/health')
    assert a.headers['X-Request-Id'] and a.headers['X-Request-Id'] != b.headers['X-Request-Id']
    assert a.headers['Cache-Control'] == 'no-store'


def test_internal_error_logs_the_same_request_id(tmp_path, monkeypatch, caplog):
    from txori_kantua import api
    path = tmp_path / 'db'
    Store(path).close()
    client = create_app(path).test_client()
    monkeypatch.setattr(api, 'connect_reader', lambda *a: (_ for _ in ()).throw(RuntimeError('secret')))
    response = client.get('/api/v1/detections', query_string=QUERY)
    assert response.status_code == 500
    assert response.json['error']['request_id'] == response.headers['X-Request-Id']
    assert response.headers['X-Request-Id'] in caplog.text


def test_allowed_parameters_match_the_openapi_contract():
    import yaml
    spec = yaml.safe_load((Path(__file__).parents[2] / 'contracts/openapi.yaml').read_text())

    def resolve(node):
        while '$ref' in node:
            target = spec
            for part in node['$ref'].removeprefix('#/').split('/'):
                target = target[part]
            node = target
        return node

    for route, item in spec['paths'].items():
        declared = {resolve(p)['name'] for p in item['get'].get('parameters', [])}
        assert ALLOWED_PARAMS['/api/v1' + route] == declared, route
