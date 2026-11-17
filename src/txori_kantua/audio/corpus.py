"""Authorised evaluation corpus for the BirdNET benchmark (issue #8).

The manifest ``corpus.json`` records origin, author, licence and SHA-256 of
each recording. Recordings are downloaded on demand into a cache directory,
verified, and decoded through an ``ffmpeg`` pipe straight into memory as
48 kHz mono float32. They are never committed to Git (``.gitignore`` and
``tests/test_repository_has_no_audio.py``) and are not station audio: the
privacy audit can allow them by hash with ``--allow-manifest``.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .birdnet import SAMPLE_RATE, WINDOW_SAMPLES

MANIFEST = Path(__file__).with_name("corpus.json")
DEFAULT_CACHE = Path.home() / ".cache" / "txori-kantua" / "corpus"
#: Wikimedia asks automated clients to identify themselves with a project URL.
USER_AGENT = "txori-kantua-benchmark/0.1 (+https://github.com/elenaatorralbo/txori-kantua)"
#: A trailing piece shorter than this is dropped instead of zero-padded.
MIN_TAIL_SAMPLES = SAMPLE_RATE  # 1 s


@dataclass(frozen=True)
class Recording:
    id: str
    species: str
    file: str
    download_url: str
    page_url: str
    author: str
    license: str
    license_url: str
    sha256: str
    bytes: int

    def path(self, cache: Path) -> Path:
        return cache / self.file


def load_manifest(path: Path = MANIFEST) -> list[Recording]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    fields = Recording.__dataclass_fields__
    return [Recording(**{k: v for k, v in item.items() if k in fields}) for item in data["recordings"]]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(recordings: list[Recording], cache: Path = DEFAULT_CACHE, *,
          pause_s: float = 3.0, retries: int = 4,
          opener=urllib.request.urlopen) -> list[Path]:
    """Download missing recordings and verify every file's SHA-256.

    Already present and valid files are not downloaded again. A pause between
    downloads and backoff on HTTP 429 respect Wikimedia's rate limits.
    """
    cache.mkdir(parents=True, exist_ok=True)
    paths = []
    for number, rec in enumerate(recordings):
        path = rec.path(cache)
        if not (path.exists() and _sha256(path) == rec.sha256):
            if number:
                time.sleep(pause_s)
            data = _download(rec.download_url, retries=retries, opener=opener)
            if hashlib.sha256(data).hexdigest() != rec.sha256:
                raise ValueError(f"{rec.id}: SHA-256 does not match the manifest")
            tmp = path.with_suffix(path.suffix + ".part")
            tmp.write_bytes(data)
            tmp.replace(path)
        paths.append(path)
    return paths


def _download(url: str, *, retries: int, opener) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    delay = 10.0
    for attempt in range(retries + 1):
        try:
            with opener(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == retries:
                raise
            time.sleep(delay)
            delay *= 2
    raise AssertionError("unreachable")


def decode(path: Path, *, ffmpeg: str = "ffmpeg") -> np.ndarray:
    """Decode any audio file to 48 kHz mono float32, in memory, via a pipe."""
    command = [ffmpeg, "-nostdin", "-v", "error", "-i", str(path),
               "-f", "f32le", "-acodec", "pcm_f32le", "-ac", "1", "-ar", str(SAMPLE_RATE), "pipe:1"]
    try:
        result = subprocess.run(command, capture_output=True, check=True, timeout=120)
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg is required to decode the corpus: sudo apt install ffmpeg") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"ffmpeg failed on {path.name}: {exc.stderr.decode(errors='replace')}") from exc
    return np.frombuffer(result.stdout, dtype="<f4").copy()


def windows(samples: np.ndarray) -> Iterator[np.ndarray]:
    """Consecutive, non-overlapping 3 s windows; the tail is padded or dropped."""
    for start in range(0, samples.size, WINDOW_SAMPLES):
        piece = samples[start:start + WINDOW_SAMPLES]
        if piece.size < WINDOW_SAMPLES:
            if piece.size < MIN_TAIL_SAMPLES:
                return
            piece = np.pad(piece, (0, WINDOW_SAMPLES - piece.size))
        yield piece
