"""Daily aggregates per Europe/Madrid local day (issue #28).

Input: contract events as stored (``detection`` and ``environment`` dicts;
any event of the station counts for coverage). Output: one ``DailySummary``
of ``contracts/openapi.yaml`` per local day **with data**.

Rules:

- A day is the Europe/Madrid local day. Storage stays in UTC; ``start_utc``
  and ``end_utc`` make the limits explicit, so the clock-change days last 23
  and 25 hours and no observation is lost or counted twice.
- Duplicates (same ``event_id``, e.g. a QoS 1 redelivery) count once.
- Environmental statistics use only readings with quality ``ok``: a gap is
  never averaged as a zero.
- ``coverage`` separates "zero detections" from "no data": a day with
  ``detections_total == 0`` and ``minutes_with_data > 0`` had a running
  station and no birds; a day without any event has no item at all.

Pure functions: the API (#20) and the dashboard queries (#21) reuse them or
reproduce them in SQL, and the projection can be rebuilt from base tables.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from txori_kantua.messaging.timestamps import format_timestamp, parse_timestamp

TIMEZONE_NAME = "Europe/Madrid"
TIMEZONE = ZoneInfo(TIMEZONE_NAME)
MAX_DAYS = 92
METRICS = ("temperature", "humidity", "pressure", "light")


def local_date(timestamp: str | datetime) -> date:
    moment = parse_timestamp(timestamp) if isinstance(timestamp, str) else timestamp
    return moment.astimezone(TIMEZONE).date()


def day_bounds(day: date) -> tuple[datetime, datetime]:
    """UTC start (included) and end (excluded) of a local day."""
    start = datetime.combine(day, time(0), TIMEZONE)
    end = datetime.combine(day + timedelta(days=1), time(0), TIMEZONE)
    return start.astimezone(ZoneInfo("UTC")), end.astimezone(ZoneInfo("UTC"))


def minutes_in_day(day: date) -> int:
    start, end = day_bounds(day)
    return int((end - start).total_seconds() // 60)


def _unique(events: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    seen: set[str] = set()
    result = []
    for event in events:
        event_id = event["event_id"]
        if event_id not in seen:
            seen.add(event_id)
            result.append(event)
    return result


class _Metric:
    __slots__ = ("unit", "count", "low", "high", "total")

    def __init__(self, unit: str) -> None:
        self.unit, self.count, self.low, self.high, self.total = unit, 0, math.inf, -math.inf, 0.0

    def add(self, value: float) -> None:
        self.count += 1
        self.low, self.high = min(self.low, value), max(self.high, value)
        self.total += value

    def summary(self) -> dict[str, Any]:
        return {"unit": self.unit, "count": self.count, "min": round(self.low, 3),
                "max": round(self.high, 3), "mean": round(self.total / self.count, 3)}


class _Day:
    def __init__(self) -> None:
        self.species: dict[str, list[float]] = defaultdict(list)
        self.metrics: dict[str, _Metric] = {}
        self.minutes: set[int] = set()


def daily_summaries(
    *,
    station_id: str,
    from_date: date,
    to_date: date,
    detections: Iterable[Mapping[str, Any]] = (),
    environment: Iterable[Mapping[str, Any]] = (),
    other_events: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Summaries for local days in ``[from_date, to_date)``, oldest first."""
    if to_date <= from_date:
        raise ValueError("to_date must be after from_date")
    if (to_date - from_date).days > MAX_DAYS:
        raise ValueError(f"at most {MAX_DAYS} days per request")

    days: dict[date, _Day] = defaultdict(_Day)

    def place(event: Mapping[str, Any]) -> _Day | None:
        if event.get("station_id") != station_id:
            return None
        moment = parse_timestamp(event["observed_at"])
        day = moment.astimezone(TIMEZONE).date()
        if not from_date <= day < to_date:
            return None
        bucket = days[day]
        bucket.minutes.add(int(moment.timestamp() // 60))
        return bucket

    for event in _unique(detections):
        bucket = place(event)
        if bucket is not None:
            bucket.species[event["species"]["scientific_name"]].append(float(event["confidence"]))

    for event in _unique(environment):
        bucket = place(event)
        if bucket is None:
            continue
        for metric, reading in event["readings"].items():
            if metric not in METRICS or reading.get("quality") != "ok" or reading.get("value") is None:
                continue
            bucket.metrics.setdefault(metric, _Metric(reading["unit"])).add(float(reading["value"]))

    for event in other_events:
        place(event)

    summaries = []
    for day in sorted(days):
        bucket = days[day]
        start, end = day_bounds(day)
        species = sorted(
            ({"scientific_name": name, "count": len(conf), "max_confidence": round(max(conf), 4)}
             for name, conf in bucket.species.items()),
            key=lambda s: (-s["count"], s["scientific_name"]),
        )
        summaries.append({
            "date": day.isoformat(),
            "timezone": TIMEZONE_NAME,
            "start_utc": format_timestamp(start),
            "end_utc": format_timestamp(end),
            "station_id": station_id,
            "detections_total": sum(s["count"] for s in species),
            "species": species,
            "environment": {m: bucket.metrics[m].summary() for m in METRICS if m in bucket.metrics},
            "coverage": {"minutes_with_data": len(bucket.minutes), "minutes_in_day": minutes_in_day(day)},
        })
    return summaries
