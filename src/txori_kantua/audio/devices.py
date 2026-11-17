"""Identify USB capture devices and their native formats from ``/proc/asound``.

Reading ``/proc`` opens no device and records nothing. USB audio cards expose
``streamN`` files with the formats the hardware itself supports, which is the
evidence issue #7 asks for ("identify a stable device and supported formats").

Card *numbers* can change between boots or when another USB device is
plugged in. The card *id* (``[Device]`` in ``/proc/asound/cards``) is stable
for a given model, so ALSA names are built as ``hw:CARD=<id>,DEV=0``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

PROC_ASOUND = Path("/proc/asound")

_CARD_RE = re.compile(r"^\s*(\d+)\s+\[(\S+)\s*\]:\s+(\S+)\s+-\s+(.*?)\s*$")
_RANGE_RE = re.compile(r"^(\d+)\s*-\s*(\d+)")


@dataclass(frozen=True)
class CaptureFormat:
    """One capture altsetting of a USB audio interface."""

    sample_format: str
    channels: int
    rates: tuple[int, ...] = ()
    rate_range: tuple[int, int] | None = None
    bits: int | None = None

    def supports(self, rate: int, channels: int, sample_format: str) -> bool:
        if self.sample_format != sample_format or self.channels != channels:
            return False
        if rate in self.rates:
            return True
        return self.rate_range is not None and self.rate_range[0] <= rate <= self.rate_range[1]

    def describe(self) -> str:
        if self.rate_range:
            rates = f"{self.rate_range[0]}-{self.rate_range[1]} Hz"
        else:
            rates = ", ".join(str(r) for r in self.rates) + " Hz"
        bits = f", {self.bits} valid bits" if self.bits else ""
        return f"{self.sample_format} x{self.channels} @ {rates}{bits}"


@dataclass(frozen=True)
class Card:
    index: int
    card_id: str
    driver: str
    name: str
    long_name: str = ""
    usb_id: str | None = None
    capture_formats: tuple[CaptureFormat, ...] = field(default=())

    @property
    def hw(self) -> str:
        return f"hw:CARD={self.card_id},DEV=0"

    @property
    def plughw(self) -> str:
        return f"plughw:CARD={self.card_id},DEV=0"

    def supports(self, rate: int, channels: int, sample_format: str) -> bool:
        return any(f.supports(rate, channels, sample_format) for f in self.capture_formats)


def parse_cards(text: str) -> list[Card]:
    """Parse ``/proc/asound/cards``."""
    cards: list[Card] = []
    lines = text.splitlines()
    for number, line in enumerate(lines):
        match = _CARD_RE.match(line)
        if not match:
            continue
        long_name = lines[number + 1].strip() if number + 1 < len(lines) else ""
        if _CARD_RE.match(long_name):
            long_name = ""
        cards.append(Card(int(match[1]), match[2], match[3], match[4], long_name))
    return cards


def parse_capture_formats(stream_text: str) -> list[CaptureFormat]:
    """Parse the ``Capture:`` section of a USB ``/proc/asound/cardN/streamM``."""
    formats: list[CaptureFormat] = []
    in_capture = False
    current: dict[str, str] = {}

    def flush() -> None:
        if "Format" in current and "Channels" in current:
            formats.append(_build_format(current))
        current.clear()

    for raw in stream_text.splitlines():
        line = raw.strip()
        if raw and not raw[0].isspace():
            # A top-level heading: "Playback:", "Capture:" or the device line.
            flush()
            in_capture = line.startswith("Capture:")
            continue
        if not in_capture:
            continue
        if line.startswith("Interface") or line.startswith("Altset"):
            flush()
            continue
        key, sep, value = line.partition(":")
        if sep:
            current[key.strip()] = value.strip()
    flush()
    return formats


def _build_format(fields: dict[str, str]) -> CaptureFormat:
    rates_text = fields.get("Rates", "")
    rate_range = None
    rates: tuple[int, ...] = ()
    match = _RANGE_RE.match(rates_text)
    if match:
        rate_range = (int(match[1]), int(match[2]))
    else:
        rates = tuple(int(r) for r in re.findall(r"\d+", rates_text))
    bits = fields.get("Bits")
    return CaptureFormat(
        sample_format=fields["Format"].split()[0],
        channels=int(fields["Channels"]),
        rates=rates,
        rate_range=rate_range,
        bits=int(bits) if bits and bits.isdigit() else None,
    )


def usb_capture_cards(proc_root: Path = PROC_ASOUND) -> list[Card]:
    """USB audio cards that actually have a capture stream (MIDI-only excluded)."""
    try:
        cards = parse_cards((proc_root / "cards").read_text())
    except OSError:
        return []
    found = []
    for card in cards:
        if card.driver != "USB-Audio":
            continue
        directory = proc_root / f"card{card.index}"
        formats: list[CaptureFormat] = []
        for stream in sorted(directory.glob("stream*")):
            try:
                formats += parse_capture_formats(stream.read_text())
            except OSError:
                continue
        if not formats:
            continue
        try:
            usb_id = (directory / "usbid").read_text().strip() or None
        except OSError:
            usb_id = None
        found.append(Card(card.index, card.card_id, card.driver, card.name,
                          card.long_name, usb_id, tuple(formats)))
    return found


def choose_device(card: Card, rate: int, channels: int, sample_format: str) -> tuple[str, bool]:
    """ALSA name to open and whether ALSA must convert (``plughw``).

    ``hw`` is used when the hardware supports the requested format natively,
    so the measurements describe the device and not a conversion layer.
    """
    if card.supports(rate, channels, sample_format):
        return card.hw, False
    return card.plughw, True
