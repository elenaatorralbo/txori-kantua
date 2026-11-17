"""Swap and dump checks against fake /proc, /sys and /etc trees."""

from pathlib import Path

import pytest

from txori_kantua.privacy.system import (
    Status,
    check_core_pattern,
    check_process_core_limit,
    check_stored_coredumps,
    check_suid_dumpable,
    check_swap,
    check_tmp,
    run_checks,
)

SWAPS_HEADER = "Filename\t\t\t\tType\t\tSize\t\tUsed\t\tPriority\n"


def write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_no_swap_passes(tmp_path):
    write(tmp_path, "proc/swaps", SWAPS_HEADER)
    assert check_swap(tmp_path).status is Status.PASS


def test_disk_swap_fails(tmp_path):
    write(tmp_path, "proc/swaps", SWAPS_HEADER + "/var/swap  file  2097148  0  -2\n")
    check = check_swap(tmp_path)
    assert check.status is Status.FAIL
    assert "/var/swap" in check.observed


def test_zram_without_writeback_passes(tmp_path):
    write(tmp_path, "proc/swaps", SWAPS_HEADER + "/dev/zram0  partition  2097148  0  100\n")
    write(tmp_path, "sys/block/zram0/backing_dev", "none\n")
    check = check_swap(tmp_path)
    assert check.status is Status.PASS
    assert "no writeback" in check.observed


def test_zram_with_writeback_file_fails(tmp_path):
    write(tmp_path, "proc/swaps", SWAPS_HEADER + "/dev/zram0  partition  2097148  0  100\n")
    write(tmp_path, "sys/block/zram0/backing_dev", "/dev/loop0\n")
    assert check_swap(tmp_path).status is Status.FAIL


def test_unreadable_swap_is_unknown(tmp_path):
    assert check_swap(tmp_path).status is Status.UNKNOWN


@pytest.mark.parametrize("conf, dropin, status", [
    (None, None, Status.FAIL),
    ("[Coredump]\nStorage=external\n", None, Status.FAIL),
    ("[Coredump]\nStorage=none\n", None, Status.PASS),
    ("[Coredump]\n#Storage=external\n", "[Coredump]\nStorage=none\n", Status.PASS),
    ("[Coredump]\nStorage=none\n", "[Coredump]\nStorage=journal\n", Status.FAIL),
])
def test_systemd_coredump_storage(tmp_path, conf, dropin, status):
    write(tmp_path, "proc/sys/kernel/core_pattern",
          "|/lib/systemd/systemd-coredump %P %u %g %s %t 9223372036854775808 %h\n")
    if conf is not None:
        write(tmp_path, "etc/systemd/coredump.conf", conf)
    if dropin is not None:
        write(tmp_path, "etc/systemd/coredump.conf.d/50-txori.conf", dropin)
    assert check_core_pattern(tmp_path).status is status


def test_plain_core_pattern_depends_on_limit(tmp_path):
    write(tmp_path, "proc/sys/kernel/core_pattern", "core\n")
    assert check_core_pattern(tmp_path).status is Status.WARN


def test_suid_dumpable(tmp_path):
    write(tmp_path, "proc/sys/fs/suid_dumpable", "0\n")
    assert check_suid_dumpable(tmp_path).status is Status.PASS
    write(tmp_path, "proc/sys/fs/suid_dumpable", "2\n")
    assert check_suid_dumpable(tmp_path).status is Status.WARN


LIMITS = """Limit                     Soft Limit           Hard Limit           Units
Max cpu time              unlimited            unlimited            seconds
Max core file size        {soft}                    {hard}                    bytes
"""


def test_service_core_limit(tmp_path):
    write(tmp_path, "proc/42/limits", LIMITS.format(soft=0, hard=0))
    assert check_process_core_limit(tmp_path, 42).status is Status.PASS
    write(tmp_path, "proc/42/limits", LIMITS.format(soft=0, hard="unlimited"))
    assert check_process_core_limit(tmp_path, 42).status is Status.FAIL
    assert check_process_core_limit(tmp_path, 7).status is Status.UNKNOWN


def test_tmp_mount(tmp_path):
    write(tmp_path, "proc/self/mounts", "/dev/mmcblk0p2 / ext4 rw 0 0\ntmpfs /tmp tmpfs rw 0 0\n")
    assert check_tmp(tmp_path).status is Status.PASS
    write(tmp_path, "proc/self/mounts", "/dev/mmcblk0p2 / ext4 rw 0 0\n")
    assert check_tmp(tmp_path).status is Status.WARN


def test_stored_coredumps(tmp_path):
    assert check_stored_coredumps(tmp_path).status is Status.PASS
    write(tmp_path, "var/lib/systemd/coredump/core.python3.1000.zst", "x")
    assert check_stored_coredumps(tmp_path).status is Status.FAIL


def test_run_checks_never_raises_on_an_empty_tree(tmp_path):
    checks = run_checks(tmp_path, pid=1)
    assert len(checks) == 7
    assert all(isinstance(c.status, Status) for c in checks)


def test_shipped_coredump_dropin_passes(tmp_path):
    shipped = Path(__file__).resolve().parents[2] / "deploy/privacy/90-txori-no-coredump.conf"
    write(tmp_path, "proc/sys/kernel/core_pattern", "|/lib/systemd/systemd-coredump %P\n")
    write(tmp_path, "etc/systemd/coredump.conf.d/90-txori-no-coredump.conf", shipped.read_text())
    assert check_core_pattern(tmp_path).status is Status.PASS


def test_shipped_swap_dropin_selects_ram_only_zram():
    import configparser

    shipped = Path(__file__).resolve().parents[2] / "deploy/privacy/90-txori-zram-only.conf"
    parser = configparser.ConfigParser()
    parser.read_string(shipped.read_text())
    assert parser.get("Main", "Mechanism") == "zram"
