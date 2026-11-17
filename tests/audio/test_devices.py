"""USB capture device discovery from /proc/asound text (no device opened)."""

from fakes import CARDS, STREAM_CMEDIA, fake_proc

from txori_kantua.audio.devices import (
    CaptureFormat,
    choose_device,
    parse_capture_formats,
    parse_cards,
    usb_capture_cards,
)

SCARLETT = """Focusrite Scarlett 2i2 USB at usb-0000:06:00.1-1, high speed : USB Audio

Playback:
  Status: Stop
  Interface 1
    Altset 1
    Format: S32_LE
    Channels: 2
    Rates: 44100, 48000, 88200, 96000, 176400, 192000
    Bits: 24

Capture:
  Status: Running
    Interface = 2
    Altset = 1
    Packet Size = 104
    Momentary freq = 48000 Hz (0x6.0000)
  Interface 2
    Altset 1
    Format: S32_LE
    Channels: 2
    Rates: 44100, 48000, 88200, 96000, 176400, 192000
    Bits: 24
"""


def test_parse_cards():
    cards = parse_cards(CARDS)
    assert [(c.index, c.card_id, c.driver) for c in cards] == [
        (0, "vc4hdmi0", "vc4-hdmi"), (2, "Device", "USB-Audio"), (3, "L49", "USB-Audio")]
    assert cards[1].name == "USB PnP Sound Device"
    assert cards[1].long_name.startswith("C-Media Electronics")


def test_capture_section_only():
    assert parse_capture_formats(STREAM_CMEDIA) == [
        CaptureFormat("S16_LE", 1, (48000, 44100), None, 16)]


def test_running_stream_status_lines_are_ignored():
    (fmt,) = parse_capture_formats(SCARLETT)
    assert fmt.sample_format == "S32_LE" and fmt.channels == 2 and fmt.bits == 24
    assert 48000 in fmt.rates


def test_continuous_rate_range():
    text = "X\n\nCapture:\n  Interface 1\n    Altset 1\n    Format: S16_LE\n    Channels: 1\n" \
           "    Rates: 8000 - 48000 (continuous)\n"
    (fmt,) = parse_capture_formats(text)
    assert fmt.rate_range == (8000, 48000)
    assert fmt.supports(32000, 1, "S16_LE") and not fmt.supports(96000, 1, "S16_LE")
    assert fmt.describe() == "S16_LE x1 @ 8000-48000 Hz"


def test_usb_capture_cards_excludes_midi_and_onboard(tmp_path):
    (card,) = usb_capture_cards(fake_proc(tmp_path))
    assert card.card_id == "Device" and card.usb_id == "0d8c:0014"
    assert card.hw == "hw:CARD=Device,DEV=0"


def test_missing_proc_returns_nothing(tmp_path):
    assert usb_capture_cards(tmp_path / "nothing") == []


def test_native_format_uses_hw_otherwise_plughw(tmp_path):
    (card,) = usb_capture_cards(fake_proc(tmp_path))
    assert choose_device(card, 48000, 1, "S16_LE") == ("hw:CARD=Device,DEV=0", False)
    assert choose_device(card, 16000, 1, "S16_LE") == ("plughw:CARD=Device,DEV=0", True)
    assert choose_device(card, 48000, 2, "S16_LE")[1] is True
