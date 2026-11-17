"""systemd states mapped to the contract: a stopped service is not healthy."""

import pytest

from txori_kantua.health.services import ServiceWatcher, UnitState, classify, parse_show

# `systemctl show` output captured on the Pi with the station stopped.
STOPPED = "NRestarts=0\nLoadState=loaded\nActiveState=inactive\nSubState=dead\n"
NOT_FOUND = "NRestarts=0\nLoadState=not-found\nActiveState=inactive\nSubState=dead\n"


def show(active, sub, restarts=0, load="loaded"):
    return f"LoadState={load}\nActiveState={active}\nSubState={sub}\nNRestarts={restarts}\n"


def test_parse_real_output():
    assert parse_show(STOPPED) == UnitState("loaded", "inactive", "dead", 0)


@pytest.mark.parametrize("text, expected", [
    (show("active", "running"), "healthy"),
    (show("active", "exited"), "healthy"),
    (show("activating", "auto-restart"), "degraded"),
    (show("deactivating", "stop-sigterm"), "degraded"),
    (STOPPED, "failed"),
    (show("failed", "failed"), "failed"),
    (NOT_FOUND, "failed"),
    ("", "failed"),
])
def test_classification(text, expected):
    assert classify(parse_show(text)) == expected


def test_restart_since_last_check_is_degraded_then_healthy_again():
    outputs = iter([show("active", "running", 0), show("active", "running", 1), show("active", "running", 1)])
    watcher = ServiceWatcher({"station": "txori-kantua.service"}, run=lambda cmd: next(outputs))
    assert [watcher.check()["station"] for _ in range(3)] == ["healthy", "degraded", "healthy"]


def test_controlled_stop_turns_not_healthy():
    outputs = iter([show("active", "running"), STOPPED])
    watcher = ServiceWatcher({"station": "txori-kantua.service"}, run=lambda cmd: next(outputs))
    assert watcher.check() == {"station": "healthy"}
    assert watcher.check() == {"station": "failed"}


def test_systemctl_unavailable_is_failed():
    def broken(cmd):
        raise OSError("no systemctl")

    assert ServiceWatcher({"x": "x.service"}, run=broken).check() == {"x": "failed"}


def test_command_asks_only_for_the_needed_properties():
    seen = []
    ServiceWatcher({"station": "txori-kantua.service"}, run=lambda cmd: seen.append(cmd) or STOPPED).check()
    assert seen == [["systemctl", "show", "txori-kantua.service",
                     "--property=LoadState,ActiveState,SubState,NRestarts"]]
