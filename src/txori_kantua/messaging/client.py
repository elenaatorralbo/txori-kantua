"""MQTT connection shared by every station service.

Wraps ``paho-mqtt`` so that each service gets, without reimplementing it:

* **Availability**: on connecting it publishes ``online`` (retained) and
  registers an ``offline`` Last Will, so the broker announces it if the
  process dies.
* Automatic **reconnection** with bounded exponential backoff.
* **Validation in both directions**: nothing that breaks the contract is
  published, and an invalid received message is counted and logged but
  **never** stops the consumer.
* **Bounded outgoing queue**: while disconnected, paho keeps pending QoS 1
  messages up to ``max_queued_messages``; beyond that ``publish`` reports the
  rejection instead of growing without limit.

A service's MQTT user name is its service name: that is what the broker ACLs
use to limit what each one can publish (``deploy/mosquitto/acl``).

Example::

    settings = MqttSettings.from_env(service="sensors", station_id="station-01")
    with MqttConnection(settings) as mqtt:
        mqtt.publish("environment", event)
"""

from __future__ import annotations

import logging
import os
import threading
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable

from . import contracts, events
from .errors import MessagingError, TopicError
from .topics import POLICIES, availability_topic, subscription_for, topic_for

__all__ = ["MqttSettings", "MqttConnection", "Handler", "PublishResult"]

log = logging.getLogger("txori_kantua.messaging")

#: ``handler(kind, event, topic)`` for each **valid** message received.
Handler = Callable[[str, dict[str, Any], str], None]


@dataclass(frozen=True)
class MqttSettings:
    """Connection parameters of a service."""

    service: str
    station_id: str
    host: str = "127.0.0.1"
    port: int = 1883
    username: str | None = None
    password: str | None = None
    keepalive: int = 30
    #: Pending QoS 1 messages kept while disconnected. Metadata only: at a few
    #: hundred bytes per event, 1000 messages are less than 1 MB.
    max_queued_messages: int = 1000
    reconnect_min_seconds: int = 1
    reconnect_max_seconds: int = 60

    @classmethod
    def from_env(cls, *, service: str, station_id: str | None = None) -> "MqttSettings":
        """Read ``TXORI_MQTT_*`` and ``TXORI_STATION_ID`` from the environment.

        Credentials arrive through the environment (systemd ``EnvironmentFile``,
        outside Git). The user name defaults to the service name.
        """
        env = os.environ
        station = station_id or env.get("TXORI_STATION_ID")
        if not station:
            raise ValueError("missing station_id: set TXORI_STATION_ID")
        return cls(
            service=service,
            station_id=station,
            host=env.get("TXORI_MQTT_HOST", "127.0.0.1"),
            port=int(env.get("TXORI_MQTT_PORT", "1883")),
            username=env.get("TXORI_MQTT_USERNAME", service),
            password=env.get("TXORI_MQTT_PASSWORD"),
        )

    def __repr__(self) -> str:  # never show the password in a log
        return (
            f"MqttSettings(service={self.service!r}, station_id={self.station_id!r}, "
            f"host={self.host!r}, port={self.port}, username={self.username!r}, password=***)"
        )


@dataclass(frozen=True)
class PublishResult:
    """Result of handing a message to the outgoing queue.

    ``accepted`` only means that paho has accepted it for sending (now or on
    reconnection), not that the broker has confirmed it. ``wait()`` blocks
    until the broker confirmation (PUBACK).
    """

    accepted: bool
    reason: str
    _info: Any = None

    def wait(self, timeout: float | None = None) -> bool:
        if not self.accepted or self._info is None:
            return False
        try:
            self._info.wait_for_publish(timeout)
            return bool(self._info.is_published())
        except (RuntimeError, ValueError):
            return False


def _default_client_factory(settings: MqttSettings) -> Any:
    import paho.mqtt.client as paho

    # Persistent session (clean_session=False) with a stable identifier: the
    # broker keeps QoS 1 subscriptions and queues what is published while the
    # consumer is down. This is what lets ingest not lose events during its
    # own restart.
    return paho.Client(
        paho.CallbackAPIVersion.VERSION2,
        client_id=f"txori-{settings.station_id}-{settings.service}",
        clean_session=False,
        protocol=paho.MQTTv311,
    )


class MqttConnection:
    """A service's connection to the broker, with availability and validation."""

    def __init__(
        self,
        settings: MqttSettings,
        *,
        client_factory: Callable[[MqttSettings], Any] = _default_client_factory,
        on_invalid: Callable[[str, bytes, Exception], None] | None = None,
    ) -> None:
        self.settings = settings
        self._client = client_factory(settings)
        self._handlers: dict[str, Handler] = {}
        self._filters: dict[str, str] = {}
        self._on_invalid = on_invalid
        self._connected = threading.Event()
        self._lock = threading.Lock()
        #: Counters for metrics and tests: ``received``, ``invalid``,
        #: ``handler_errors``, ``published``, ``rejected``, ``connects``...
        self.stats: Counter[str] = Counter()

        self._availability_topic = availability_topic(settings.station_id, settings.service)
        client = self._client
        if settings.username:
            client.username_pw_set(settings.username, settings.password)
        client.max_queued_messages_set(settings.max_queued_messages)
        client.reconnect_delay_set(settings.reconnect_min_seconds, settings.reconnect_max_seconds)
        # The Last Will is built NOW: its observed_at is the connection time,
        # not the failure time (see availability.schema.json).
        client.will_set(
            self._availability_topic,
            self._availability_payload("offline"),
            qos=POLICIES["availability"].qos,
            retain=POLICIES["availability"].retain,
        )
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        """Connect in the background. Does not block or fail if the broker is
        not there: paho retries with exponential backoff until it succeeds."""
        self._client.connect_async(self.settings.host, self.settings.port, self.settings.keepalive)
        self._client.loop_start()

    def wait_connected(self, timeout: float | None = None) -> bool:
        return self._connected.wait(timeout)

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    def close(self) -> None:
        """Orderly shutdown: publish ``offline`` and disconnect."""
        try:
            if self.connected:
                info = self._client.publish(
                    self._availability_topic,
                    self._availability_payload("offline"),
                    qos=POLICIES["availability"].qos,
                    retain=POLICIES["availability"].retain,
                )
                try:
                    info.wait_for_publish(2)
                except (RuntimeError, ValueError):
                    pass
            self._client.disconnect()
        finally:
            self._client.loop_stop()
            self._connected.clear()

    def __enter__(self) -> "MqttConnection":
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- publishing -----------------------------------------------------------

    def publish(self, kind: str, event: dict[str, Any]) -> PublishResult:
        """Validate and publish an event with the QoS and retain of its contract.

        Can be called while disconnected: the message stays in the outgoing
        queue. Retrying means calling again with **the same** ``event``.

        :raises MessagingError: if the event breaks the contract. It is a
            producer defect and must not be silenced.
        """
        if kind == "availability":
            raise TopicError("availability is managed by the connection itself")
        payload = contracts.encode(kind, event)
        if event["station_id"] != self.settings.station_id:
            raise TopicError(
                f"the event belongs to {event['station_id']!r} and this connection to "
                f"{self.settings.station_id!r}"
            )
        policy = POLICIES[kind]
        info = self._client.publish(topic_for(kind, self.settings.station_id), payload,
                                    qos=policy.qos, retain=policy.retain)
        rc = getattr(info, "rc", 0)
        if rc == 0 or self._is_queued(rc):
            self.stats["published"] += 1
            return PublishResult(True, "ok" if rc == 0 else "queued", info)
        self.stats["rejected"] += 1
        log.warning("publish rejected kind=%s event_id=%s rc=%s", kind, event.get("event_id"), rc)
        return PublishResult(False, f"rc={rc}", info)

    @staticmethod
    def _is_queued(rc: int) -> bool:
        try:
            import paho.mqtt.client as paho
        except ImportError:  # pragma: no cover
            return False
        return rc == paho.MQTT_ERR_NO_CONN

    # -- subscribing ----------------------------------------------------------

    def subscribe(self, kind: str, handler: Handler, *, all_stations: bool = False) -> None:
        """Receive the valid events of a type.

        Can be called before or after connecting; the subscription is repeated
        on every reconnection.
        """
        topic_filter = subscription_for(kind, "+" if all_stations else self.settings.station_id)
        with self._lock:
            self._handlers[kind] = handler
            self._filters[kind] = topic_filter
        if self.connected:
            self._client.subscribe(topic_filter, qos=POLICIES[kind].qos)

    # -- paho callbacks ---------------------------------------------------------

    def _availability_payload(self, status: str) -> bytes:
        return contracts.encode(
            "availability",
            events.availability(station_id=self.settings.station_id,
                                service=self.settings.service, status=status),
        )

    def _on_connect(self, client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any = None) -> None:
        if getattr(reason_code, "is_failure", False) or (isinstance(reason_code, int) and reason_code != 0):
            self.stats["connect_failures"] += 1
            log.error("connection refused by the broker service=%s reason=%s", self.settings.service, reason_code)
            return
        self.stats["connects"] += 1
        with self._lock:
            filters = dict(self._filters)
        for kind, topic_filter in filters.items():
            client.subscribe(topic_filter, qos=POLICIES[kind].qos)
        client.publish(
            self._availability_topic,
            self._availability_payload("online"),
            qos=POLICIES["availability"].qos,
            retain=POLICIES["availability"].retain,
        )
        self._connected.set()
        log.info("connected service=%s station=%s", self.settings.service, self.settings.station_id)

    def _on_disconnect(self, client: Any, userdata: Any, flags: Any, reason_code: Any = None,
                       properties: Any = None) -> None:
        self._connected.clear()
        self.stats["disconnects"] += 1
        log.warning("disconnected service=%s reason=%s", self.settings.service, reason_code)

    def _on_message(self, client: Any, userdata: Any, message: Any) -> None:
        """Never lets an exception escape: paho would stop its network thread."""
        self.stats["received"] += 1
        topic, payload = message.topic, bytes(message.payload)
        try:
            kind, event = contracts.decode(topic, payload)
        except MessagingError as exc:
            self.stats["invalid"] += 1
            # Size and reason are logged, never the content: an invalid message
            # may contain exactly what the contract forbids.
            log.warning("invalid message topic=%s bytes=%d reason=%s", topic, len(payload), exc)
            if self._on_invalid is not None:
                try:
                    self._on_invalid(topic, payload, exc)
                except Exception:  # noqa: BLE001
                    log.exception("on_invalid failed topic=%s", topic)
            return
        with self._lock:
            handler = self._handlers.get(kind)
        if handler is None:
            return
        try:
            handler(kind, event, topic)
        except Exception:  # noqa: BLE001 - a broken consumer does not bring down the connection
            self.stats["handler_errors"] += 1
            log.exception("consumer failed kind=%s event_id=%s", kind, event.get("event_id"))
