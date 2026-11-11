"""Conversion between RFC 3339 UTC and the storage millisecond integer.

Contracts travel as RFC 3339 with a ``Z`` suffix and storage keeps UTC epoch
milliseconds (ADR 0003, docs/adr/0003-persistence.md). That conversion happens
**only here**, so the truncation rule is not reimplemented in three different
ways in three modules.

Rules this module guarantees:

* Only ``Z`` is accepted. An offset such as ``+01:00`` is rejected: accepting
  it would force every comparison to interpret a time zone.
* The fraction of a second accepts up to nine digits in the contract, but it is
  **truncated down** to milliseconds when converting to an integer. Truncating
  rather than rounding avoids moving an observation to the next millisecond.
* ``format_timestamp`` always emits three fraction digits, so two timestamps of
  the same instant are written identically, character by character.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from .errors import ContractViolation

__all__ = [
    "RFC3339_UTC_PATTERN",
    "format_timestamp",
    "now_timestamp",
    "parse_timestamp",
    "to_epoch_ms",
    "from_epoch_ms",
]

#: Same pattern as ``common.schema.json#/$defs/timestampUtc``. It is duplicated
#: on purpose: the schema protects the system boundary and this constant
#: protects the code. ``test_timestamp_pattern_matches_the_schema`` checks that
#: they do not drift apart.
RFC3339_UTC_PATTERN = (
    r"^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])"
    r"T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](\.[0-9]{1,9})?Z$"
)

_PARSER = re.compile(
    r"^(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})"
    r"T(?P<time>[0-9]{2}:[0-9]{2}:[0-9]{2})"
    r"(?:\.(?P<frac>[0-9]{1,9}))?Z$"
)

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_NAIVE = "a datetime without a time zone is ambiguous; use timezone.utc"


def parse_timestamp(value: str) -> datetime:
    """Convert an RFC 3339 UTC timestamp into a timezone-aware ``datetime``.

    :raises ContractViolation: if the value is not a string with the exact
        contract format, or is not a real calendar date.
    """
    if not isinstance(value, str):
        raise ContractViolation("timestamp", [f"expected a string, got {type(value).__name__}"])
    match = _PARSER.match(value)
    if match is None:
        raise ContractViolation("timestamp", [f"{value!r} is not RFC 3339 in UTC with a Z suffix"])
    # ``datetime.fromisoformat`` accepts at most six fraction digits, so the
    # value is normalised to microseconds before delegating. Extra digits are
    # discarded, never rounded.
    micros = (match.group("frac") or "").ljust(6, "0")[:6]
    try:
        return datetime.fromisoformat(f"{match.group('date')}T{match.group('time')}.{micros}+00:00")
    except ValueError as exc:
        # The pattern cannot know that 30 February does not exist; the calendar can.
        raise ContractViolation("timestamp", [f"{value!r} is not a real date: {exc}"]) from exc


def format_timestamp(moment: datetime) -> str:
    """Emit an RFC 3339 UTC timestamp with milliseconds.

    Accepts any timezone-aware ``datetime`` and converts it to UTC. A naive
    ``datetime`` is rejected: assuming it is UTC is exactly the mistake that
    shifts observations by one hour in winter.
    """
    if moment.tzinfo is None:
        raise ContractViolation("timestamp", [_NAIVE])
    as_utc = moment.astimezone(timezone.utc)
    millis = as_utc.microsecond // 1000
    return f"{as_utc.strftime('%Y-%m-%dT%H:%M:%S')}.{millis:03d}Z"


def now_timestamp() -> str:
    """RFC 3339 UTC timestamp of the current instant, with milliseconds."""
    return format_timestamp(datetime.now(timezone.utc))


def to_epoch_ms(value: str | datetime) -> int:
    """UTC epoch milliseconds, truncated down.

    This is the canonical form persisted by storage. It is computed with integer
    arithmetic on a ``timedelta`` instead of ``timestamp() * 1000`` so as not to
    carry the floating-point error of epoch seconds.
    """
    moment = parse_timestamp(value) if isinstance(value, str) else value
    if moment.tzinfo is None:
        raise ContractViolation("timestamp", [_NAIVE])
    delta = moment.astimezone(timezone.utc) - _EPOCH
    return (delta.days * 86_400 + delta.seconds) * 1000 + delta.microseconds // 1000


def from_epoch_ms(epoch_ms: int) -> str:
    """Inverse of :func:`to_epoch_ms`, to serialise what comes from the database."""
    # Integer arithmetic: dividing by 1000 in floating point can shift a millisecond.
    return format_timestamp(_EPOCH + timedelta(milliseconds=int(epoch_ms)))
