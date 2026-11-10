"""MQTT connection tests with a paho double (issue #13).

There is no broker: the tests check what the connection asks paho to do and
how it reacts to paho callbacks. Verification against real Mosquitto lives in
``tests/broker``.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from txori_kantua import messaging as m
from txori_kantua.messaging.client import MqttConnection, MqttSettings

NO_CONN = 4  # paho.MQTT_ERR_NO_CONN
QUEUE_FULL = 15  # paho.MQTT_ERR_QUEUE_SIZE


class FakePaho:
    """Records the calls and lets the tests fire the callbacks by hand."""

    def __init__(self):
        self.published = []
        self.subscriptions = []
        self.will = None
        self.credentials = None
        self.max_queued = None
        self.reconnect_delay = None
        self.connect_args = None
        self.loop_running = False
        self.disconnected = False
        self.next_rc = 0
        self.on_connect = self.on_disconnect = self.on_message = None

    def username_pw_set(self, username, password):
        self.credentials = (username, password)

    def max_queued_messages_set(self, n):
        self.max_queued = n

    def reconnect_delay_set(self, lo, hi):
        self.reconnect_delay = (lo, hi)

    def will_set(self, topic, payload, qos, retain):
        self.will = SimpleNamespace(topic=topic, payload=payload, qos=qos, retain=retain)

    def connect_async(self, host, port, keepalive):
        self.connect_args = (host, port, keepalive)

    def loop_start(self):
        self.loop_running = True

    def loop_stop(self):
        self.loop_running = False

    def disconnect(self):
        self.disconnected = True

    def subscribe(self, topic, qos):
        self.subscriptions.append((topic, qos))

    def publish(self, topic, payload, qos, retain):
        self.published.append(SimpleNamespace(topic=topic, payload=payload, qos=qos, retain=retain))
        return SimpleNamespace(rc=self.next_rc, wait_for_publish=lambda t=None: None,
                               is_published=lambda: self.next_rc == 0)

    # -- test helpers --
    def broker_accepts(self):
        self.on_connect(self, None, {}, 0, None)

    def broker_drops(self):
        self.on_disconnect(self, None, {}, 7, None)

    def deliver(self, topic, payload):
        self.on_message(self, None, SimpleNamespace(topic=topic, payload=payload))


@pytest.fixture
def fake():
    return FakePaho()


@pytest.fixture
def conn(fake):
    settings = MqttSettings(service="ingest", station_id="station-01", username="ingest", password="s3cret")
    return MqttConnection(settings, client_factory=lambda s: fake)


def _environment(**overrides):
    return m.new_environment(station_id=overrides.pop("station_id", "station-01"),
                             readings={"temperature": m.reading(17.4, "degC")}, **overrides)


# -- configuration --------------------------------------------------------------

def test_configures_credentials_bounded_queue_and_backoff(conn, fake):
    assert fake.credentials == ("ingest", "s3cret")
    assert fake.max_queued == 1000
    assert fake.reconnect_delay == (1, 60)


def test_last_will_is_retained_offline_and_complies_with_the_contract(conn, fake):
    assert fake.will.topic == "txori/v1/station-01/availability/ingest"
    assert (fake.will.qos, fake.will.retain) == (1, True)
    kind, event = m.decode(fake.will.topic, fake.will.payload)
    assert kind == "availability" and event["status"] == "offline" and event["service"] == "ingest"


def test_start_does_not_block_or_require_a_broker(conn, fake):
    conn.start()
    assert fake.connect_args == ("127.0.0.1", 1883, 30)
    assert fake.loop_running and not conn.connected


def test_settings_repr_does_not_show_the_password(conn):
    assert "s3cret" not in repr(conn.settings)


def test_settings_from_environment(monkeypatch):
    monkeypatch.setenv("TXORI_STATION_ID", "station-07")
    monkeypatch.setenv("TXORI_MQTT_PASSWORD", "x")
    monkeypatch.delenv("TXORI_MQTT_USERNAME", raising=False)
    settings = MqttSettings.from_env(service="sensors")
    assert (settings.station_id, settings.username, settings.password) == ("station-07", "sensors", "x")
    monkeypatch.delenv("TXORI_STATION_ID")
    with pytest.raises(ValueError):
        MqttSettings.from_env(service="sensors")


# -- availability and reconnection ---------------------------------------------

def test_on_connect_publishes_retained_online(conn, fake):
    conn.start()
    fake.broker_accepts()
    assert conn.connected
    online = fake.published[-1]
    assert online.topic == "txori/v1/station-01/availability/ingest" and online.retain and online.qos == 1
    assert json.loads(online.payload)["status"] == "online"


def test_reconnection_repeats_subscriptions_and_availability(conn, fake):
    conn.subscribe("detection", lambda *a: None)
    conn.subscribe("availability", lambda *a: None)
    conn.start()
    fake.broker_accepts()
    assert set(fake.subscriptions) == {("txori/v1/station-01/detections", 1),
                                       ("txori/v1/station-01/availability/+", 1)}
    fake.broker_drops()
    assert not conn.connected
    fake.broker_accepts()
    assert conn.connected
    assert len(fake.subscriptions) == 4
    assert [json.loads(p.payload)["status"] for p in fake.published] == ["online", "online"]
    assert conn.stats["connects"] == 2 and conn.stats["disconnects"] == 1


def test_refused_connection_is_not_marked_connected(conn, fake):
    conn.start()
    fake.on_connect(fake, None, {}, 5, None)  # 5 = not authorised
    assert not conn.connected and fake.published == []
    assert conn.stats["connect_failures"] == 1


def test_subscribing_after_connecting_applies_immediately(conn, fake):
    conn.start()
    fake.broker_accepts()
    conn.subscribe("environment", lambda *a: None, all_stations=True)
    assert fake.subscriptions == [("txori/v1/+/environment", 1)]


def test_orderly_close_publishes_offline(conn, fake):
    conn.start()
    fake.broker_accepts()
    conn.close()
    assert json.loads(fake.published[-1].payload)["status"] == "offline"
    assert fake.published[-1].retain
    assert fake.disconnected and not fake.loop_running and not conn.connected


# -- publishing -------------------------------------------------------------------

def test_publishes_with_the_contract_policy(conn, fake):
    event = _environment()
    result = conn.publish("environment", event)
    sent = fake.published[-1]
    assert result.accepted and result.reason == "ok"
    assert (sent.topic, sent.qos, sent.retain) == ("txori/v1/station-01/environment", 1, False)
    assert json.loads(sent.payload) == event


def test_retrying_sends_the_same_bytes(conn, fake):
    event = _environment()
    conn.publish("environment", event)
    conn.publish("environment", event)
    assert fake.published[0].payload == fake.published[1].payload


def test_without_connection_the_message_is_queued(conn, fake):
    fake.next_rc = NO_CONN
    result = conn.publish("environment", _environment())
    assert result.accepted and result.reason == "queued"


def test_full_queue_is_reported_not_hidden(conn, fake):
    fake.next_rc = QUEUE_FULL
    result = conn.publish("environment", _environment())
    assert not result.accepted and conn.stats["rejected"] == 1
    assert result.wait(0) is False


def test_does_not_publish_an_invalid_event(conn, fake):
    event = _environment()
    event["audio_b64"] = "AAAA"
    with pytest.raises(m.ContractViolation):
        conn.publish("environment", event)
    assert fake.published == []


def test_does_not_publish_events_of_another_station(conn, fake):
    with pytest.raises(m.TopicError):
        conn.publish("environment", _environment(station_id="station-02"))
    assert fake.published == []


def test_availability_is_not_published_by_hand(conn):
    with pytest.raises(m.TopicError):
        conn.publish("availability", m.availability(station_id="station-01", service="ingest", status="online"))


# -- receiving ----------------------------------------------------------------------

def test_delivers_valid_messages(conn, fake):
    seen = []
    conn.subscribe("environment", lambda kind, event, topic: seen.append((kind, event["event_id"], topic)))
    event = _environment()
    fake.deliver("txori/v1/station-01/environment", m.encode("environment", event))
    assert seen == [("environment", event["event_id"], "txori/v1/station-01/environment")]
    assert conn.stats["received"] == 1 and conn.stats["invalid"] == 0


@pytest.mark.parametrize("topic, payload", [
    ("txori/v1/station-01/environment", b"not json"),
    ("txori/v1/station-01/environment", b'{"schema_version":"2.0"}'),
    ("txori/v1/station-01/environment", b"x" * 20000),
    ("txori/v2/station-01/environment", b"{}"),
    ("other/thing", b"{}"),
])
def test_an_invalid_message_does_not_stop_the_consumer(conn, fake, topic, payload):
    seen, invalid = [], []
    conn._on_invalid = lambda t, p, exc: invalid.append(type(exc).__name__)
    conn.subscribe("environment", lambda *a: seen.append(a))
    fake.deliver(topic, payload)  # must not raise
    good = _environment()
    fake.deliver("txori/v1/station-01/environment", m.encode("environment", good))
    assert len(seen) == 1 and len(invalid) == 1
    assert conn.stats["invalid"] == 1 and conn.stats["received"] == 2


def test_the_log_of_an_invalid_message_does_not_contain_the_payload(conn, fake, caplog):
    secret = b'{"audio_b64":"UklGRiQAAABXQVZF"}'
    with caplog.at_level("WARNING", logger="txori_kantua.messaging"):
        fake.deliver("txori/v1/station-01/environment", secret)
    assert "UklGRiQAAABXQVZF" not in caplog.text
    assert "invalid message" in caplog.text


def test_a_failing_consumer_does_not_bring_down_the_connection(conn, fake):
    calls = []

    def handler(kind, event, topic):
        calls.append(event["event_id"])
        if len(calls) == 1:
            raise RuntimeError("storage down")

    conn.subscribe("environment", handler)
    for _ in range(2):
        fake.deliver("txori/v1/station-01/environment", m.encode("environment", _environment()))
    assert len(calls) == 2 and conn.stats["handler_errors"] == 1


def test_a_failing_on_invalid_neither(conn, fake):
    conn._on_invalid = lambda *a: 1 / 0
    fake.deliver("txori/v1/station-01/environment", b"garbage")
    assert conn.stats["invalid"] == 1


# -- against real paho, without a broker ---------------------------------------------

def test_paho_constants_used_by_the_double():
    paho = pytest.importorskip("paho.mqtt.client")
    assert (paho.MQTT_ERR_NO_CONN, paho.MQTT_ERR_QUEUE_SIZE) == (NO_CONN, QUEUE_FULL)


def test_with_real_paho_and_no_broker_messages_queue_up_to_the_limit():
    """Without a connection, paho accepts up to ``max_queued_messages`` and then
    rejects: memory does not grow without limit even if the broker never returns."""
    pytest.importorskip("paho.mqtt.client")
    settings = MqttSettings(service="sensors", station_id="station-01", max_queued_messages=3)
    conn = MqttConnection(settings)
    results = [conn.publish("environment", _environment()) for _ in range(5)]
    assert [r.accepted for r in results] == [True, True, True, False, False]
    assert [r.reason for r in results[:3]] == ["queued"] * 3
    assert conn.stats["published"] == 3 and conn.stats["rejected"] == 2
