"""Daily aggregates: local days, clock changes, duplicates and coverage (#28)."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from txori_kantua.aggregates import day_bounds, daily_summaries, local_date, minutes_in_day
from txori_kantua.messaging import new_detection, new_environment, new_health, reading

STATION = "station-01"
SPEC = yaml.safe_load((Path(__file__).resolve().parents[1] / "contracts" / "openapi.yaml").read_text())
REGISTRY = Registry().with_resource("urn:spec", Resource(contents=SPEC, specification=DRAFT202012))
SUMMARY = Draft202012Validator({"$ref": "urn:spec#/components/schemas/DailySummaryList"}, registry=REGISTRY)


def ts(text: str) -> str:
    return text if text.endswith("Z") else text + "Z"


def detection(at: str, species: str = "Turdus merula", confidence: float = 0.8, station: str = STATION):
    start = datetime.fromisoformat(ts(at).replace("Z", "+00:00"))
    return new_detection(station_id=station, scientific_name=species, confidence=confidence,
                         observed_at=start, window_end=start + timedelta(seconds=3),
                         model_name="BirdNET", model_version="GLOBAL_6K_V2.4-int8")


def environment(at: str, temperature: float | None = 12.0, quality: str = "ok"):
    value = temperature if quality == "ok" else None
    return new_environment(station_id=STATION, observed_at=ts(at), readings={
        "temperature": reading(value, "degC", quality),
        "pressure": reading(1002.8, "hPa"),
    })


def summarize(**kwargs):
    kwargs.setdefault("from_date", date(2026, 11, 16))
    kwargs.setdefault("to_date", date(2026, 11, 19))
    result = daily_summaries(station_id=STATION, **kwargs)
    errors = list(SUMMARY.iter_errors({"items": result}))
    assert not errors, errors
    return {item["date"]: item for item in result}


def test_local_midnight_splits_days_in_winter():
    # CET = UTC+1: 22:59:59Z is still the 17th, 23:00:00Z is already the 18th.
    days = summarize(detections=[detection("2026-11-17T22:59:59"), detection("2026-11-17T23:00:00")])
    assert days["2026-11-17"]["detections_total"] == 1
    assert days["2026-11-18"]["detections_total"] == 1
    assert days["2026-11-17"]["start_utc"] == "2026-11-16T23:00:00.000Z"
    assert days["2026-11-17"]["end_utc"] == "2026-11-17T23:00:00.000Z"


def test_duplicates_count_once():
    first = detection("2026-11-17T08:00:00", "Erithacus rubecula", 0.61)
    redelivered = json.loads(json.dumps(first))
    days = summarize(detections=[first, redelivered, detection("2026-11-17T08:05:00", "Turdus merula", 0.87),
                                 detection("2026-11-17T09:00:00", "Turdus merula", 0.5)])
    day = days["2026-11-17"]
    assert day["detections_total"] == 3
    assert day["species"] == [
        {"scientific_name": "Turdus merula", "count": 2, "max_confidence": 0.87},
        {"scientific_name": "Erithacus rubecula", "count": 1, "max_confidence": 0.61},
    ]


@pytest.mark.parametrize("day, minutes, start, end", [
    (date(2026, 3, 29), 1380, "2026-03-28T23:00:00.000Z", "2026-03-29T22:00:00.000Z"),   # spring forward
    (date(2026, 10, 25), 1500, "2026-10-24T22:00:00.000Z", "2026-10-25T23:00:00.000Z"),  # fall back
    (date(2026, 11, 17), 1440, "2026-11-16T23:00:00.000Z", "2026-11-17T23:00:00.000Z"),
])
def test_clock_change_days_have_explicit_bounds(day, minutes, start, end):
    from txori_kantua.messaging.timestamps import format_timestamp

    assert minutes_in_day(day) == minutes
    assert tuple(format_timestamp(b) for b in day_bounds(day)) == (start, end)


def test_fall_back_repeated_hour_is_neither_lost_nor_duplicated():
    # 00:30Z = 02:30 CEST and 01:30Z = 02:30 CET: same local clock time, two observations.
    events = [detection("2026-10-24T21:59:59"), detection("2026-10-25T00:30:00"),
              detection("2026-10-25T01:30:00"), detection("2026-10-25T22:59:59"),
              detection("2026-10-25T23:00:00")]
    days = summarize(detections=events, from_date=date(2026, 10, 24), to_date=date(2026, 10, 27))
    assert {d: v["detections_total"] for d, v in days.items()} == {
        "2026-10-24": 1, "2026-10-25": 3, "2026-10-26": 1}
    assert sum(v["detections_total"] for v in days.values()) == len(events)


def test_spring_forward_day_keeps_every_observation():
    events = [detection("2026-03-28T22:59:59"), detection("2026-03-28T23:00:00"),
              detection("2026-03-29T01:30:00"), detection("2026-03-29T21:59:59"),
              detection("2026-03-29T22:00:00")]
    days = summarize(detections=events, from_date=date(2026, 3, 28), to_date=date(2026, 3, 31))
    assert {d: v["detections_total"] for d, v in days.items()} == {
        "2026-03-28": 1, "2026-03-29": 3, "2026-03-30": 1}


def test_environment_statistics_ignore_failed_readings():
    days = summarize(environment=[environment("2026-11-17T10:00:00", 10.0),
                                  environment("2026-11-17T10:00:30", 14.0),
                                  environment("2026-11-17T10:01:00", quality="unavailable"),
                                  environment("2026-11-17T10:01:30", quality="error")])
    temperature = days["2026-11-17"]["environment"]["temperature"]
    assert temperature == {"unit": "degC", "count": 2, "min": 10.0, "max": 14.0, "mean": 12.0}
    assert days["2026-11-17"]["environment"]["pressure"]["count"] == 4


def test_zero_detections_is_distinguished_from_no_data():
    health = new_health(station_id=STATION, services={"station": "healthy"}, observed_at="2026-11-18T12:00:00Z")
    days = summarize(environment=[environment("2026-11-17T10:00:00")], other_events=[health])
    assert days["2026-11-17"]["detections_total"] == 0          # running, no birds
    assert days["2026-11-17"]["coverage"] == {"minutes_with_data": 1, "minutes_in_day": 1440}
    assert days["2026-11-18"]["environment"] == {}               # only health: still a day with data
    assert "2026-11-16" not in days                               # no event at all: no data


def test_other_stations_and_out_of_range_days_are_ignored():
    days = summarize(detections=[detection("2026-11-17T08:00:00", station="station-02"),
                                 detection("2026-11-20T08:00:00")])
    assert days == {}


def test_range_is_validated():
    with pytest.raises(ValueError):
        daily_summaries(station_id=STATION, from_date=date(2026, 11, 17), to_date=date(2026, 11, 17))
    with pytest.raises(ValueError, match="92"):
        daily_summaries(station_id=STATION, from_date=date(2026, 1, 1), to_date=date(2026, 6, 1))


def test_local_date_helper():
    assert local_date("2026-07-01T22:30:00Z") == date(2026, 7, 2)  # CEST = UTC+2
    assert local_date(datetime(2026, 1, 1, 22, 30, tzinfo=timezone.utc)) == date(2026, 1, 1)
