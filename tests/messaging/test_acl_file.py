"""Checks the intent of the ACL file without a broker (issue #13).

Evaluates ``deploy/mosquitto/acl`` with MQTT topic-matching rules. **It is a
simulation**: it shows that the file says what we want, not that Mosquitto
enforces it. That is verified by ``tests/broker`` against the real broker.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from txori_kantua import messaging as m

ACL = Path(__file__).resolve().parents[2] / "deploy" / "mosquitto" / "acl"
STATION = "station-01"
SERVICES = ["inference", "sensors", "monitor", "ingest", "station", "healthcheck"]


def _parse():
    users: dict[str, list[tuple[str, str]]] = {}
    patterns: list[tuple[str, str]] = []
    current = None
    for raw in ACL.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        word, _, rest = line.partition(" ")
        if word == "user":
            current = rest.strip()
            users.setdefault(current, [])
        elif word in ("topic", "pattern"):
            access, _, topic = rest.strip().partition(" ")
            if access not in ("read", "write", "readwrite"):
                access, topic = "readwrite", rest.strip()
            (patterns if word == "pattern" else users[current]).append((access, topic.strip()))
        else:
            raise AssertionError(f"unrecognised ACL line: {raw!r}")
    return users, patterns


def _matches(topic_filter: str, topic: str) -> bool:
    f, t = topic_filter.split("/"), topic.split("/")
    for i, part in enumerate(f):
        if part == "#":
            return True
        if i >= len(t) or (part != "+" and part != t[i]):
            return False
    return len(f) == len(t)


def allowed(user: str, action: str, topic: str) -> bool:
    users, patterns = _parse()
    rules = list(users.get(user, [])) + [(a, p.replace("%u", user)) for a, p in patterns]
    return any(a in (action, "readwrite") and _matches(f, topic) for a, f in rules)


DET = m.topic_for("detection", STATION)
ENV = m.topic_for("environment", STATION)
HEA = m.topic_for("health", STATION)


def test_every_service_is_declared():
    users, _ = _parse()
    assert set(users) == set(SERVICES)


@pytest.mark.parametrize("user, topic", [("inference", DET), ("sensors", ENV), ("monitor", HEA)])
def test_each_producer_writes_its_topic(user, topic):
    assert allowed(user, "write", topic)


@pytest.mark.parametrize("user", SERVICES)
@pytest.mark.parametrize("topic, owner", [(DET, "inference"), (ENV, "sensors"), (HEA, "monitor")])
def test_nobody_else_writes_another_service_topic(user, topic, owner):
    assert allowed(user, "write", topic) == (user == owner)


def test_ingest_reads_everything_and_writes_no_data():
    for topic in (DET, ENV, HEA, m.availability_topic(STATION, "sensors")):
        assert allowed("ingest", "read", topic)
    for topic in (DET, ENV, HEA):
        assert not allowed("ingest", "write", topic)


def test_station_reads_detections_and_availability_but_not_environment():
    assert allowed("station", "read", DET)
    assert allowed("station", "read", m.availability_topic(STATION, "inference"))
    assert not allowed("station", "read", ENV)
    assert not allowed("station", "read", HEA)


@pytest.mark.parametrize("user", SERVICES)
def test_each_service_publishes_only_its_own_availability(user):
    assert allowed(user, "write", m.availability_topic(STATION, user))
    for other in SERVICES:
        if other != user:
            assert not allowed(user, "write", m.availability_topic(STATION, other))


@pytest.mark.parametrize("user", SERVICES)
def test_nobody_writes_outside_the_v1_tree(user):
    for topic in ("txori/v2/station-01/detections", "other/topic", "$SYS/broker/version",
                  "txori/v1/station-01/audio"):
        assert not allowed(user, "write", topic)


def test_an_undeclared_user_cannot_touch_data():
    for topic in (DET, ENV, HEA):
        assert not allowed("intruder", "write", topic)
        assert not allowed("intruder", "read", topic)


def test_broker_limit_matches_the_contract_limit():
    conf = (ACL.parent / "txori-kantua.conf").read_text(encoding="utf-8")
    assert f"message_size_limit {m.MAX_PAYLOAD_BYTES}" in conf
    assert "allow_anonymous false" in conf
    assert "allow_anonymous true" not in conf
    listeners = [l.split() for l in conf.splitlines() if l.startswith("listener ")]
    assert listeners == [["listener", "1883", "127.0.0.1"]], "it must only listen on loopback"
