"""Structured logging: one JSON object per line.

Fields: ``ts`` (UTC), ``level``, ``logger``, ``msg`` and any ``extra`` passed
to the log call (``event_id``, ``service``...). Under systemd, journald stores
the line and its rotation limits apply (``deploy/journald``). Exceptions are
reduced to their type and message: no tracebacks with local variables or
paths in the log.
"""

from __future__ import annotations

import json
import logging
import time

_STANDARD = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + f".{int(record.msecs):03d}Z",
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in vars(record).items():
            if key not in _STANDARD and not key.startswith("_"):
                entry[key] = value
        if record.exc_info and record.exc_info[1] is not None:
            exc = record.exc_info[1]
            entry["error"] = f"{type(exc).__name__}: {exc}"
        return json.dumps(entry, ensure_ascii=False, default=str)


def configure(level: int = logging.INFO) -> logging.Handler:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    # Replace only a previous JSON handler: calling configure twice must not
    # duplicate lines, and handlers installed by others are left alone.
    root.handlers[:] = [h for h in root.handlers if not isinstance(h.formatter, JsonFormatter)]
    root.addHandler(handler)
    root.setLevel(level)
    return handler
