"""Thin BirdNET V2.4 wrapper over a TFLite interpreter (issue #8).

Only what the station needs: one 3 s window of 48 kHz mono float32 audio in,
scores for the 6 522 BirdNET classes out. The window is an in-memory array
(ADR 0006); nothing here reads or writes audio files.

The model files come from the official BirdNET V2.4 release on Zenodo
(https://doi.org/10.5281/zenodo.15050749, CC BY-NC 4.0). They are not stored
in the repository; see docs/birdnet-feasibility.md.

Runtime: ``ai-edge-litert`` (Google's successor of ``tflite-runtime``), which
publishes aarch64 wheels for Python 3.13, the Python of Raspberry Pi OS
Trixie. ``tflite-runtime`` (≤ Python 3.11) and full TensorFlow are accepted
as fallbacks so the same code runs wherever one of them is installed.
"""

from __future__ import annotations

import hashlib
import importlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

SAMPLE_RATE = 48_000
WINDOW_SECONDS = 3.0
WINDOW_SAMPLES = 144_000
MODEL_NAME = "BirdNET"

#: Classes that reveal people. They are never published (privacy.md) and are
#: only used to screen an evaluation corpus for voices.
HUMAN_LABELS = frozenset({"Human vocal", "Human non-vocal", "Human whistle"})

_RUNTIMES = (
    ("ai-edge-litert", "ai_edge_litert.interpreter", "Interpreter"),
    ("tflite-runtime", "tflite_runtime.interpreter", "Interpreter"),
    ("tensorflow", "tensorflow.lite", "Interpreter"),
)


@dataclass(frozen=True)
class Label:
    scientific_name: str
    common_name: str

    @property
    def is_species(self) -> bool:
        """BirdNET's non-species classes repeat their name ("Dog_Dog")."""
        return self.scientific_name != self.common_name


@dataclass(frozen=True)
class Candidate:
    index: int
    scientific_name: str
    common_name: str
    confidence: float


def load_labels(path: Path | str) -> list[Label]:
    """Parse a BirdNET labels file: ``Scientific name_Common name`` per line."""
    labels = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        scientific, _, common = line.partition("_")
        labels.append(Label(scientific.strip(), (common or scientific).strip()))
    return labels


def flat_sigmoid(logits: np.ndarray, sensitivity: float = 1.0) -> np.ndarray:
    """BirdNET's score: a sigmoid over logits clipped to ±15.

    ``sensitivity`` (BirdNET's 0.5–1.5 range) steepens or flattens the curve.
    The result is a model score, not a calibrated probability.
    """
    if not 0.5 <= sensitivity <= 1.5:
        raise ValueError("sensitivity must be between 0.5 and 1.5")
    clipped = np.clip(logits.astype(np.float64), -15.0, 15.0)
    return (1.0 / (1.0 + np.exp(-sensitivity * clipped))).astype(np.float32)


def pcm16_to_float32(buffer: bytes | bytearray | memoryview) -> np.ndarray:
    """Convert little-endian 16-bit PCM (what ``arecord`` produces) to [-1, 1)."""
    return np.frombuffer(buffer, dtype="<i2").astype(np.float32) / 32768.0


def model_precision(path: Path | str) -> str:
    name = Path(path).stem.lower()
    for precision in ("int8", "fp16"):
        if precision in name:
            return precision
    return "fp32"


def load_interpreter(model_path: Path | str, num_threads: int | None = None) -> tuple[Any, str, str]:
    """Return ``(interpreter, runtime name, runtime version)`` for the first runtime found."""
    errors = []
    for name, module_name, attribute in _RUNTIMES:
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            errors.append(f"{name}: {exc}")
            continue
        interpreter = getattr(module, attribute)(model_path=str(model_path), num_threads=num_threads)
        return interpreter, name, _version(name)
    raise ImportError("no TFLite runtime available; install ai-edge-litert. " + "; ".join(errors))


def _version(distribution: str) -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version(distribution)
    except PackageNotFoundError:
        return "unknown"


def file_sha256(path: Path | str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class BirdNet:
    """One loaded model. Not thread-safe: use one instance per worker."""

    def __init__(
        self,
        model_path: Path | str,
        labels: Sequence[Label],
        *,
        num_threads: int | None = None,
        sensitivity: float = 1.0,
        interpreter: Any | None = None,
        runtime: tuple[str, str] = ("injected", "n/a"),
    ) -> None:
        self.model_path = Path(model_path)
        self.labels = list(labels)
        self.sensitivity = sensitivity
        flat_sigmoid(np.zeros(1), sensitivity)  # validates the range
        if interpreter is None:
            interpreter, *runtime = load_interpreter(self.model_path, num_threads)
        self.runtime_name, self.runtime_version = runtime
        self.num_threads = num_threads
        self._interpreter = interpreter
        interpreter.allocate_tensors()
        (inp,) = interpreter.get_input_details()
        (out,) = interpreter.get_output_details()
        if list(inp["shape"]) != [1, WINDOW_SAMPLES] or inp["dtype"] is not np.float32:
            raise ValueError(f"unexpected model input {list(inp['shape'])} {inp['dtype']}")
        if list(out["shape"]) != [1, len(self.labels)]:
            raise ValueError(f"model has {out['shape'][-1]} outputs but {len(self.labels)} labels")
        self._input = inp["index"]
        self._output = out["index"]
        self._window = np.zeros((1, WINDOW_SAMPLES), dtype=np.float32)  # reused input buffer

    @property
    def precision(self) -> str:
        return model_precision(self.model_path)

    def version(self, sha256: str | None = None) -> str:
        """Value for ``model.version`` in the detection contract (≤ 64 chars)."""
        digest = (sha256 or file_sha256(self.model_path))[:12]
        return f"GLOBAL_6K_V2.4-{self.precision}+sha256.{digest}"

    def predict(self, window: np.ndarray) -> np.ndarray:
        """Scores in [0, 1] for every label. Shorter windows are zero-padded."""
        samples = np.asarray(window, dtype=np.float32).reshape(-1)
        if samples.size > WINDOW_SAMPLES:
            raise ValueError(f"window has {samples.size} samples; at most {WINDOW_SAMPLES}")
        self._window[0, : samples.size] = samples
        self._window[0, samples.size:] = 0.0
        try:
            self._interpreter.set_tensor(self._input, self._window)
            self._interpreter.invoke()
            logits = self._interpreter.get_tensor(self._output)[0]
            if not np.isfinite(logits).all():
                raise ValueError("model returned non-finite scores")
            return flat_sigmoid(logits, self.sensitivity)
        finally:
            self._window.fill(0.0)
            # Clear the interpreter input even when invocation failed.
            self._interpreter.set_tensor(self._input, self._window)

    def top(self, scores: np.ndarray, *, k: int = 5, min_confidence: float = 0.0,
            species_only: bool = True) -> list[Candidate]:
        """Best ``k`` classes at or above ``min_confidence``, highest first."""
        order = np.argsort(scores)[::-1]
        found = []
        for index in order:
            score = float(scores[index])
            if score < min_confidence or len(found) == k:
                break
            label = self.labels[index]
            if species_only and not label.is_species:
                continue
            found.append(Candidate(int(index), label.scientific_name, label.common_name, score))
        return found

    def score_of(self, scores: np.ndarray, names: frozenset[str]) -> float:
        """Highest score among classes whose scientific name is in ``names``."""
        values = [float(scores[i]) for i, label in enumerate(self.labels) if label.scientific_name in names]
        return max(values, default=0.0)
