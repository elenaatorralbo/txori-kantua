"""Fake capture processes and /proc/asound trees for the audio tests.

The fakes generate synthetic tones in a child Python process that speaks the
same protocol as ``arecord -t raw``: raw PCM on stdout, messages on stderr.
No microphone is opened and nothing is recorded.
"""

import sys
from pathlib import Path

from txori_kantua.audio.capture import ArecordStream, CaptureConfig

_TONE = r"""
import math, struct, sys, time
rate, freq, amp = int(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])
limit = int(sys.argv[4])          # bytes before failing; -1 = endless
mode = sys.argv[5]                # "exit" | "hang" after the limit
if sys.argv[6] == "overrun":
    sys.stderr.write("overrun!!! (at least 1.234 ms long)\n"); sys.stderr.flush()
out, sent, i = sys.stdout.buffer, 0, 0
while limit < 0 or sent < limit:
    chunk = b"".join(struct.pack("<h", max(-32768, min(32767, int(amp * math.sin(2 * math.pi * freq * (i + k) / rate)))))
                     for k in range(400))
    if limit >= 0:
        chunk = chunk[: limit - sent]
    i += 400
    out.write(chunk); out.flush(); sent += len(chunk)
    time.sleep(0.001)
if mode == "exit":
    sys.stderr.write("arecord: pcm_read:2221: read error: No such device\n"); sys.stderr.flush()
    sys.exit(1)
time.sleep(3600)
"""

#: Small, fast windows for the tests: 0.1 s at 8 kHz, 16-bit mono.
CONFIG = CaptureConfig(device="fake", rate=8000, window_seconds=0.1, stall_timeout_s=0.5)


def tone_command(*, rate=8000, freq=1000.0, amp=10000.0, limit=-1, then="hang", overrun=False):
    return [sys.executable, "-c", _TONE, str(rate), str(freq), str(amp), str(limit), then,
            "overrun" if overrun else "-"]


def factory(**kwargs):
    return lambda config: ArecordStream(config, command=tone_command(rate=config.rate, **kwargs))


CARDS = """ 0 [vc4hdmi0       ]: vc4-hdmi - vc4-hdmi-0
                      vc4-hdmi-0
 2 [Device         ]: USB-Audio - USB PnP Sound Device
                      C-Media Electronics Inc. USB PnP Sound Device at usb-xhci-hcd.1-1, full speed
 3 [L49            ]: USB-Audio - Launchkey MK3 49
                      Focusrite - Novation Launchkey MK3 49 at usb-0000:06:00.1-2, full speed
"""

STREAM_CMEDIA = """C-Media Electronics Inc. USB PnP Sound Device at usb-xhci-hcd.1-1, full speed : USB Audio

Playback:
  Status: Stop
  Interface 1
    Altset 1
    Format: S16_LE
    Channels: 2
    Endpoint: 0x01 (1 OUT) (ADAPTIVE)
    Rates: 48000, 44100
    Bits: 16

Capture:
  Status: Stop
  Interface 2
    Altset 1
    Format: S16_LE
    Channels: 1
    Endpoint: 0x82 (2 IN) (ASYNC)
    Rates: 48000, 44100
    Bits: 16
    Channel map: MONO
"""


def fake_proc(root: Path, cards: str = CARDS) -> Path:
    asound = root / "asound"
    asound.mkdir(parents=True, exist_ok=True)
    (asound / "cards").write_text(cards)
    for index in (0, 2, 3):
        (asound / f"card{index}").mkdir(exist_ok=True)
    (asound / "card2" / "stream0").write_text(STREAM_CMEDIA)
    (asound / "card2" / "usbid").write_text("0d8c:0014\n")
    (asound / "card3" / "usbid").write_text("1235:0136\n")  # MIDI only: no stream file
    return asound
