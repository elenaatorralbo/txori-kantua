"""The issue #7 report end to end, with fake capture processes."""

import pytest
from fakes import CONFIG, factory, fake_proc

from txori_kantua.audio.capture import ArecordStream
from txori_kantua.audio.mic_check import main, run_disconnect

ARGS = ["--rate", "8000", "--seconds", "0.1", "--stall-timeout", "0.5"]


@pytest.fixture
def proc(tmp_path):
    return fake_proc(tmp_path / "proc")


def test_list(proc, capsys):
    assert main(["--list"], proc_root=proc) == 0
    out = capsys.readouterr().out
    assert "hw:CARD=Device,DEV=0" in out and "0d8c:0014" in out and "L49" not in out


def test_ten_windows_report_passes(proc, tmp_path, capsys):
    code = main(ARGS + ["--expect-tone", "1000", "--scan", str(tmp_path / "scan")],
                factory=factory(), proc_root=proc)
    out = capsys.readouterr().out
    assert code == 0, out
    assert "Windows captured without error: **10 / 10**" in out
    assert "tone mismatch" not in out
    assert "| 10 consecutive windows without error | PASS |" in out
    assert "| No audio file created by the capture | PASS |" in out
    # 8 kHz is not native for the fake card, so ALSA conversion is declared.
    assert "plughw:CARD=Device,DEV=0" in out and "ALSA converts" in out


def test_capture_error_fails_the_report(proc, tmp_path, capsys):
    code = main(ARGS + ["--scan", str(tmp_path)], proc_root=proc,
                factory=factory(limit=CONFIG.window_bytes * 3, then="exit"))
    out = capsys.readouterr().out
    assert code == 1
    assert "**ERROR**" in out and "**FAIL**" in out


def test_audio_file_left_behind_fails_the_report(proc, tmp_path, capsys):
    from txori_kantua.privacy.audit import synthetic_wav

    scan = tmp_path / "scan"
    scan.mkdir()

    def leaky(config):
        (scan / "debug.wav").write_bytes(synthetic_wav())
        return ArecordStream(config, command=factory()(config).command)

    assert main(ARGS + ["--windows", "2", "--scan", str(scan)], factory=leaky, proc_root=proc) == 1
    assert "debug.wav" in capsys.readouterr().out


def test_no_device_is_a_usage_error(tmp_path, capsys):
    empty = fake_proc(tmp_path / "proc", cards=" 0 [vc4hdmi0 ]: vc4-hdmi - x\n   x\n")
    assert main(ARGS, factory=factory(), proc_root=empty) == 2
    assert "Connect the USB microphone" in capsys.readouterr().err


def test_disconnect_detected_and_reopen_fails_fast(proc):
    calls = []

    def unplugging(config):
        calls.append(1)
        if len(calls) == 1:  # first stream: three windows, then the device goes away
            return factory(limit=config.window_bytes * 3, then="exit")(config)
        return factory(limit=0, then="exit")(config)  # device absent

    result = run_disconnect(unplugging, CONFIG, max_wait_s=10, reconnect_wait_s=0,
                            card_id="Device", proc_root=proc, prompt=lambda _t: None)
    assert result.windows_before == 3
    assert "DeviceUnavailable" in result.error
    assert result.reopen_error and result.reopen_s < 3


def test_disconnect_report_with_reconnection(proc, capsys):
    calls = []

    def unplug_then_back(config):
        calls.append(1)
        if len(calls) == 1:
            return factory(limit=config.window_bytes, then="exit")(config)
        if len(calls) == 2:
            return factory(limit=0, then="exit")(config)
        return factory()(config)

    code = main(ARGS + ["--disconnect-test", "--reconnect-wait", "5", "--scan"],
                factory=unplug_then_back, proc_root=proc)
    out = capsys.readouterr().out
    assert code == 0, out
    assert "captured a window after" in out
    assert "| Disconnection detected without blocking | PASS |" in out


def test_no_unplug_within_wait_fails(proc, capsys):
    code = main(ARGS + ["--disconnect-test", "--max-wait", "0.5", "--scan"],
                factory=factory(), proc_root=proc)
    assert code == 1
    assert "No disconnection observed" in capsys.readouterr().out


def test_pre_existing_audio_is_reported_but_not_blamed_on_the_capture(proc, tmp_path, capsys):
    import os
    import time

    from txori_kantua.privacy.audit import synthetic_wav

    old = tmp_path / "scan" / "old.wav"
    old.parent.mkdir()
    old.write_bytes(synthetic_wav())
    past = time.time() - 3600
    os.utime(old, (past, past))
    assert main(ARGS + ["--windows", "1", "--scan", str(old.parent)], factory=factory(), proc_root=proc) == 0
    assert "Pre-existing audio-like files (older than the run, review separately): 1" in capsys.readouterr().out
