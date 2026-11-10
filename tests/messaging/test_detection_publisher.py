"""Detection publishing (issue #18), against the simulated broker.

Acceptance criteria:

1. A valid event reaches two independent consumers.
2. A retry keeps the identifier and does not change ``observed_at``.
3. No message carries samples, audio paths or precise coordinates.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timedelta, timezone

import pytest

from support.fake_broker import FakeBroker
from txori_kantua import messaging as m

TOPIC = "txori/v1/station-01/detections"
START = datetime(2026, 11, 17, 9, 0, 0, tzinfo=timezone.utc)


def result(offset=0, **overrides):
    start = START + timedelta(seconds=3 * offset)
    values = dict(scientific_name="Turdus merula", confidence=0.87, window_start=start,
                  window_end=start + timedelta(seconds=3), model_name="BirdNET", model_version="test")
    values.update(overrides)
    return m.InferenceResult(**values)


@pytest.fixture
def broker():
    return FakeBroker()


@pytest.fixture
def publisher(broker):
    return m.DetectionPublisher(broker.connection("inference"))


class Consumer:
    def __init__(self, broker, service):
        self.events = []
        self.conn = broker.connection(service)
        self.conn.subscribe("detection", lambda kind, event, topic: self.events.append(event))


# -- criterion 1 ---------------------------------------------------------------

def test_an_event_reaches_two_independent_consumers(broker, publisher):
    ingest, station = Consumer(broker, "ingest"), Consumer(broker, "station")
    event = publisher.publish(result())
    assert ingest.events == [event] and station.events == [event]


def test_a_broken_consumer_does_not_prevent_delivery_to_the_other(broker, publisher):
    station = Consumer(broker, "station")
    broken = broker.connection("ingest")
    broken.subscribe("detection", lambda *a: 1 / 0)
    event = publisher.publish(result())
    assert station.events == [event] and broken.stats["handler_errors"] == 1


def test_the_published_event_complies_with_contract_v1(broker, publisher):
    publisher.publish(result(taxon_key="k-1"))
    kind, event = m.decode(TOPIC, broker.published(TOPIC)[0])
    assert kind == "detection"
    assert event["schema_version"] == "1.0"
    assert event["species"] == {"scientific_name": "Turdus merula", "taxon_key": "k-1"}
    assert event["confidence"] == 0.87
    assert (event["observed_at"], event["window_end"]) == ("2026-11-17T09:00:00.000Z", "2026-11-17T09:00:03.000Z")
    assert event["model"] == {"name": "BirdNET", "version": "test"}


def test_detections_are_not_retained(broker, publisher):
    publisher.publish(result())
    assert [retain for topic, _, retain in broker.log if topic == TOPIC] == [False]
    late = Consumer(broker, "station")
    assert late.events == [], "a new subscriber must not receive old detections"


# -- criterion 2 ---------------------------------------------------------------

def test_retry_keeps_identifier_observed_at_and_bytes(broker, publisher):
    first = publisher.publish(result())
    again = publisher.publish(result())
    assert first == again
    sent = broker.published(TOPIC)
    assert len(sent) == 2 and sent[0] == sent[1]


def test_same_detection_after_restarting_inference_has_the_same_id(broker):
    before = m.DetectionPublisher(broker.connection("inference")).build_event(result())
    after = m.DetectionPublisher(broker.connection("inference")).build_event(result())
    assert before["event_id"] == after["event_id"]


def test_same_instant_written_two_ways_gives_the_same_id(publisher):
    a = publisher.build_event(result())
    b = publisher.build_event(result(window_start="2026-11-17T09:00:00Z", window_end="2026-11-17T09:00:03.000000Z"))
    assert a["event_id"] == b["event_id"] and a["observed_at"] == b["observed_at"]


def test_different_detections_have_different_identifiers(publisher):
    ids = {
        publisher.build_event(result())["event_id"],
        publisher.build_event(result(offset=1))["event_id"],
        publisher.build_event(result(scientific_name="Erithacus rubecula"))["event_id"],
    }
    assert len(ids) == 3


def test_confidence_is_not_part_of_the_identity(publisher):
    """Reanalysing the same window with another score is the same observation."""
    assert (publisher.build_event(result(confidence=0.5))["event_id"]
            == publisher.build_event(result(confidence=0.9))["event_id"])


def test_broker_down_delivers_on_return_without_changing_the_event(broker, publisher):
    ingest = Consumer(broker, "ingest")
    broker.go_down()
    events = [publisher.publish(result(offset=i)) for i in range(3)]
    assert ingest.events == []
    broker.come_up()
    assert ingest.events == events
    assert [e["observed_at"] for e in ingest.events] == [e["observed_at"] for e in events]


def test_full_queue_stays_pending_and_flush_delivers_without_duplicates(broker):
    ingest = Consumer(broker, "ingest")
    publisher = m.DetectionPublisher(broker.connection("inference", max_queued_messages=2))
    broker.go_down()
    events = [publisher.publish(result(offset=i)) for i in range(5)]
    assert publisher.pending == 3 and publisher.stats["deferred"] == 3
    broker.come_up()
    assert publisher.flush() == 0
    assert sorted(e["event_id"] for e in ingest.events) == sorted(e["event_id"] for e in events)
    assert len(ingest.events) == 5
    assert publisher.stats["dropped"] == 0


def test_bounded_pending_drops_the_oldest_and_counts_it(broker):
    publisher = m.DetectionPublisher(broker.connection("inference", max_queued_messages=1), max_pending=2)
    broker.go_down()
    for i in range(10):
        publisher.publish(result(offset=i))
    assert publisher.pending == 2 and publisher.stats["dropped"] == 7


def test_invalid_max_pending(broker):
    with pytest.raises(ValueError):
        m.DetectionPublisher(broker.connection("inference"), max_pending=0)


# -- criterion 3 ---------------------------------------------------------------

def test_inference_result_has_no_fields_for_audio_or_location():
    fields = {f.name for f in dataclasses.fields(m.InferenceResult)}
    assert fields == {"scientific_name", "confidence", "window_start", "window_end",
                      "model_name", "model_version", "taxon_key"}


def test_no_published_message_carries_audio_paths_or_coordinates(broker, publisher):
    for i in range(5):
        publisher.publish(result(offset=i, taxon_key="k"))
    allowed = {"schema_version", "event_id", "station_id", "observed_at", "window_end",
               "species", "confidence", "model"}
    for topic, payload, _ in broker.log:
        if topic != TOPIC:
            continue
        event = json.loads(payload)
        assert set(event) == allowed
        assert set(event["species"]) <= {"scientific_name", "taxon_key"}
        assert set(event["model"]) == {"name", "version"}
        assert len(payload) < 1024
        text = payload.decode().lower()
        for forbidden in ("audio", "wav", "base64", "samples", "/tmp", "path", "latitude", "longitude"):
            assert forbidden not in text


@pytest.mark.parametrize("overrides", [
    {"confidence": 1.5},
    {"confidence": "high"},
    {"scientific_name": "common blackbird"},
    {"scientific_name": "/home/pi/recording.wav"},
    {"model_version": ""},
    {"window_end": START},  # empty window
])
def test_an_invalid_result_is_not_published(broker, publisher, overrides):
    with pytest.raises(m.MessagingError):
        publisher.publish(result(**overrides))
    assert broker.published(TOPIC) == []
