"""Messaging contract errors.

The hierarchy exists so that a consumer can tell apart three situations that
require different reactions, instead of catching a generic exception:

* :class:`UnsupportedSchemaVersion` — the producer speaks a major version we do
  not know. It is not a corrupt message: it is an out-of-step deployment. It
  is logged and discarded, and the consumer **keeps running** (ADR 0002).
* :class:`ContractViolation` — the message claims a version we do know, but
  does not comply with it. It signals a producer defect and must be
  investigated.
* :class:`PayloadTooLarge` — the message exceeds the agreed limit. It is
  handled separately because it is not even worth trying to deserialise it.
"""

from __future__ import annotations

__all__ = [
    "MessagingError",
    "ContractViolation",
    "UnsupportedSchemaVersion",
    "PayloadTooLarge",
    "TopicError",
]


class MessagingError(Exception):
    """Root of every Txori Kantua messaging error."""


class ContractViolation(MessagingError):
    """The message does not comply with the contract of its version.

    :param kind: event type (``detection``, ``environment``...).
    :param reasons: human-readable reasons. They are kept in a list because a
        message can break several rules, and fixing only the first one would
        force another full round of diagnosis.
    """

    def __init__(self, kind: str, reasons: list[str]) -> None:
        self.kind = kind
        self.reasons = list(reasons)
        detail = "; ".join(self.reasons) if self.reasons else "no detail"
        super().__init__(f"{kind!r} event does not comply with the contract: {detail}")


class UnsupportedSchemaVersion(MessagingError):
    """The message major version is not the one implemented by this consumer."""

    def __init__(self, declared: object, supported_major: int) -> None:
        self.declared = declared
        self.supported_major = supported_major
        super().__init__(
            f"schema_version {declared!r} is not compatible: "
            f"this consumer implements major version {supported_major}"
        )


class PayloadTooLarge(MessagingError):
    """The message exceeds the agreed maximum size."""

    def __init__(self, size_bytes: int, limit_bytes: int) -> None:
        self.size_bytes = size_bytes
        self.limit_bytes = limit_bytes
        super().__init__(f"payload of {size_bytes} bytes over a limit of {limit_bytes}")


class TopicError(MessagingError):
    """The topic name does not follow the ``txori/v1/...`` scheme."""
