"""Publishing of bird detections (issue #18).

This is the seam between inference (David) and the rest of the system.
Inference hands over one :class:`InferenceResult` per species detected in a
window and this module takes care of everything else: building the v1 event,
giving it a stable identifier, publishing it and retrying without duplicating.

    publisher = DetectionPublisher(connection)
    publisher.publish(InferenceResult(
        scientific_name="Turdus merula", confidence=0.87,
        window_start=start, window_end=end,
        model_name="BirdNET", model_version=version,
    ))

Guarantees:

* **Stable identity.** ``event_id`` is derived from the station, the window and
  the species. Publishing the same detection twice —because of a retry, or
  because inference restarted and analysed the same window again— produces the
  same identifier, and persistence stores it only once.
* **Retrying does not alter the event.** Pending events are resent as they
  are: same bytes, same ``observed_at``.
* **No retain.** Detections are published with ``retain=False``: a retained
  event would be delivered to every new subscriber as if it had just happened.
* **No audio.** :class:`InferenceResult` has no field able to carry samples,
  paths or coordinates, and the contract would reject the event if it had one.
* **Bounded memory.** Whatever could not be delivered is kept in a fixed-size
  queue; when full, the oldest entry is discarded and counted.
"""

from __future__ import annotations

import logging
from collections import Counter, OrderedDict
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from . import events
from .client import MqttConnection
from .timestamps import format_timestamp, parse_timestamp

__all__ = ["InferenceResult", "DetectionPublisher"]

log = logging.getLogger("txori_kantua.messaging.detections")


@dataclass(frozen=True)
class InferenceResult:
    """What inference knows about a detection. Nothing else crosses this boundary.

    PROVISIONAL: the shape is settled with David (docs/interfaces.md). If
    BirdNET returns several candidate species for a window, each one that
    passes the filter is an ``InferenceResult`` and, therefore, a separate
    event.
    """

    scientific_name: str
    confidence: float
    window_start: datetime | str
    window_end: datetime | str
    model_name: str
    model_version: str
    taxon_key: str | None = None


class DetectionPublisher:
    """Publishes detections accepted by inference.

    :param connection: connection of the producer service (user ``inference``).
    :param max_pending: undelivered detections kept in memory. At about 400
        bytes per event, the default is less than 0.5 MB.
    """

    def __init__(self, connection: MqttConnection, *, max_pending: int = 1000) -> None:
        if max_pending < 1:
            raise ValueError("max_pending must be at least 1")
        self._connection = connection
        self._max_pending = max_pending
        self._pending: OrderedDict[str, dict[str, Any]] = OrderedDict()
        #: ``published``, ``retried``, ``deferred``, ``dropped``.
        self.stats: Counter[str] = Counter()

    @property
    def pending(self) -> int:
        """Detections waiting to be handed to the outgoing queue."""
        return len(self._pending)

    def build_event(self, result: InferenceResult) -> dict[str, Any]:
        """Build the v1 event of a detection, without publishing it."""
        station_id = self._connection.settings.station_id
        observed_at = _as_timestamp(result.window_start)
        window_end = _as_timestamp(result.window_end)
        return events.new_detection(
            station_id=station_id,
            scientific_name=result.scientific_name,
            confidence=result.confidence,
            observed_at=observed_at,
            window_end=window_end,
            model_name=result.model_name,
            model_version=result.model_version,
            taxon_key=result.taxon_key,
            event_id=events.stable_event_id("detection", station_id, observed_at, window_end,
                                            result.scientific_name),
        )

    def publish(self, result: InferenceResult) -> dict[str, Any]:
        """Publish a detection and return the generated event.

        Never blocks inference: if the broker is not there, the event stays in
        the connection's outgoing queue; if that queue is full, it stays
        pending here and is retried with :meth:`flush`.

        :raises MessagingError: if the result cannot form a valid event (for
            example, a confidence outside 0–1). It is a producer defect and is
            not silenced.
        """
        self.flush()
        event = self.build_event(result)
        self._send(event, retry=False)
        return event

    def flush(self) -> int:
        """Retry pending events, in order. Returns how many are still pending.

        It should be called periodically when there are no new detections, so
        that pending events go out as soon as the connection returns.
        """
        for event_id in list(self._pending):
            if not self._send(self._pending[event_id], retry=True):
                break
        return len(self._pending)

    def _send(self, event: dict[str, Any], *, retry: bool) -> bool:
        event_id = event["event_id"]
        result = self._connection.publish("detection", event)
        if result.accepted:
            self._pending.pop(event_id, None)
            self.stats["retried" if retry else "published"] += 1
            return True
        if event_id not in self._pending:
            self.stats["deferred"] += 1
            self._pending[event_id] = event
            while len(self._pending) > self._max_pending:
                dropped_id, _ = self._pending.popitem(last=False)
                self.stats["dropped"] += 1
                log.warning("detection dropped because the queue is full event_id=%s", dropped_id)
        return False


def _as_timestamp(value: datetime | str) -> str:
    # Always normalised to the same notation (milliseconds, Z): the same
    # instant written in two ways must give the same event_id.
    return format_timestamp(value if isinstance(value, datetime) else parse_timestamp(value))
