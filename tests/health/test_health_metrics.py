"""Resource metrics from /proc and /sys, with outputs copied from the Pi 5."""

import os

import pytest

from txori_kantua.health import metrics

# Captured on the station Pi 5 (Debian 13, kernel 6.18) on 17/11/2026.
MEMINFO = "MemTotal:        4146112 kB\nMemFree:         2383968 kB\nMemAvailable:    3675696 kB\n"
STAT_1 = "cpu  2902 21 972 575341 4328 0 34 0 0 0\ncpu0 700 5 240 143800 1080 0 10 0 0 0\n"
STAT_2 = "cpu  3902 21 1972 583341 4328 0 34 0 0 0\n"


@pytest.fixture
def proc(tmp_path):
    (tmp_path / "meminfo").write_text(MEMINFO)
    (tmp_path / "stat").write_text(STAT_1)
    (tmp_path / "uptime").write_text("1460.19 5753.41\n")
    return tmp_path


def test_memory_used_is_total_minus_available(proc):
    assert metrics.memory_used_bytes(proc) == (4146112 - 3675696) * 1024


def test_cpu_percent_between_two_samples(proc):
    before = metrics.read_cpu_times(proc)
    (proc / "stat").write_text(STAT_2)
    after = metrics.read_cpu_times(proc)
    # +1000 user, +1000 system, +8000 idle -> 20 % busy
    assert metrics.cpu_percent(before, after) == 20.0


def test_cpu_percent_is_none_without_two_samples(proc):
    assert metrics.cpu_percent(None, metrics.read_cpu_times(proc)) is None
    same = metrics.read_cpu_times(proc)
    assert metrics.cpu_percent(same, same) is None


def test_uptime_and_temperature(proc, tmp_path):
    assert metrics.uptime_seconds(proc) == 1460
    zone = tmp_path / "temp"
    zone.write_text("50150\n")
    assert metrics.cpu_temperature_c(zone) == 50.1


@pytest.mark.parametrize("content", ["", "garbage", "-273000", "200000"])
def test_unreadable_or_absurd_temperature_is_none(tmp_path, content):
    zone = tmp_path / "temp"
    zone.write_text(content)
    assert metrics.cpu_temperature_c(zone) is None


def test_missing_files_give_none_not_zero(tmp_path):
    assert metrics.memory_used_bytes(tmp_path) is None
    assert metrics.read_cpu_times(tmp_path) is None
    assert metrics.uptime_seconds(tmp_path) is None
    assert metrics.cpu_temperature_c(tmp_path / "nope") is None


def test_disk_free_uses_space_available_to_users():
    fake = os.statvfs_result((4096, 4096, 1000, 500, 300, 0, 0, 0, 0, 255))
    assert metrics.disk_free_bytes("/", statvfs=lambda _p: fake) == 300 * 4096

    def broken(_p):
        raise OSError("gone")

    assert metrics.disk_free_bytes("/x", statvfs=broken) is None
