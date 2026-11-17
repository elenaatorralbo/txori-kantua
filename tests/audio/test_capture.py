"""Capture windows from fake arecord processes: timing, failures, statistics."""

import array
import math
import time

import pytest
from fakes import CONFIG, tone_command

from txori_kantua.audio.capture import (
    ArecordStream,
    CaptureConfig,
    CaptureStalled,
    DeviceUnavailable,
    arecord_command,
    window_stats,
)


def stream(**kwargs):
    return ArecordStream(CONFIG, command=tone_command(**kwargs))


def test_arecord_command_writes_raw_pcm_to_stdout_only():
    cmd = arecord_command(CaptureConfig(device="hw:CARD=Device,DEV=0"))
    assert cmd == ["arecord", "-q", "-D", "hw:CARD=Device,DEV=0", "-t", "raw",
                   "-f", "S16_LE", "-r", "48000", "-c", "1"]
    # No output file argument: arecord writes to stdout.
    assert not any(part.endswith((".wav", ".raw")) for part in cmd)


def test_window_geometry():
    config = CaptureConfig(device="d")
    assert config.window_frames == 144000 and config.window_bytes == 288000


@pytest.mark.parametrize("kwargs", [
    {"sample_format": "U8"}, {"rate": 0}, {"window_seconds": -1}, {"stall_timeout_s": 0}])
def test_invalid_config(kwargs):
    with pytest.raises(ValueError):
        CaptureConfig(device="d", **kwargs)


def test_ten_consecutive_windows_reuse_one_buffer():
    with stream() as s:
        buffer = s.new_buffer()
        for _ in range(10):
            assert s.read_window(buffer) is buffer
            assert len(buffer) == CONFIG.window_bytes
            assert window_stats(buffer, CONFIG).rms_dbfs > -20
        assert s.running
    assert not s.running


def test_unplug_mid_window_raises_device_unavailable_with_reason():
    with stream(limit=CONFIG.window_bytes + 100, then="exit") as s:
        s.read_window()
        t0 = time.monotonic()
        with pytest.raises(DeviceUnavailable, match="No such device"):
            s.read_window()
        assert time.monotonic() - t0 < CONFIG.stall_timeout_s + 2
    assert not s.running


def test_stalled_device_does_not_block_forever():
    with stream(limit=0, then="hang") as s:
        t0 = time.monotonic()
        with pytest.raises(CaptureStalled):
            s.read_window()
        assert time.monotonic() - t0 < CONFIG.stall_timeout_s + 1
        assert not s.running  # the stuck process was stopped


def test_missing_program_is_device_unavailable():
    with pytest.raises(DeviceUnavailable, match="cannot start"):
        ArecordStream(CONFIG, command=["/nonexistent/arecord"]).start()


def test_overruns_are_counted_from_stderr():
    with stream(overrun=True) as s:
        s.read_window()
        time.sleep(0.1)
        assert s.overruns == 1
        assert "overrun" in s.diagnostics[0]


def test_wrong_buffer_size_is_rejected():
    with stream() as s, pytest.raises(ValueError):
        s.read_window(bytearray(10))


def test_read_before_start_is_an_error():
    with pytest.raises(RuntimeError):
        stream().read_window()


def pcm(values):
    return array.array("h", values).tobytes()


def test_stats_of_a_sine_tone():
    rate, freq, amp = 8000, 1000, 16384
    samples = [round(amp * math.sin(2 * math.pi * freq * i / rate + 0.1)) for i in range(800)]
    stats = window_stats(pcm(samples), CONFIG)
    assert stats.peak_dbfs == pytest.approx(-6.0, abs=0.2)
    assert stats.rms_dbfs == pytest.approx(-9.0, abs=0.2)  # amplitude / sqrt(2)
    assert stats.zero_crossing_hz == pytest.approx(1000, rel=0.02)
    assert not stats.silent and not stats.clipping


def test_stats_detect_clipping_silence_and_dc():
    clipped = window_stats(pcm([32767, -32768] * 400), CONFIG)
    assert clipped.clipping and clipped.clipped_fraction == 1.0
    silent = window_stats(pcm([0] * 800), CONFIG)
    assert silent.silent and math.isinf(silent.rms_dbfs)
    offset = window_stats(pcm([3277] * 800), CONFIG)
    assert offset.dc_offset == pytest.approx(0.1, abs=0.001)


def test_stats_of_stereo_s32():
    config = CaptureConfig(device="d", rate=8000, channels=2, sample_format="S32_LE", window_seconds=0.1)
    frames = [v for i in range(800) for v in (int(2**30 * math.sin(2 * math.pi * 500 * i / 8000)), 0)]
    stats = window_stats(array.array("i", frames).tobytes(), config)
    assert stats.zero_crossing_hz == pytest.approx(500, rel=0.02)
    assert stats.peak_dbfs == pytest.approx(-6.0, abs=0.2)
