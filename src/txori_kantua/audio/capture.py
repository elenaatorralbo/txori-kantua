"""Capture fixed-size audio windows into RAM through ``arecord``.

``arecord`` (alsa-utils, present on Raspberry Pi OS) writes raw PCM to a pipe
and this module reads it straight into a caller-owned, reused buffer. No file
is created at any point: there is no WAV header, no temporary path and no
spool (ADR 0006). The samples never leave the buffer except as the numbers
computed by :func:`window_stats`.

A subprocess instead of a Python audio binding keeps the dependency list
empty and gives a clean failure boundary: when the USB device disappears,
``arecord`` exits or stops producing data, and :meth:`ArecordStream.read_window`
raises within ``stall_timeout_s`` instead of blocking forever.
"""

from __future__ import annotations

import array
import math
import os
import select
import subprocess
import sys
import threading
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass

#: Bytes per sample of the formats this module can analyse.
SAMPLE_BYTES = {"S16_LE": 2, "S32_LE": 4}
_ARRAY_CODES = {"S16_LE": "h", "S32_LE": "i"}

#: RMS below this level is reported as silence (dBFS).
SILENCE_DBFS = -60.0


class CaptureError(Exception):
    """The capture could not produce a complete window."""


class DeviceUnavailable(CaptureError):
    """The capture process ended: device missing, unplugged or busy."""


class CaptureStalled(CaptureError):
    """No data arrived within the stall timeout; the process was stopped."""


@dataclass(frozen=True)
class CaptureConfig:
    device: str
    rate: int = 48000
    channels: int = 1
    sample_format: str = "S16_LE"
    window_seconds: float = 3.0
    #: Longest wait for the *next* bytes before declaring the device stalled.
    stall_timeout_s: float = 2.0

    def __post_init__(self) -> None:
        if self.sample_format not in SAMPLE_BYTES:
            raise ValueError(f"unsupported sample format {self.sample_format!r}")
        if self.rate <= 0 or self.channels <= 0 or self.window_seconds <= 0:
            raise ValueError("rate, channels and window_seconds must be positive")
        if self.stall_timeout_s <= 0:
            raise ValueError("stall_timeout_s must be positive")

    @property
    def frame_bytes(self) -> int:
        return SAMPLE_BYTES[self.sample_format] * self.channels

    @property
    def window_frames(self) -> int:
        return round(self.rate * self.window_seconds)

    @property
    def window_bytes(self) -> int:
        return self.window_frames * self.frame_bytes


def arecord_command(config: CaptureConfig) -> list[str]:
    """Raw PCM to stdout, no header, no file, until stopped."""
    return [
        "arecord", "-q", "-D", config.device, "-t", "raw",
        "-f", config.sample_format, "-r", str(config.rate), "-c", str(config.channels),
    ]


class ArecordStream:
    """A running capture process that yields consecutive windows.

    Use as a context manager so the process is always stopped::

        with ArecordStream(config) as stream:
            buffer = stream.new_buffer()
            stream.read_window(buffer)   # overwritten on every call
    """

    def __init__(self, config: CaptureConfig, command: Sequence[str] | None = None) -> None:
        self.config = config
        self.command = list(command) if command is not None else arecord_command(config)
        self._process: subprocess.Popen[bytes] | None = None
        self._stderr: deque[str] = deque(maxlen=50)
        self._stderr_thread: threading.Thread | None = None
        self.overruns = 0

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        if self._process is not None:
            raise RuntimeError("stream already started")
        try:
            self._process = subprocess.Popen(
                self.command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, bufsize=0, close_fds=True,
            )
        except OSError as exc:  # arecord not installed, for instance
            raise DeviceUnavailable(f"cannot start capture: {exc}") from exc
        self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._stderr_thread.start()

    def close(self) -> None:
        process, self._process = self._process, None
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        if process.stdout:
            process.stdout.close()
        if self._stderr_thread:
            self._stderr_thread.join(timeout=2)

    def __enter__(self) -> ArecordStream:
        self.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @property
    def diagnostics(self) -> list[str]:
        """Recent stderr lines of the capture process (never audio)."""
        return list(self._stderr)

    def _drain_stderr(self) -> None:
        process = self._process
        if process is None or process.stderr is None:
            return
        for raw in process.stderr:
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            if "overrun" in line.lower():
                self.overruns += 1
            self._stderr.append(line)
        process.stderr.close()

    # -- reading -------------------------------------------------------------

    def new_buffer(self) -> bytearray:
        return bytearray(self.config.window_bytes)

    def read_window(self, buffer: bytearray | None = None) -> bytearray:
        """Fill ``buffer`` (or a new one) with exactly one window.

        :raises DeviceUnavailable: the process ended before the window was full.
        :raises CaptureStalled: no bytes for ``stall_timeout_s``; the process is
            stopped so the caller never blocks indefinitely.
        """
        process = self._process
        if process is None or process.stdout is None:
            raise RuntimeError("stream not started")
        if buffer is None:
            buffer = self.new_buffer()
        if len(buffer) != self.config.window_bytes:
            raise ValueError("buffer size does not match the window size")
        fd = process.stdout.fileno()
        view = memoryview(buffer)
        filled = 0
        try:
            while filled < len(buffer):
                ready, _, _ = select.select([fd], [], [], self.config.stall_timeout_s)
                if not ready:
                    self.close()
                    raise CaptureStalled(
                        f"no audio for {self.config.stall_timeout_s:.1f} s "
                        f"after {filled} of {len(buffer)} bytes")
                count = os.readv(fd, [view[filled:]])
                if count == 0:
                    raise DeviceUnavailable(self._exit_reason(filled, len(buffer)))
                filled += count
        finally:
            view.release()
        return buffer

    def _exit_reason(self, filled: int, wanted: int) -> str:
        process = self._process
        code = None
        if process is not None:
            try:
                code = process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
        if self._stderr_thread:
            self._stderr_thread.join(timeout=1)
        detail = self._stderr[-1] if self._stderr else "no message"
        self.close()
        return f"capture ended (exit {code}) after {filled} of {wanted} bytes: {detail}"


# ---------------------------------------------------------------------------
# Signal statistics: numbers about the window, never the window itself
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WindowStats:
    peak_dbfs: float
    rms_dbfs: float
    clipped_fraction: float
    dc_offset: float
    #: Rough tone frequency from zero crossings; meaningful only for a test tone.
    zero_crossing_hz: float

    @property
    def silent(self) -> bool:
        return self.rms_dbfs < SILENCE_DBFS

    @property
    def clipping(self) -> bool:
        return self.clipped_fraction > 0.001


def _dbfs(value: float) -> float:
    return 20 * math.log10(value) if value > 0 else -math.inf


def window_stats(buffer: bytes | bytearray | memoryview, config: CaptureConfig) -> WindowStats:
    """Level, clipping and DC offset of one window (all channels together)."""
    samples = array.array(_ARRAY_CODES[config.sample_format])
    samples.frombytes(buffer)
    if sys.byteorder == "big":
        samples.byteswap()
    if not samples:
        raise ValueError("empty window")
    full_scale = float(1 << (8 * SAMPLE_BYTES[config.sample_format] - 1))
    low, high = min(samples), max(samples)
    peak = max(-low, high) / full_scale
    total = float(sum(samples))
    squares = math.fsum(float(s) * s for s in samples)
    rms = math.sqrt(squares / len(samples)) / full_scale
    limit = full_scale - 2
    clipped = sum(1 for s in samples if s >= limit or s <= -limit - 1)
    mono = samples[:: config.channels] if config.channels > 1 else samples
    crossings = sum(1 for a, b in zip(mono, mono[1:]) if (a < 0) != (b < 0))
    seconds = len(mono) / config.rate
    return WindowStats(
        peak_dbfs=_dbfs(peak),
        rms_dbfs=_dbfs(rms),
        clipped_fraction=clipped / len(samples),
        dc_offset=total / len(samples) / full_scale,
        zero_crossing_hz=crossings / 2 / seconds,
    )
