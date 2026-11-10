"""Txori Kantua messaging contracts (MQTT v1).

Public interface for the other modules. Anything not exported here is an
internal detail and may change without notice.
"""

from .client import MqttConnection, MqttSettings, PublishResult
from .contracts import (
    CURRENT_SCHEMA_VERSION,
    MAX_PAYLOAD_BYTES,
    SUPPORTED_MAJOR,
    decode,
    encode,
    load_schema,
    validate,
)
from .errors import (
    ContractViolation,
    MessagingError,
    PayloadTooLarge,
    TopicError,
    UnsupportedSchemaVersion,
)
from .events import (
    availability,
    new_detection,
    new_environment,
    new_event_id,
    new_health,
    reading,
    stable_event_id,
)
from .timestamps import (
    format_timestamp,
    from_epoch_ms,
    now_timestamp,
    parse_timestamp,
    to_epoch_ms,
)
from .topics import (
    KINDS,
    POLICIES,
    ParsedTopic,
    TopicPolicy,
    availability_topic,
    parse_topic,
    subscription_for,
    topic_for,
)

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "MAX_PAYLOAD_BYTES",
    "SUPPORTED_MAJOR",
    "KINDS",
    "POLICIES",
    "ContractViolation",
    "MessagingError",
    "MqttConnection",
    "MqttSettings",
    "ParsedTopic",
    "PayloadTooLarge",
    "PublishResult",
    "TopicError",
    "TopicPolicy",
    "UnsupportedSchemaVersion",
    "availability",
    "availability_topic",
    "decode",
    "encode",
    "format_timestamp",
    "from_epoch_ms",
    "load_schema",
    "new_detection",
    "new_environment",
    "new_event_id",
    "new_health",
    "now_timestamp",
    "parse_timestamp",
    "parse_topic",
    "reading",
    "stable_event_id",
    "subscription_for",
    "to_epoch_ms",
    "topic_for",
    "validate",
]
