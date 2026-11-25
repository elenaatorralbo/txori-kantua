"""In-memory MQTT broker for tests.

Imitates what the code uses from paho and Mosquitto: QoS 1, retained messages,
``+`` and ``#`` filters, persistent sessions, broker outage and recovery with a
bounded outgoing queue in the client, and duplicated delivery (which QoS 1
allows).

**It is not Mosquitto.** It enforces no ACL or authentication and delivers
synchronously. It is useful to test producer and consumer logic; the real
broker behaviour is verified in ``tests/broker``.
"""

from __future__ import annotations

from types import SimpleNamespace

from txori_kantua.messaging.client import MqttConnection, MqttSettings

MQTT_ERR_SUCCESS, MQTT_ERR_NO_CONN, MQTT_ERR_QUEUE_SIZE = 0, 4, 15


def topic_matches(topic_filter: str, topic: str) -> bool:
    f, t = topic_filter.split("/"), topic.split("/")
    for i, part in enumerate(f):
        if part == "#":
            return True
        if i >= len(t) or (part != "+" and part != t[i]):
            return False
    return len(f) == len(t)


class _Info:
    def __init__(self, rc: int):
        self.rc, self._published = rc, rc == MQTT_ERR_SUCCESS

    def wait_for_publish(self, timeout=None):
        return None

    def is_published(self):
        return self._published


class FakeClient:
    """Double of ``paho.mqtt.client.Client`` connected to a :class:`FakeBroker`."""

    def __init__(self, broker: "FakeBroker", name: str):
        self.broker, self.name = broker, name
        self.filters: list[str] = []
        self.queue: list[tuple] = []
        #: Messages the broker keeps for this client while it is disconnected
        #: (persistent session, clean_session=False).
        self.session_queue: list[tuple[str, bytes]] = []
        self.max_queued = 0
        self.will = None
        self.started = self.connected = False
        self.on_connect = self.on_disconnect = self.on_message = None

    # -- paho interface used by MqttConnection --
    def username_pw_set(self, username, password): ...
    def reconnect_delay_set(self, lo, hi): ...

    def max_queued_messages_set(self, n):
        self.max_queued = n

    def will_set(self, topic, payload, qos, retain):
        self.will = (topic, payload, qos, retain)

    def connect_async(self, host, port, keepalive): ...

    def loop_start(self):
        self.started = True
        self.broker.clients.append(self)
        if self.broker.up:
            self._connect()

    def loop_stop(self):
        self.started = False

    def disconnect(self):
        self.connected = False
        if self in self.broker.clients:
            self.broker.clients.remove(self)

    def subscribe(self, topic_filter, qos):
        if topic_filter not in self.filters:
            self.filters.append(topic_filter)
        for topic, payload in list(self.broker.retained.items()):
            if topic_matches(topic_filter, topic):
                self._receive(topic, payload)

    def publish(self, topic, payload, qos, retain):
        if not self.connected:
            if self.max_queued and len(self.queue) >= self.max_queued:
                return _Info(MQTT_ERR_QUEUE_SIZE)
            self.queue.append((topic, payload, retain))
            return _Info(MQTT_ERR_NO_CONN)
        self.broker.route(topic, payload, retain)
        return _Info(MQTT_ERR_SUCCESS)

    # -- internals --
    def _connect(self):
        self.connected = True
        self.on_connect(self, None, {}, 0, None)
        stored, self.session_queue = self.session_queue, []
        for topic, payload in stored:
            self._receive(topic, payload)
        pending, self.queue = self.queue, []
        for topic, payload, retain in pending:
            self.broker.route(topic, payload, retain)

    def _drop(self):
        self.connected = False
        self.on_disconnect(self, None, {}, 7, None)

    def _receive(self, topic, payload):
        self.on_message(self, None, SimpleNamespace(topic=topic, payload=payload))


class FakeBroker:
    def __init__(self):
        self.clients: list[FakeClient] = []
        self.retained: dict[str, bytes] = {}
        self.log: list[tuple[str, bytes, bool]] = []
        self.up = True
        #: How many times each message is delivered. 1 is normal; with QoS 1 a
        #: higher value is legitimate protocol behaviour.
        self.deliveries = 1
        #: Like Mosquitto's max_queued_messages: cap per disconnected client.
        self.max_session_queue = 5000

    def connection(self, service: str, station_id: str = "station-01", **settings) -> MqttConnection:
        """A real ``MqttConnection`` connected to this simulated broker."""
        conn = MqttConnection(
            MqttSettings(service=service, station_id=station_id, **settings),
            client_factory=lambda s: FakeClient(self, s.service),
        )
        conn.start()
        return conn

    def route(self, topic: str, payload: bytes, retain: bool) -> None:
        self.log.append((topic, payload, retain))
        if retain:
            self.retained[topic] = payload
        for client in list(self.clients):
            if not any(topic_matches(f, topic) for f in client.filters):
                continue
            for _ in range(self.deliveries):
                if client.connected:
                    client._receive(topic, payload)
                elif len(client.session_queue) < self.max_session_queue:
                    client.session_queue.append((topic, payload))

    def inject(self, topic: str, payload: bytes, retain: bool = False) -> None:
        """Publish arbitrary bytes, as a faulty producer would."""
        self.route(topic, payload, retain)

    def go_down(self) -> None:
        self.up = False
        for client in list(self.clients):
            if client.connected:
                client._drop()

    def come_up(self) -> None:
        self.up = True
        for client in list(self.clients):
            if client.started and not client.connected:
                client._connect()

    def kill(self, conn: MqttConnection) -> None:
        """Abrupt death of a client: the broker publishes its Last Will."""
        client = conn._client
        client.connected = client.started = False
        self.clients.remove(client)
        if client.will:
            topic, payload, _, retain = client.will
            self.route(topic, payload, retain)

    def published(self, topic: str) -> list[bytes]:
        return [p for t, p, _ in self.log if t == topic]
