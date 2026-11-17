"""Recognise audio in bytes, files and message payloads.

These checks back the privacy audit of issue #11. They answer one question:
"could this contain audio?". They are deliberately cautious: a finding is a
reason for a person to look, not proof of a leak, and an empty result is only
as good as the paths and payloads that were actually inspected.

Nothing here reads more than a few bytes of a file, decodes audio or keeps the
content it inspects: a finding records where and why, never the data.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import stat
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

#: Bytes read from the start of each file to recognise its format.
HEADER_BYTES = 16

#: File extensions that hold audio, or raw samples without a header.
AUDIO_EXTENSIONS = frozenset({
    ".wav", ".wave", ".bwf", ".rf64", ".flac", ".mp3", ".mp2", ".ogg", ".oga",
    ".opus", ".spx", ".m4a", ".m4b", ".aac", ".adts", ".aif", ".aiff", ".aifc",
    ".caf", ".au", ".snd", ".amr", ".3gp", ".wma", ".webm", ".mka", ".weba",
    ".pcm", ".raw", ".s16", ".f32", ".npy", ".npz",
})

#: JSON keys that suggest samples or recordings travel in a payload.
SUSPICIOUS_KEYS = frozenset({
    "audio", "audio_b64", "audio_base64", "audio_data", "pcm", "samples",
    "sample_data", "wav", "waveform", "recording", "recordings", "clip",
    "sound", "raw_audio", "buffer", "spectrogram", "mel",
})

#: A numeric list this long in a payload looks like samples, not metadata.
MAX_NUMERIC_ARRAY = 256
#: A base64 string this long is reported even if it has no audio header.
MAX_OPAQUE_BASE64 = 4096
#: Shortest string worth trying as base64 (a WAV header is 44 bytes).
MIN_BASE64_PROBE = 24

_BASE64_RE = re.compile(r"^[A-Za-z0-9+/_-]+={0,2}$")
_DATA_URI_RE = re.compile(r"^data:(audio|video)/", re.IGNORECASE)

#: Directories never walked: virtual filesystems with no persistent content.
_SKIP_ROOTS = ("/proc", "/sys", "/dev/pts")
#: Installed Python packages ship data such as NumPy's ``.npy`` test fixtures.
#: They are library files, not runtime output, and audio services cannot write
#: there (ProtectSystem=strict), so walking them only adds false positives.
_SKIP_DIRS = frozenset({"site-packages", "dist-packages", "__pycache__", ".git"})


@dataclass(frozen=True)
class Finding:
    """Something that may be audio. ``location`` never contains the data."""

    location: str
    reason: str


def sniff(header: bytes) -> str | None:
    """Return the audio container recognised at the start of ``header``.

    Covers the formats a microphone pipeline or a careless debug dump would
    produce. Raw PCM has no signature and is therefore NOT recognised here:
    file extensions and payload shape catch that case instead.
    """
    if len(header) < 4:
        return None
    if header[:4] in (b"RIFF", b"RIFX", b"RF64", b"BW64") and header[8:12] == b"WAVE":
        return "WAV"
    if header[:4] == b"FORM" and header[8:12] in (b"AIFF", b"AIFC"):
        return "AIFF"
    if header[:4] == b"fLaC":
        return "FLAC"
    if header[:4] == b"OggS":
        return "Ogg (Vorbis/Opus/FLAC)"
    if header[:3] == b"ID3":
        return "MP3 (ID3 tag)"
    if header[:4] == b"caff":
        return "CAF"
    if header[:4] == b".snd":
        return "AU"
    if header[:5] == b"#!AMR":
        return "AMR"
    if header[:4] == b"\x1aE\xdf\xa3":
        return "Matroska/WebM"
    if header[4:8] == b"ftyp":
        return "MP4/M4A container"
    if header[:6] == b"\x93NUMPY":
        return "NumPy array"
    if _is_mpeg_frame(header):
        return "MPEG audio frame (MP3/AAC)"
    return None


def _is_mpeg_frame(header: bytes) -> bool:
    # 11 sync bits, then a valid version/layer pair (MP1-3) or ADTS (AAC).
    if header[0] != 0xFF or header[1] & 0xE0 != 0xE0:
        return False
    version = (header[1] >> 3) & 0b11
    layer = (header[1] >> 1) & 0b11
    if layer == 0:  # ADTS: layer is always 00 and version is MPEG-2/4.
        return header[1] & 0xF6 == 0xF0
    bitrate = header[2] >> 4
    rate = (header[2] >> 2) & 0b11
    return version != 0b01 and bitrate not in (0, 0xF) and rate != 0b11


def sniff_file(path: Path) -> str | None:
    """Recognise a file by extension and by its first bytes."""
    try:
        with open(path, "rb") as handle:
            kind = sniff(handle.read(HEADER_BYTES))
    except OSError:
        kind = None
    if kind:
        return kind
    if path.suffix.lower() in AUDIO_EXTENSIONS:
        return f"audio extension {path.suffix.lower()}"
    return None


@dataclass
class TreeScan:
    """Result of walking a set of directories."""

    findings: list[Finding]
    new_files: list[str]
    files_checked: int = 0
    unreadable: int = 0


def scan_tree(
    roots: Iterable[Path | str],
    *,
    newer_than: float | None = None,
    allowed_sha256: frozenset[str] = frozenset(),
) -> TreeScan:
    """Walk ``roots`` and report files that look like audio.

    ``newer_than`` (epoch seconds) additionally lists every file modified since
    then, audio or not, so a reviewer can see everything a test run created.
    Files whose SHA-256 is in ``allowed_sha256`` (for example an authorised
    evaluation corpus with a recorded licence) are not reported. Symbolic links
    are not followed and other filesystems under a root are still walked.
    """
    result = TreeScan(findings=[], new_files=[])
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        for path in _walk(root, result):
            result.files_checked += 1
            try:
                info = path.lstat()
            except OSError:
                result.unreadable += 1
                continue
            if newer_than is not None and info.st_mtime >= newer_than:
                result.new_files.append(str(path))
            kind = sniff_file(path)
            if kind is None:
                continue
            if allowed_sha256 and _sha256(path) in allowed_sha256:
                continue
            result.findings.append(Finding(str(path), kind))
    return result


def _walk(root: Path, result: TreeScan) -> Iterator[Path]:
    if root.is_file():
        yield root
        return
    def on_error(_error: OSError) -> None:
        result.unreadable += 1
    for directory, dirnames, filenames in os.walk(root, onerror=on_error):
        if directory.startswith(_SKIP_ROOTS):
            dirnames.clear()
            continue
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for name in filenames:
            path = Path(directory, name)
            try:
                if stat.S_ISREG(path.lstat().st_mode):
                    yield path
            except OSError:
                result.unreadable += 1


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
    except OSError:
        return ""
    return digest.hexdigest()


def inspect_payload(payload: bytes | str, *, location: str = "payload") -> list[Finding]:
    """Inspect one message (MQTT body, API response, log line) for audio.

    JSON is walked recursively; anything else is checked as raw bytes. The
    contracts only allow JSON, so an opaque binary payload is itself reported.
    """
    raw = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
    kind = sniff(raw[:HEADER_BYTES])
    if kind:
        return [Finding(location, f"binary {kind} payload")]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return [Finding(location, f"non-text payload of {len(raw)} bytes")]
    try:
        document = json.loads(text)
    except ValueError:
        return _inspect_string(text.strip(), location)
    return list(_inspect_json(document, location))


def _inspect_json(value: object, location: str) -> Iterator[Finding]:
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{location}.{key}"
            if str(key).lower() in SUSPICIOUS_KEYS:
                yield Finding(child, f"suspicious key {key!r}")
            yield from _inspect_json(item, child)
    elif isinstance(value, list):
        numbers = sum(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value)
        if numbers >= MAX_NUMERIC_ARRAY:
            yield Finding(location, f"numeric array of {len(value)} items (possible samples)")
            return
        for index, item in enumerate(value):
            yield from _inspect_json(item, f"{location}[{index}]")
    elif isinstance(value, str):
        yield from _inspect_string(value, location)


def _inspect_string(value: str, location: str) -> list[Finding]:
    if _DATA_URI_RE.match(value):
        return [Finding(location, "data: URI with audio/video media type")]
    if Path(value).suffix.lower() in AUDIO_EXTENSIONS and len(value) < 4096:
        return [Finding(location, "path or name of an audio file")]
    if len(value) >= MIN_BASE64_PROBE and _BASE64_RE.match(value):
        kind = sniff(_b64_prefix(value))
        if kind:
            return [Finding(location, f"base64-encoded {kind}")]
        if len(value) >= MAX_OPAQUE_BASE64:
            return [Finding(location, f"opaque base64 string of {len(value)} characters")]
    return []


def _b64_prefix(value: str) -> bytes:
    chunk = value[:64].rstrip("=")
    chunk += "=" * (-len(chunk) % 4)
    decode = base64.urlsafe_b64decode if ("-" in chunk or "_" in chunk) else base64.b64decode
    try:
        return decode(chunk)
    except (binascii.Error, ValueError):
        return b""
