"""Verification against real Mosquitto (issue #13).

Skipped unless explicitly requested, on the machine where the broker
configured with ``deploy/mosquitto/setup_broker.sh`` runs::

    sudo TXORI_BROKER_TESTS=1 /opt/txori-kantua/venv/bin/python -m pytest tests/broker -v

It needs to read ``/etc/txori-kantua/mqtt/*.env`` (hence ``sudo``). For the
restart test, also::

    TXORI_BROKER_RESTART_CMD="systemctl restart mosquitto"

It covers the three acceptance criteria. **It has not been run yet**: there is
no broker on the development machine.
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path

import pytest

from txori_kantua import messaging as m
from txori_kantua.messaging.client import MqttConnection, MqttSettings

pytestmark = [
    pytest.mark.broker,
    pytest.mark.skipif(os.environ.get("TXORI_BROKER_TESTS") != "1",
                       reason="requires a configured Mosquitto; set TXORI_BROKER_TESTS=1"),
]

STATION = os.environ.get("TXORI_STATION_ID", "station-01")
HOST = os.environ.get("TXORI_MQTT_HOST", "127.0.0.1")
PORT = int(os.environ.get("TXORI_MQTT_PORT", "1883"))
ENV_DIR = Path(os.environ.get("TXORI_CONFIG_DIR", "/etc/txori-kantua")) / "mqtt"
WAIT = 5.0


def _credentials(service: str) -> tuple[str, str]:
    values = dict(line.split("=", 1) for line in (ENV_DIR / f"{service}.env").read_text().splitlines() if "=" in line)
    return values["TXORI_MQTT_USERNAME"], values["TXORI_MQTT_PASSWORD"]


def _connect(service: str, **overrides) -> MqttConnection:
    username, password = _credentials(service)
    settings = MqttSettings(service=service, station_id=STATION, host=HOST, port=PORT,
                            username=overrides.get("username", username),
                            password=overrides.get("password", password))
    conn = MqttConnection(settings)
    conn.start()
    return conn


class Inbox:
    def __init__(self):
        self.events, self._arrived = [], threading.Event()

    def __call__(self, kind, event, topic):
        self.events.append((kind, event, topic))
        self._arrived.set()

    def wait(self, timeout=WAIT):
        return self._arrived.wait(timeout)


def _environment():
    return m.new_environment(station_id=STATION, readings={"temperature": m.reading(17.4, "degC")})


# Criterion 1 ----------------------------------------------------------------

def test_authorised_publisher_publishes_and_authorised_consumer_receives():
    inbox = Inbox()
    ingest, sensors = _connect("ingest"), _connect("sensors")
    try:
        assert ingest.wait_connected(WAIT) and sensors.wait_connected(WAIT)
        ingest.subscribe("environment", inbox)
        time.sleep(0.5)
        event = _environment()
        assert sensors.publish("environment", event).wait(WAIT), "the broker did not confirm QoS 1"
        assert inbox.wait(), "ingest did not receive the event"
        assert inbox.events[0][1] == event
    finally:
        sensors.close(); ingest.close()


# Criterion 2 ----------------------------------------------------------------

def test_anonymous_client_is_rejected():
    settings = MqttSettings(service="healthcheck", station_id=STATION, host=HOST, port=PORT,
                            username=None, password=None)
    conn = MqttConnection(settings)
    conn.start()
    try:
        assert not conn.wait_connected(3), "the broker accepted an anonymous client"
        assert conn.stats["connect_failures"] >= 1
    finally:
        conn.close()


def test_wrong_password_is_rejected():
    conn = _connect("sensors", password="wrong")
    try:
        assert not conn.wait_connected(3)
    finally:
        conn.close()


def test_write_outside_acl_reaches_no_consumer():
    """``sensors`` is not a producer of detections. With MQTT 3.1.1 the broker
    acknowledges the send but discards the message: the test checks it is not
    delivered."""
    inbox = Inbox()
    ingest, sensors = _connect("ingest"), _connect("sensors")
    try:
        assert ingest.wait_connected(WAIT) and sensors.wait_connected(WAIT)
        ingest.subscribe("detection", inbox)
        time.sleep(0.5)
        detection = m.new_detection(station_id=STATION, scientific_name="Turdus merula", confidence=0.9,
                                    observed_at="2026-11-17T09:00:00Z", window_end="2026-11-17T09:00:03Z",
                                    model_name="acl-test", model_version="0")
        sensors._client.publish(m.topic_for("detection", STATION), m.encode("detection", detection), qos=1)
        assert not inbox.wait(3), "a write outside the ACL was delivered"
    finally:
        sensors.close(); ingest.close()


def test_a_service_cannot_declare_another_one_down():
    inbox = Inbox()
    ingest, sensors = _connect("ingest"), _connect("sensors")
    try:
        assert ingest.wait_connected(WAIT) and sensors.wait_connected(WAIT)
        ingest.subscribe("availability", inbox)
        time.sleep(1)  # the retained states arrive
        inbox.events.clear(); inbox._arrived.clear()
        fake = m.availability(station_id=STATION, service="inference", status="offline")
        sensors._client.publish(m.availability_topic(STATION, "inference"), m.encode("availability", fake), qos=1)
        assert not inbox.wait(3)
    finally:
        sensors.close(); ingest.close()


def test_read_outside_acl_receives_nothing():
    """``station`` cannot read environment."""
    inbox = Inbox()
    station, sensors = _connect("station"), _connect("sensors")
    try:
        assert station.wait_connected(WAIT) and sensors.wait_connected(WAIT)
        station.subscribe("environment", inbox)
        time.sleep(0.5)
        sensors.publish("environment", _environment()).wait(WAIT)
        assert not inbox.wait(3)
    finally:
        sensors.close(); station.close()


# Criterion 3 ----------------------------------------------------------------

def test_last_will_publishes_offline_if_the_service_dies():
    inbox = Inbox()
    ingest, sensors = _connect("ingest"), _connect("sensors")
    try:
        assert ingest.wait_connected(WAIT) and sensors.wait_connected(WAIT)
        ingest.subscribe("availability", inbox)
        time.sleep(1)
        inbox.events.clear(); inbox._arrived.clear()
        sensors._client._sock.close()  # abrupt death: no DISCONNECT
        sensors._client.loop_stop()
        deadline = time.time() + 60  # up to 1.5 x keepalive
        while time.time() < deadline:
            if any(e["service"] == "sensors" and e["status"] == "offline" for _, e, _ in inbox.events):
                return
            time.sleep(0.5)
        pytest.fail("the broker did not publish the Last Will")
    finally:
        ingest.close()


@pytest.mark.skipif(not os.environ.get("TXORI_BROKER_RESTART_CMD"),
                    reason="set TXORI_BROKER_RESTART_CMD to test the restart")
def test_after_restarting_the_broker_clients_reconnect_and_availability_updates():
    inbox = Inbox()
    ingest, sensors = _connect("ingest"), _connect("sensors")
    try:
        assert ingest.wait_connected(WAIT) and sensors.wait_connected(WAIT)
        ingest.subscribe("environment", inbox)
        connects_before = sensors.stats["connects"]
        subprocess.run(os.environ["TXORI_BROKER_RESTART_CMD"].split(), check=True)
        deadline = time.time() + 90
        while time.time() < deadline and not (
            sensors.connected and ingest.connected and sensors.stats["connects"] > connects_before
        ):
            time.sleep(0.5)
        assert sensors.stats["connects"] > connects_before, "the producer did not reconnect"
        assert ingest.connected, "the consumer did not reconnect"
        event = _environment()
        assert sensors.publish("environment", event).wait(WAIT)
        assert inbox.wait(), "after the restart events are not delivered"
        # The retained availability is online again.
        state = Inbox()
        ingest.subscribe("availability", state)
        time.sleep(2)
        latest = {e["service"]: e["status"] for _, e, _ in state.events}
        assert latest.get("sensors") == "online"
    finally:
        sensors.close(); ingest.close()
