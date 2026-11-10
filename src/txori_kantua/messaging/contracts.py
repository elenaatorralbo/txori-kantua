"""Validation of events against the MQTT v1 contracts.

The JSON Schemas in ``contracts/mqtt/`` are the source of truth. This module
loads them, resolves their ``$ref`` locally (never over the network) and adds
the few rules that JSON Schema cannot express. Those extra rules are listed in
``contracts/README.md``; if one is added here, it is documented there.

Typical producer usage::

    payload = encode("detection", event)          # validates and serialises
    client.publish(topic, payload, qos=1)

Typical consumer usage::

    try:
        kind, event = decode(topic, payload)
    except UnsupportedSchemaVersion:
        ...  # log and carry on
    except MessagingError:
        ...  # log and carry on: a bad message never stops the consumer
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .errors import ContractViolation, PayloadTooLarge, UnsupportedSchemaVersion
from .timestamps import to_epoch_ms
from .topics import KINDS, parse_topic

__all__ = [
    "MAX_PAYLOAD_BYTES",
    "SUPPORTED_MAJOR",
    "CURRENT_SCHEMA_VERSION",
    "contracts_dir",
    "load_schema",
    "validate",
    "encode",
    "decode",
]

#: Maximum size of a serialised message (16 KiB, docs/mqtt.md). A legitimate
#: event takes a few hundred bytes; anything close to the limit is suspected of
#: carrying something that is not metadata.
MAX_PAYLOAD_BYTES = 16 * 1024

SUPPORTED_MAJOR = 1
CURRENT_SCHEMA_VERSION = "1.0"

_ENV_DIR = "TXORI_CONTRACTS_DIR"


def contracts_dir() -> Path:
    """The ``contracts/mqtt`` directory.

    Taken from ``TXORI_CONTRACTS_DIR`` if set (deployment); otherwise it is
    searched for walking up from this file (cloned repository or editable
    install).
    """
    override = os.environ.get(_ENV_DIR)
    if override:
        candidate = Path(override)
        if (candidate / "common.schema.json").is_file():
            return candidate
        raise FileNotFoundError(f"{_ENV_DIR}={override!r} does not contain common.schema.json")
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "contracts" / "mqtt"
        if (candidate / "common.schema.json").is_file():
            return candidate
    raise FileNotFoundError(f"contracts/mqtt not found; set {_ENV_DIR} to its path")


@lru_cache(maxsize=1)
def _registry() -> tuple[Registry, dict[str, dict[str, Any]]]:
    schemas: dict[str, dict[str, Any]] = {}
    registry = Registry()
    for path in sorted(contracts_dir().glob("*.schema.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
        schemas[path.name.removesuffix(".schema.json")] = schema
    return registry, schemas


def load_schema(kind: str) -> dict[str, Any]:
    """Return the JSON Schema of an event type."""
    _, schemas = _registry()
    if kind not in KINDS or kind not in schemas:
        raise ContractViolation(kind, [f"there is no contract for type {kind!r}"])
    return schemas[kind]


@lru_cache(maxsize=None)
def _validator(kind: str) -> Draft202012Validator:
    registry, _ = _registry()
    return Draft202012Validator(load_schema(kind), registry=registry)


def _check_version(event: dict[str, Any]) -> None:
    """Tell "unknown major version" apart from "invalid message"."""
    declared = event.get("schema_version")
    if isinstance(declared, str):
        major, _, _ = declared.partition(".")
        if major.isdigit() and int(major) != SUPPORTED_MAJOR:
            raise UnsupportedSchemaVersion(declared, SUPPORTED_MAJOR)


def _semantic_reasons(kind: str, event: dict[str, Any], station_in_topic: str | None,
                      service_in_topic: str | None) -> list[str]:
    """Rules that JSON Schema cannot express. See contracts/README.md."""
    reasons: list[str] = []
    # Dates that match the pattern but do not exist (30 February).
    moments: dict[str, int] = {}
    for field in ("observed_at", "window_end"):
        if field in event:
            try:
                moments[field] = to_epoch_ms(event[field])
            except ContractViolation as exc:
                reasons.extend(f"{field}: {r}" for r in exc.reasons)
    if kind == "detection" and len(moments) == 2 and moments["window_end"] <= moments["observed_at"]:
        reasons.append("window_end must be later than observed_at")
    if station_in_topic is not None and event["station_id"] != station_in_topic:
        reasons.append(
            f"station_id {event['station_id']!r} does not match the topic station {station_in_topic!r}"
        )
    if kind == "availability" and service_in_topic is not None and event["service"] != service_in_topic:
        reasons.append(
            f"service {event['service']!r} does not match the topic service {service_in_topic!r}"
        )
    return reasons


def validate(kind: str, event: Any, *, topic: str | None = None) -> None:
    """Validate an already deserialised event.

    :param topic: if given, also checks that the message ``station_id`` (and
        ``service`` for availability) match those in the topic.
    :raises UnsupportedSchemaVersion: major version other than the supported one.
    :raises ContractViolation: with **every** reason found.
    """
    if not isinstance(event, dict):
        raise ContractViolation(kind, ["the message must be a JSON object"])
    _check_version(event)
    errors = sorted(_validator(kind).iter_errors(event), key=lambda e: list(e.absolute_path))
    if errors:
        raise ContractViolation(
            kind,
            [f"{'/'.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}" for e in errors],
        )
    station = service = None
    if topic is not None:
        parsed = parse_topic(topic)
        if parsed.kind != kind:
            raise ContractViolation(kind, [f"topic {topic!r} is of type {parsed.kind!r}"])
        station, service = parsed.station_id, parsed.service
    reasons = _semantic_reasons(kind, event, station, service)
    if reasons:
        raise ContractViolation(kind, reasons)


def encode(kind: str, event: dict[str, Any]) -> bytes:
    """Validate and serialise an event as compact UTF-8 JSON.

    Serialisation is deterministic (sorted keys): resending the same event
    produces exactly the same bytes.
    """
    validate(kind, event)
    payload = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                         allow_nan=False).encode("utf-8")
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise PayloadTooLarge(len(payload), MAX_PAYLOAD_BYTES)
    return payload


def decode(topic: str, payload: bytes | bytearray | str) -> tuple[str, dict[str, Any]]:
    """Interpret and validate a message received on ``topic``.

    The size is checked **before** deserialising: a huge message is not even
    worth the cost of parsing it.

    :returns: ``(kind, event)``.
    :raises TopicError: foreign topic or topic of another version.
    :raises PayloadTooLarge, UnsupportedSchemaVersion, ContractViolation:
        depending on the case. They all derive from ``MessagingError``.
    """
    parsed = parse_topic(topic)
    raw = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
    if len(raw) > MAX_PAYLOAD_BYTES:
        raise PayloadTooLarge(len(raw), MAX_PAYLOAD_BYTES)
    try:
        event = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractViolation(parsed.kind, [f"not valid UTF-8 JSON: {exc}"]) from exc
    validate(parsed.kind, event, topic=topic)
    return parsed.kind, event
