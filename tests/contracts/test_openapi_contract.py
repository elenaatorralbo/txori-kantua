"""OpenAPI document tests (issue #10).

They check that the REST contract is consistent with itself and with the MQTT
contract. That the implemented API complies with it is verified in issue #20.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

ROOT = Path(__file__).resolve().parents[2]
SPEC = yaml.safe_load((ROOT / "contracts" / "openapi.yaml").read_text(encoding="utf-8"))
SPEC_URI = "urn:txori:openapi"
REGISTRY = Registry().with_resource(SPEC_URI, Resource(contents=SPEC, specification=DRAFT202012))
METHODS = {"get", "put", "post", "delete", "patch", "options", "head", "trace"}


def _resolve(node):
    """Follow a local $ref of the document."""
    while isinstance(node, dict) and "$ref" in node:
        target = SPEC
        for part in node["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        node = target
    return node


def _validator(schema) -> Draft202012Validator:
    if "$ref" in schema:
        schema = {"$ref": SPEC_URI + schema["$ref"]}
        return Draft202012Validator(schema, registry=REGISTRY)
    wrapped = json.loads(json.dumps(schema).replace('"#/components/', f'"{SPEC_URI}#/components/'))
    return Draft202012Validator(wrapped, registry=REGISTRY)


def _operations():
    for path, item in SPEC["paths"].items():
        for method, operation in item.items():
            if method in METHODS:
                yield path, method, operation


def _response_examples():
    for path, method, operation in _operations():
        for status, response in operation["responses"].items():
            response = _resolve(response)
            for media in response.get("content", {}).values():
                if "example" in media:
                    yield f"{method} {path} {status}", media["schema"], media["example"]
                for name, example in media.get("examples", {}).items():
                    yield f"{method} {path} {status} {name}", media["schema"], example["value"]


def test_version_and_prefix():
    assert SPEC["openapi"].startswith("3.1")
    assert SPEC["servers"][0]["url"] == "/api/v1"


def test_agreed_endpoints_and_read_only():
    assert set(SPEC["paths"]) == {"/health", "/detections", "/environment", "/summaries/daily"}
    assert {method for _, method, _ in _operations()} == {"get"}


def test_there_is_no_audio_endpoint():
    assert "audio" not in json.dumps(SPEC["paths"]).lower()


@pytest.mark.parametrize("path, method, operation", list(_operations()),
                         ids=lambda v: v if isinstance(v, str) else "")
def test_operation_is_documented(path, method, operation):
    assert operation.get("operationId")
    assert operation.get("summary")
    for parameter in operation.get("parameters", []):
        parameter = _resolve(parameter)
        assert parameter.get("description"), f"{path}: parameter {parameter['name']} without description"
        assert "schema" in parameter
        assert "example" in parameter, f"{path}: parameter {parameter['name']} without example"
    for status, response in operation["responses"].items():
        response = _resolve(response)
        assert response.get("description")
        assert response.get("content"), f"{path} {status} without a described body"


@pytest.mark.parametrize("path", ["/detections", "/environment", "/summaries/daily"])
def test_queries_declare_400_and_503(path):
    assert {"200", "400", "503"} <= set(SPEC["paths"][path]["get"]["responses"])


@pytest.mark.parametrize("path", ["/detections", "/environment"])
def test_lists_paginate_with_a_bounded_limit(path):
    names = {_resolve(p)["name"] for p in SPEC["paths"][path]["get"]["parameters"]}
    assert {"from", "to", "station_id", "limit", "cursor"} <= names
    limit = SPEC["components"]["parameters"]["Limit"]["schema"]
    assert (limit["minimum"], limit["default"], limit["maximum"]) == (1, 100, 500)


@pytest.mark.parametrize("label, schema, example", list(_response_examples()),
                         ids=lambda v: v if isinstance(v, str) else "")
def test_every_example_matches_its_schema(label, schema, example):
    errors = list(_validator(schema).iter_errors(example))
    assert not errors, f"{label}: {[e.message for e in errors]}"


def test_every_response_has_an_example():
    with_example = {label.rsplit(" ", 1)[0] if label.count(" ") > 2 else label for label, _, _ in _response_examples()}
    for path, method, operation in _operations():
        for status in operation["responses"]:
            assert f"{method} {path} {status}" in with_example


def test_patterns_shared_with_mqtt():
    """The API cannot accept an identifier that MQTT would reject, or vice versa."""
    common = json.loads((ROOT / "contracts" / "mqtt" / "common.schema.json").read_text(encoding="utf-8"))["$defs"]
    schemas = SPEC["components"]["schemas"]
    assert schemas["Timestamp"]["pattern"] == common["timestampUtc"]["pattern"]
    assert schemas["StationId"]["pattern"] == common["stationId"]["pattern"]
    assert schemas["EventId"]["pattern"] == common["eventId"]["pattern"]


def test_responses_are_closed_to_additional_fields():
    for name, schema in SPEC["components"]["schemas"].items():
        if schema.get("type") == "object" and "properties" in schema:
            assert schema.get("additionalProperties") is False, name
