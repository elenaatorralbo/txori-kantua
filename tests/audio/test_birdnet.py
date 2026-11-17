"""BirdNET wrapper with a fake interpreter; the real model is opt-in.

Set TXORI_BIRDNET_MODEL_DIR to a directory with ``audio-model*.tflite`` and
``labels/en_us.txt`` (docs/birdnet-feasibility.md) to also run the tests
marked ``model``.
"""

import os
from pathlib import Path

import numpy as np
import pytest

from txori_kantua.audio.birdnet import (
    HUMAN_LABELS,
    WINDOW_SAMPLES,
    BirdNet,
    Label,
    flat_sigmoid,
    load_labels,
    model_precision,
    pcm16_to_float32,
)

LABELS = [
    Label("Turdus merula", "Eurasian Blackbird"),
    Label("Erithacus rubecula", "European Robin"),
    Label("Human vocal", "Human vocal"),
    Label("Dog", "Dog"),
]


class FakeInterpreter:
    """Logits chosen by the test; records what the model was given."""

    def __init__(self, logits, outputs=len(LABELS), shape=(1, WINDOW_SAMPLES)):
        self.logits = np.asarray(logits, dtype=np.float32)
        self.outputs = outputs
        self.shape = shape
        self.received = None

    def allocate_tensors(self):
        pass

    def get_input_details(self):
        return [{"index": 0, "shape": np.array(self.shape), "dtype": np.float32}]

    def get_output_details(self):
        return [{"index": 1, "shape": np.array([1, self.outputs]), "dtype": np.float32}]

    def set_tensor(self, index, value):
        self.received = value.copy()

    def invoke(self):
        self.invoked_with = self.received.copy()

    def get_tensor(self, index):
        return self.logits[None]


def model(logits=(0, 0, 0, 0), **kwargs):
    return BirdNet("audio-model-int8.tflite", LABELS, interpreter=FakeInterpreter(logits, **kwargs))


def test_load_labels(tmp_path):
    path = tmp_path / "en_us.txt"
    path.write_text("Turdus merula_Eurasian Blackbird\nHuman vocal_Human vocal\n\n")
    labels = load_labels(path)
    assert labels == [Label("Turdus merula", "Eurasian Blackbird"), Label("Human vocal", "Human vocal")]
    assert labels[0].is_species and not labels[1].is_species


def test_flat_sigmoid_matches_birdnet():
    scores = flat_sigmoid(np.array([0.0, 2.0, -2.0, 100.0, -100.0]))
    assert scores[0] == pytest.approx(0.5)
    assert scores[1] == pytest.approx(1 / (1 + np.exp(-2)))
    assert scores[3] == pytest.approx(1 / (1 + np.exp(-15)))  # clipped at 15
    assert scores[4] == pytest.approx(1 / (1 + np.exp(15)))
    steeper = flat_sigmoid(np.array([2.0]), sensitivity=1.5)
    assert steeper[0] > scores[1]


@pytest.mark.parametrize("sensitivity", [0.4, 1.6])
def test_sensitivity_range(sensitivity):
    with pytest.raises(ValueError):
        flat_sigmoid(np.zeros(1), sensitivity)


def test_pcm16_conversion():
    pcm = np.array([0, 16384, -32768, 32767], dtype="<i2").tobytes()
    assert pcm16_to_float32(pcm).tolist() == pytest.approx([0.0, 0.5, -1.0, 32767 / 32768])


@pytest.mark.parametrize("name, precision", [
    ("audio-model.tflite", "fp32"), ("audio-model-fp16.tflite", "fp16"), ("audio-model-int8.tflite", "int8")])
def test_precision_from_file_name(name, precision):
    assert model_precision(name) == precision


def test_short_window_is_zero_padded_and_input_buffer_cleared():
    m = model()
    m.predict(np.ones(1000, dtype=np.float32))
    received = m._interpreter.invoked_with
    assert received.shape == (1, WINDOW_SAMPLES)
    assert received[0, :1000].sum() == 1000 and received[0, 1000:].sum() == 0
    assert not m._window.any()  # nothing of the window is kept after inference
    assert not m._interpreter.received.any()


def test_long_window_is_rejected():
    with pytest.raises(ValueError):
        model().predict(np.zeros(WINDOW_SAMPLES + 1, dtype=np.float32))


def test_top_skips_non_species_and_respects_threshold():
    m = model(logits=[1.0, 3.0, 9.0, 8.0])
    scores = m.predict(np.zeros(WINDOW_SAMPLES, dtype=np.float32))
    top = m.top(scores, k=5, min_confidence=0.6)
    assert [c.scientific_name for c in top] == ["Erithacus rubecula", "Turdus merula"]
    assert top[0].confidence == pytest.approx(1 / (1 + np.exp(-3)))
    assert [c.scientific_name for c in m.top(scores, k=1, species_only=False)] == ["Human vocal"]
    assert m.score_of(scores, HUMAN_LABELS) == pytest.approx(1 / (1 + np.exp(-9)))


def test_mismatched_labels_or_input_are_rejected():
    with pytest.raises(ValueError, match="outputs"):
        model(outputs=6522)
    with pytest.raises(ValueError, match="input"):
        model(shape=(1, 48000))


def test_version_fits_the_detection_contract(tmp_path):
    from txori_kantua.messaging import new_detection

    m = model()
    version = m.version("ab" * 32)
    assert version == "GLOBAL_6K_V2.4-int8+sha256.abababababab"
    new_detection(station_id="station-01", scientific_name="Turdus merula", confidence=0.9,
                  observed_at="2026-11-17T09:00:00Z", window_end="2026-11-17T09:00:03Z",
                  model_name="BirdNET", model_version=version)


MODEL_DIR = os.environ.get("TXORI_BIRDNET_MODEL_DIR")


@pytest.mark.model
@pytest.mark.skipif(not MODEL_DIR, reason="TXORI_BIRDNET_MODEL_DIR not set")
@pytest.mark.parametrize("model_file", sorted(Path(MODEL_DIR or ".").rglob("audio-model*.tflite")),
                         ids=lambda p: p.name)
def test_real_model_loads_and_scores_a_tone(model_file):
    labels = load_labels(model_file.parent / "labels" / "en_us.txt")
    birdnet = BirdNet(model_file, labels, num_threads=1)
    t = np.arange(WINDOW_SAMPLES) / 48000
    scores = birdnet.predict((0.1 * np.sin(2 * np.pi * 3000 * t)).astype(np.float32))
    assert scores.shape == (len(labels),) and 0 <= scores.min() and scores.max() <= 1
    assert len(birdnet.version()) <= 64


def test_failed_inference_clears_both_input_buffers():
    m = model()
    def fail():
        raise RuntimeError("model invocation failed")
    m._interpreter.invoke = fail
    with pytest.raises(RuntimeError, match="invocation"):
        m.predict(np.ones(1000, dtype=np.float32))
    assert not m._window.any()
    assert not m._interpreter.received.any()
