"""Health events are contract-valid, logged with event_id, and flag budgets."""

import io
import json
import logging

from txori_kantua.health import jsonlog
from txori_kantua.health.monitor import Monitor, Thresholds, breaches, main, parse_services
from txori_kantua.health.services import ServiceWatcher
from txori_kantua.messaging import validate


def watcher(*outputs):
    it = iter(outputs)
    return ServiceWatcher({"station": "txori-kantua.service"}, run=lambda cmd: next(it))


RUNNING = "LoadState=loaded\nActiveState=active\nSubState=running\nNRestarts=0\n"
STOPPED = "LoadState=loaded\nActiveState=inactive\nSubState=dead\nNRestarts=0\n"


def test_event_is_valid_even_when_metrics_are_missing(tmp_path, caplog):
    monitor = Monitor("station-01", watcher(STOPPED), proc=tmp_path, thermal=tmp_path / "none",
                      disk_path=str(tmp_path))
    with caplog.at_level(logging.INFO, logger="txori_kantua.health"):
        event = monitor.sample()
    validate("health", event)
    assert event["services"] == {"station": "failed"}
    assert event["cpu_percent"] is None and event["memory_used_bytes"] is None
    assert isinstance(event["disk_free_bytes"], int)
    record = caplog.records[0]
    assert record.levelno == logging.WARNING
    assert record.event_id == event["event_id"]
    assert record.systemd == "inactive/dead"


def test_status_change_logged_once(tmp_path, caplog):
    monitor = Monitor("station-01", watcher(RUNNING, RUNNING, STOPPED), proc=tmp_path, thermal=tmp_path / "x")
    with caplog.at_level(logging.INFO, logger="txori_kantua.health"):
        for _ in range(3):
            monitor.sample()
    assert [r.getMessage() for r in caplog.records] == ["service station is healthy", "service station is failed"]


def test_breaches_use_measured_budgets():
    limits = Thresholds()
    assert breaches({"cpu_temperature_c": 79.9, "disk_free_bytes": 5 * 1024**3}, limits) == []
    assert breaches({"cpu_temperature_c": 81.0}, limits) == ["cpu_temperature_c 81.0 >= 80.0"]
    assert breaches({"disk_free_bytes": 10, "cpu_percent": None}, limits) == ["disk_free_bytes 10 <= 1073741824"]


def test_json_log_line_carries_extra_fields_and_no_traceback():
    record = logging.LogRecord("txori_kantua.health", logging.WARNING, __file__, 1, "service %s is %s",
                               ("station", "failed"), None)
    record.event_id = "e1"
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        import sys
        record.exc_info = sys.exc_info()
    line = json.loads(jsonlog.JsonFormatter().format(record))
    assert line["msg"] == "service station is failed"
    assert line["event_id"] == "e1"
    assert line["level"] == "warning"
    assert line["error"] == "RuntimeError: boom"
    assert "Traceback" not in json.dumps(line)


def test_parse_services():
    assert parse_services(None) == {"station": "txori-kantua.service"}
    assert parse_services(["capture=txori-capture.service", "api=txori-api.service"]) == {
        "capture": "txori-capture.service", "api": "txori-api.service"}


def test_main_once_writes_one_valid_json_line(monkeypatch):
    monkeypatch.setattr("txori_kantua.health.monitor.time.sleep", lambda _s: None)
    out = io.StringIO()
    assert main(["--once"], watcher_factory=lambda units: watcher(STOPPED), out=out) == 0
    lines = out.getvalue().splitlines()
    assert len(lines) == 1
    validate("health", json.loads(lines[0]))
