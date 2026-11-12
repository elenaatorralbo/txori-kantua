"""Consumer compatibility checks; no MQTT broker or physical LCD involved."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from txori_kantua import messaging
from txori_kantua.lcd import paginate_text

EXAMPLES = Path(__file__).resolve().parents[1] / "contracts" / "examples"
VALID = sorted((EXAMPLES / "valid").glob("detection.*.json"))


def validated_pages(event):
    """Exercise the existing public interfaces as a future consumer would."""
    payload = messaging.encode("detection", event)
    topic = messaging.topic_for("detection", event["station_id"])
    kind, decoded = messaging.decode(topic, payload)
    assert kind == "detection"
    return paginate_text(decoded["species"]["scientific_name"])


@pytest.mark.parametrize("path", VALID, ids=lambda path: path.stem)
def test_repository_detection_examples_reach_lcd_unchanged(path):
    event = json.loads(path.read_text())
    before = deepcopy(event)
    pages = validated_pages(event)
    assert pages == (("Turdus merula".ljust(16), " " * 16),)
    assert event == before


def test_optional_taxon_key_does_not_change_display():
    event = json.loads(VALID[0].read_text())
    without_key = validated_pages(event)
    event["species"]["taxon_key"] = "synthetic-key"
    assert validated_pages(event) == without_key


def test_long_schema_valid_name_uses_multiple_pages_without_loss():
    event = json.loads(VALID[0].read_text())
    # Synthetic schema stress case, not an assertion that this taxon exists.
    name = "A" + "a" * 39 + " " + "b" * 40
    event["species"]["scientific_name"] = name
    pages = validated_pages(event)
    assert len(pages) > 1
    assert all(len(row) == 16 for page in pages for row in page)
    assert "".join(row.replace(" ", "") for page in pages for row in page) == name.replace(" ", "")


def test_invalid_common_name_is_rejected_before_display():
    example = json.loads((EXAMPLES / "invalid" / "detection.common-name-as-scientific.json").read_text())
    with pytest.raises(messaging.ContractViolation):
        validated_pages(example["event"])


def test_wrong_station_is_rejected_at_consumer_boundary():
    event = json.loads(VALID[0].read_text())
    payload = messaging.encode("detection", event)
    with pytest.raises(messaging.ContractViolation):
        messaging.decode(messaging.topic_for("detection", "other-station"), payload)


def test_retry_keeps_identity_time_and_display():
    event = json.loads(VALID[0].read_text())
    topic = messaging.topic_for("detection", event["station_id"])
    payload = messaging.encode("detection", event)
    _, first = messaging.decode(topic, payload)
    _, retry = messaging.decode(topic, payload)
    assert first["event_id"] == retry["event_id"] == event["event_id"]
    assert first["observed_at"] == retry["observed_at"] == event["observed_at"]
    assert paginate_text(first["species"]["scientific_name"]) == paginate_text(retry["species"]["scientific_name"])
