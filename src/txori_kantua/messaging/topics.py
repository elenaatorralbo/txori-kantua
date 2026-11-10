"""MQTT v1 topic names and their QoS and retain policy.

No module should write a ``"txori/v1/..."`` string by hand: topics are built
and interpreted here, so that a change to the topic scheme is an edit in a
single file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import TopicError

__all__ = [
    "TOPIC_ROOT",
    "TOPIC_VERSION",
    "KINDS",
    "TopicPolicy",
    "ParsedTopic",
    "POLICIES",
    "topic_for",
    "availability_topic",
    "subscription_for",
    "parse_topic",
]

TOPIC_ROOT = "txori"
TOPIC_VERSION = "v1"

#: Event types with a contract. The name matches the JSON Schema file name.
KINDS = ("detection", "environment", "health", "availability")

_SEGMENT = {
    "detection": "detections",
    "environment": "environment",
    "health": "health",
    "availability": "availability",
}
_KIND_BY_SEGMENT = {segment: kind for kind, segment in _SEGMENT.items()}

_STATION = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
_SERVICE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


@dataclass(frozen=True)
class TopicPolicy:
    """Agreed QoS and retain for an event type."""

    qos: int
    retain: bool


#: Events (detection, environment) are never retained: a retained event would
#: be delivered again to every subscriber that connects, as if it had just
#: happened. Only state (health, availability) is retained.
POLICIES = {
    "detection": TopicPolicy(qos=1, retain=False),
    "environment": TopicPolicy(qos=1, retain=False),
    "health": TopicPolicy(qos=1, retain=True),
    "availability": TopicPolicy(qos=1, retain=True),
}


@dataclass(frozen=True)
class ParsedTopic:
    """Result of interpreting a received topic."""

    kind: str
    station_id: str
    service: str | None = None


def _check_station(station_id: str) -> str:
    if not isinstance(station_id, str) or not _STATION.match(station_id):
        raise TopicError(f"invalid station_id: {station_id!r}")
    return station_id


def topic_for(kind: str, station_id: str) -> str:
    """Publication topic for ``detection``, ``environment`` or ``health``."""
    if kind == "availability":
        raise TopicError("availability needs the service: use availability_topic()")
    if kind not in _SEGMENT:
        raise TopicError(f"unknown event type: {kind!r}")
    return f"{TOPIC_ROOT}/{TOPIC_VERSION}/{_check_station(station_id)}/{_SEGMENT[kind]}"


def availability_topic(station_id: str, service: str) -> str:
    """Retained availability topic of a service (and of its Last Will)."""
    if not isinstance(service, str) or not _SERVICE.match(service):
        raise TopicError(f"invalid service name: {service!r}")
    return (
        f"{TOPIC_ROOT}/{TOPIC_VERSION}/{_check_station(station_id)}"
        f"/{_SEGMENT['availability']}/{service}"
    )


def subscription_for(kind: str, station_id: str = "+") -> str:
    """Subscription filter. ``station_id='+'`` covers every station."""
    if kind not in _SEGMENT:
        raise TopicError(f"unknown event type: {kind!r}")
    station = station_id if station_id == "+" else _check_station(station_id)
    base = f"{TOPIC_ROOT}/{TOPIC_VERSION}/{station}/{_SEGMENT[kind]}"
    return f"{base}/+" if kind == "availability" else base


def parse_topic(topic: str) -> ParsedTopic:
    """Interpret a received topic.

    :raises TopicError: if it does not belong to ``txori/v1`` or its shape is
        invalid. A version other than ``v1`` is also a ``TopicError``: the
        consumer logs it and ignores it, without stopping.
    """
    parts = topic.split("/") if isinstance(topic, str) else []
    if len(parts) < 4 or parts[0] != TOPIC_ROOT:
        raise TopicError(f"topic outside {TOPIC_ROOT}: {topic!r}")
    if parts[1] != TOPIC_VERSION:
        raise TopicError(f"unsupported topic version: {parts[1]!r}")
    station_id = _check_station(parts[2])
    kind = _KIND_BY_SEGMENT.get(parts[3])
    if kind is None:
        raise TopicError(f"unknown segment in {topic!r}")
    if kind == "availability":
        if len(parts) != 5 or not _SERVICE.match(parts[4]):
            raise TopicError(f"malformed availability topic: {topic!r}")
        return ParsedTopic(kind=kind, station_id=station_id, service=parts[4])
    if len(parts) != 4:
        raise TopicError(f"extra segments in {topic!r}")
    return ParsedTopic(kind=kind, station_id=station_id)
