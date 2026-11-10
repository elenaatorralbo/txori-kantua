"""MQTT v1 contract tests (issue #10).

They need no hardware or broker. They cover the three acceptance criteria:

1. The schemas validate detection, environment and status examples, and reject
   invalid messages.
2. The contract distinguishes ``observed_at`` from ``received_at`` and keeps a
   stable ``event_id`` on retry.
3. (Team review: not automatable; see the PR.)
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from txori_kantua import messaging as m
from txori_kantua.messaging import contracts, timestamps

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "contracts" / "examples"
VALID = sorted((EXAMPLES / "valid").glob("*.json"))
INVALID = sorted((EXAMPLES / "invalid").glob("*.json"))


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _kind(path: Path) -> str:
    return path.name.split(".", 1)[0]


# --------------------------------------------------------------------------
# The schemas themselves
# --------------------------------------------------------------------------

@pytest.mark.parametrize("kind", m.KINDS)
def test_schema_is_valid_draft_2020_12(kind):
    Draft202012Validator.check_schema(m.load_schema(kind))


@pytest.mark.parametrize("kind", m.KINDS)
def test_schema_closes_additional_fields(kind):
    """Without this, a field carrying audio would pass validation silently."""
    assert m.load_schema(kind)["additionalProperties"] is False


def test_there_are_examples_of_every_type():
    assert {_kind(p) for p in VALID} == set(m.KINDS)
    assert {_kind(p) for p in INVALID} == set(m.KINDS)


# --------------------------------------------------------------------------
# Criterion 1: valid accepted, invalid rejected
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_valid_example_is_accepted(path):
    m.validate(_kind(path), _load(path))


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.stem)
def test_invalid_example_is_rejected(path):
    case = _load(path)
    expected = {
        "ContractViolation": m.ContractViolation,
        "UnsupportedSchemaVersion": m.UnsupportedSchemaVersion,
    }[case["expect"]]
    with pytest.raises(expected):
        m.validate(_kind(path), case["event"])


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.stem)
def test_every_invalid_example_documents_its_reason(path):
    """Guards against a negative example failing for an accidental reason."""
    case = _load(path)
    assert case["why"].strip(), "every invalid example documents its reason"


@pytest.mark.parametrize("field", ["audio_b64", "audio", "samples", "audio_path", "transcript", "location"])
def test_no_type_accepts_audio_or_location_fields(field):
    for path in VALID:
        event = _load(path)
        event[field] = "x"
        with pytest.raises(m.ContractViolation):
            m.validate(_kind(path), event)


@pytest.mark.parametrize("date", ["2026-02-30T09:00:00Z", "2026-04-31T09:00:00Z", "2027-02-29T09:00:00Z"])
def test_non_existent_date_is_rejected_as_a_contract_violation(date):
    """The pattern accepts it; the calendar does not. No ValueError must escape."""
    for path in VALID:
        event = _load(path)
        event["observed_at"] = date
        with pytest.raises(m.ContractViolation):
            m.validate(_kind(path), event)


def test_the_error_lists_every_reason():
    event = _load(EXAMPLES / "valid" / "detection.basic.json")
    event["confidence"] = 7
    del event["model"]
    with pytest.raises(m.ContractViolation) as info:
        m.validate("detection", event)
    assert len(info.value.reasons) == 2


# --------------------------------------------------------------------------
# Versioning
# --------------------------------------------------------------------------

def test_unknown_major_version_is_a_distinct_error():
    event = _load(EXAMPLES / "valid" / "detection.basic.json")
    event["schema_version"] = "2.0"
    with pytest.raises(m.UnsupportedSchemaVersion) as info:
        m.validate("detection", event)
    assert not isinstance(info.value, m.ContractViolation)
    assert isinstance(info.value, m.MessagingError)


def test_later_minor_version_is_accepted():
    event = _load(EXAMPLES / "valid" / "detection.basic.json")
    event["schema_version"] = "1.7"
    m.validate("detection", event)


# --------------------------------------------------------------------------
# Criterion 2: observed_at, received_at and stable event_id
# --------------------------------------------------------------------------

def test_received_at_is_not_part_of_the_message():
    """``received_at`` is added by the consumer: a producer cannot send it."""
    for path in VALID:
        event = _load(path)
        assert "received_at" not in event
        event["received_at"] = "2026-11-17T09:00:01Z"
        with pytest.raises(m.ContractViolation):
            m.validate(_kind(path), event)


def test_retry_keeps_event_id_observed_at_and_bytes():
    event = m.new_detection(
        station_id="station-01",
        scientific_name="Turdus merula",
        confidence=0.87,
        observed_at="2026-11-17T09:00:00Z",
        window_end="2026-11-17T09:00:03Z",
        model_name="BirdNET",
        model_version="example-not-validated",
    )
    first = m.encode("detection", event)
    retry = m.encode("detection", event)
    assert first == retry
    assert json.loads(retry)["event_id"] == event["event_id"]
    assert json.loads(retry)["observed_at"] == "2026-11-17T09:00:00Z"


def test_two_different_observations_have_different_event_ids():
    kwargs = dict(station_id="station-01", readings={"temperature": m.reading(17.4, "degC")})
    assert m.new_environment(**kwargs)["event_id"] != m.new_environment(**kwargs)["event_id"]


def test_stable_event_id_is_deterministic_and_valid():
    a = m.stable_event_id("detection", "station-01", "2026-11-17T09:00:00Z", "Turdus merula")
    b = m.stable_event_id("detection", "station-01", "2026-11-17T09:00:00Z", "Turdus merula")
    c = m.stable_event_id("detection", "station-01", "2026-11-17T09:00:03Z", "Turdus merula")
    assert a == b != c
    event = _load(EXAMPLES / "valid" / "detection.basic.json")
    event["event_id"] = a
    m.validate("detection", event)


# --------------------------------------------------------------------------
# Builders
# --------------------------------------------------------------------------

def test_builders_produce_valid_events():
    now = datetime(2026, 11, 17, 9, 0, 0, tzinfo=timezone.utc)
    det = m.new_detection(station_id="station-01", scientific_name="Erithacus rubecula",
                          confidence=0.5, observed_at=now, window_end=now + timedelta(seconds=3),
                          model_name="BirdNET", model_version="x")
    assert det["observed_at"] == "2026-11-17T09:00:00.000Z"
    env = m.new_environment(station_id="station-01", observed_at=now, readings={
        "temperature": m.reading(17.4, "degC"),
        "light": m.reading(None, "raw", "unavailable"),
    })
    hea = m.new_health(station_id="station-01", services={"ingest": "healthy"}, observed_at=now)
    ava = m.availability(station_id="station-01", service="ingest", status="offline", observed_at=now)
    for kind, event in (("detection", det), ("environment", env), ("health", hea), ("availability", ava)):
        m.validate(kind, event)
    assert "event_id" not in ava


def test_builder_rejects_a_filler_zero():
    with pytest.raises(m.ContractViolation):
        m.new_environment(station_id="station-01",
                          readings={"light": m.reading(0, "raw", "unavailable")})


# --------------------------------------------------------------------------
# Topics
# --------------------------------------------------------------------------

def test_topics_and_policies():
    assert m.topic_for("detection", "station-01") == "txori/v1/station-01/detections"
    assert m.topic_for("environment", "station-01") == "txori/v1/station-01/environment"
    assert m.availability_topic("station-01", "ingest") == "txori/v1/station-01/availability/ingest"
    assert m.subscription_for("detection") == "txori/v1/+/detections"
    assert m.subscription_for("availability", "station-01") == "txori/v1/station-01/availability/+"
    assert m.POLICIES["detection"] == m.TopicPolicy(qos=1, retain=False)
    assert m.POLICIES["environment"].retain is False
    assert m.POLICIES["health"].retain is True
    assert m.POLICIES["availability"].retain is True


def test_parse_topic_round_trip():
    assert m.parse_topic("txori/v1/station-01/detections") == m.ParsedTopic("detection", "station-01")
    assert m.parse_topic("txori/v1/station-01/availability/api") == m.ParsedTopic(
        "availability", "station-01", "api")


@pytest.mark.parametrize("topic", [
    "other/v1/station-01/detections",
    "txori/v2/station-01/detections",
    "txori/v1/Station_01/detections",
    "txori/v1/station-01/audio",
    "txori/v1/station-01/detections/extra",
    "txori/v1/station-01/availability",
    "txori/v1/+/detections",
])
def test_parse_topic_rejects(topic):
    with pytest.raises(m.TopicError):
        m.parse_topic(topic)


# --------------------------------------------------------------------------
# decode: what a consumer uses
# --------------------------------------------------------------------------

def test_decode_round_trip():
    event = _load(EXAMPLES / "valid" / "environment.basic.json")
    kind, decoded = m.decode("txori/v1/station-01/environment", m.encode("environment", event))
    assert (kind, decoded) == ("environment", event)


def test_decode_rejects_station_different_from_topic():
    payload = m.encode("detection", _load(EXAMPLES / "valid" / "detection.basic.json"))
    with pytest.raises(m.ContractViolation, match="station_id"):
        m.decode("txori/v1/station-02/detections", payload)


def test_decode_rejects_service_different_from_topic():
    payload = m.encode("availability", _load(EXAMPLES / "valid" / "availability.online.json"))
    with pytest.raises(m.ContractViolation, match="service"):
        m.decode("txori/v1/station-01/availability/api", payload)


def test_decode_rejects_crossed_type():
    payload = m.encode("environment", _load(EXAMPLES / "valid" / "environment.basic.json"))
    with pytest.raises(m.ContractViolation):
        m.decode("txori/v1/station-01/detections", payload)


@pytest.mark.parametrize("payload", [b"", b"not json", b"\xff\xfe", b"[]", b'"string"', b"null"])
def test_decode_rejects_garbage_without_foreign_exceptions(payload):
    with pytest.raises(m.MessagingError):
        m.decode("txori/v1/station-01/detections", payload)


def test_decode_rejects_huge_payload_before_parsing_it():
    with pytest.raises(m.PayloadTooLarge):
        m.decode("txori/v1/station-01/detections", b"{" + b" " * m.MAX_PAYLOAD_BYTES + b"}")


def test_size_limit_is_16_kib():
    assert m.MAX_PAYLOAD_BYTES == 16 * 1024


# --------------------------------------------------------------------------
# Timestamps
# --------------------------------------------------------------------------

def test_timestamp_pattern_matches_the_schema():
    common = json.loads((contracts.contracts_dir() / "common.schema.json").read_text(encoding="utf-8"))
    assert common["$defs"]["timestampUtc"]["pattern"] == timestamps.RFC3339_UTC_PATTERN


@pytest.mark.parametrize("text, expected", [
    ("1970-01-01T00:00:00Z", 0),
    ("2026-11-17T09:00:00Z", 1794906000000),
    ("2026-11-17T09:00:00.123Z", 1794906000123),
    ("2026-11-17T09:00:00.123999999Z", 1794906000123),  # truncates, does not round
    ("2026-11-17T09:00:00.9Z", 1794906000900),
])
def test_to_epoch_ms_truncates(text, expected):
    assert m.to_epoch_ms(text) == expected


def test_epoch_ms_exact_round_trip():
    for ms in (0, 1, 999, 1794906000123, 1794906000999, 4102444799999):
        assert m.to_epoch_ms(m.from_epoch_ms(ms)) == ms


def test_format_timestamp_converts_to_utc_and_rejects_naive():
    madrid = timezone(timedelta(hours=1))
    assert m.format_timestamp(datetime(2026, 11, 17, 10, 0, 0, tzinfo=madrid)) == "2026-11-17T09:00:00.000Z"
    with pytest.raises(m.ContractViolation):
        m.format_timestamp(datetime(2026, 11, 17, 10, 0, 0))


@pytest.mark.parametrize("text", ["2026-11-17T09:00:00", "2026-11-17T10:00:00+01:00",
                                  "2026-11-17 09:00:00Z", "2026-13-17T09:00:00Z", 17, None])
def test_parse_timestamp_rejects(text):
    with pytest.raises(m.ContractViolation):
        m.parse_timestamp(text)


def test_now_timestamp_matches_the_pattern():
    assert re.match(timestamps.RFC3339_UTC_PATTERN, m.now_timestamp())
