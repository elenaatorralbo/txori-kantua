"""Logging filter that keeps audio buffers out of every log record.

The rule in docs/privacy.md is "no sample logging". Code review enforces it;
this filter is the safety net for the mistake that review misses, such as
``log.debug("window %s", buffer)``. Any binary or array argument is replaced
by its size before the record is formatted, so the samples never reach a
handler, journald or a file.
"""

from __future__ import annotations

import array
import logging

#: Arrays smaller than this are allowed (shapes, a few metrics), not samples.
MAX_ARRAY_ITEMS = 64


def _is_buffer(value: object) -> bool:
    if isinstance(value, (bytes, bytearray, memoryview, array.array)):
        return True
    # numpy and other array libraries, without importing them.
    size = getattr(value, "size", None)
    return (
        hasattr(value, "__array_interface__")
        and isinstance(size, int)
        and size > MAX_ARRAY_ITEMS
    )


def _describe(value: object) -> str:
    nbytes = getattr(value, "nbytes", None)
    if nbytes is None:
        nbytes = len(value)  # type: ignore[arg-type]
    return f"<redacted {type(value).__name__} of {nbytes} bytes>"


class AudioLogFilter(logging.Filter):
    """Replace binary or large array arguments of a record by their size."""

    def filter(self, record: logging.LogRecord) -> bool:
        if _is_buffer(record.msg):
            record.msg = _describe(record.msg)
        args = record.args
        if isinstance(args, tuple):
            record.args = tuple(_describe(a) if _is_buffer(a) else a for a in args)
        elif isinstance(args, dict):
            record.args = {k: _describe(v) if _is_buffer(v) else v for k, v in args.items()}
        return True


def install(logger: logging.Logger | None = None) -> AudioLogFilter:
    """Attach the filter to every handler of ``logger`` (root by default).

    Handler filters see records from child loggers too, unlike logger filters.
    Call it after configuring logging, in every process that touches audio.
    """
    target = logger or logging.getLogger()
    guard = AudioLogFilter()
    for handler in target.handlers:
        if not any(isinstance(f, AudioLogFilter) for f in handler.filters):
            handler.addFilter(guard)
    return guard
