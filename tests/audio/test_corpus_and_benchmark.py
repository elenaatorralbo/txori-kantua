"""Corpus manifest, windowing, download checks and benchmark bookkeeping."""

import hashlib
import io
import json
import urllib.error
from pathlib import Path

import numpy as np
import pytest

from txori_kantua.audio import corpus
from txori_kantua.audio.benchmark import Budget, ConfigResult, percentile, run_config
from txori_kantua.audio.birdnet import WINDOW_SAMPLES, BirdNet, Label

REPO = Path(__file__).resolve().parents[2]


def test_manifest_is_complete_and_licensed():
    recordings = corpus.load_manifest()
    assert len(recordings) >= 5
    for rec in recordings:
        assert rec.license.startswith("CC BY"), rec.id
        assert rec.author and rec.page_url.startswith("https://commons.wikimedia.org/")
        assert len(rec.sha256) == 64 and rec.bytes > 0
        assert rec.download_url.startswith("https://upload.wikimedia.org/")


def test_manifest_works_as_privacy_allow_list():
    from txori_kantua.privacy.audit import _allowed

    allowed = _allowed(str(corpus.MANIFEST))
    assert {r.sha256 for r in corpus.load_manifest()} == allowed


def test_windows_split_pad_and_drop_tail():
    samples = np.ones(2 * WINDOW_SAMPLES + 60_000, dtype=np.float32)
    wins = list(corpus.windows(samples))
    assert len(wins) == 3 and all(w.size == WINDOW_SAMPLES for w in wins)
    assert wins[2][:60_000].all() and not wins[2][60_000:].any()
    assert len(list(corpus.windows(np.ones(WINDOW_SAMPLES + 1000, dtype=np.float32)))) == 1


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def recording(data: bytes) -> corpus.Recording:
    return corpus.Recording("XC1", "Turdus merula", "XC1.mp3", "https://example.invalid/x", "p",
                            "a", "CC BY 4.0", "l", hashlib.sha256(data).hexdigest(), len(data))


def test_fetch_verifies_hash_and_skips_valid_files(tmp_path):
    calls = []

    def opener(request, timeout):
        calls.append(request.full_url)
        return FakeResponse(b"audio bytes")

    rec = recording(b"audio bytes")
    assert corpus.fetch([rec], tmp_path, opener=opener) == [tmp_path / "XC1.mp3"]
    corpus.fetch([rec], tmp_path, opener=opener)
    assert len(calls) == 1
    assert not list(tmp_path.glob("*.part"))


def test_fetch_rejects_tampered_download(tmp_path):
    with pytest.raises(ValueError, match="SHA-256"):
        corpus.fetch([recording(b"expected")], tmp_path, opener=lambda r, timeout: FakeResponse(b"other"))
    assert not (tmp_path / "XC1.mp3").exists()


def test_fetch_backs_off_on_rate_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(corpus.time, "sleep", lambda s: None)
    attempts = []

    def opener(request, timeout):
        attempts.append(1)
        if len(attempts) < 3:
            raise urllib.error.HTTPError(request.full_url, 429, "Too many requests", {}, None)
        return FakeResponse(b"ok")

    corpus.fetch([recording(b"ok")], tmp_path, opener=opener)
    assert len(attempts) == 3


def test_decode_reports_missing_ffmpeg(tmp_path):
    with pytest.raises(RuntimeError, match="apt install ffmpeg"):
        corpus.decode(tmp_path / "x.mp3", ffmpeg="/nonexistent/ffmpeg")


def test_percentile_and_budget():
    assert percentile([1, 2, 3, 4], 50) == 2.5
    result = ConfigResult("m", "int8", "v", 2, "rt", 0.1, 100.0, [0.2] * 19 + [1.5], 4.0, 4.0,
                          peak_rss_mb=300.0, temps_c=[60.0], throttled_after="0x0")
    assert result.p95_s == pytest.approx(0.265)
    assert Budget().check(result) == []
    assert "p95" in Budget(p95_s=0.1).check(result)[0]
    result.throttled_after = "0x50005"
    assert "throttled=0x50005" in Budget().check(result)


class EchoInterpreter:
    """Scores the species whose index equals the window's constant value."""

    def __init__(self):
        self.x = None

    def allocate_tensors(self):
        pass

    def get_input_details(self):
        return [{"index": 0, "shape": np.array([1, WINDOW_SAMPLES]), "dtype": np.float32}]

    def get_output_details(self):
        return [{"index": 1, "shape": np.array([1, 3]), "dtype": np.float32}]

    def set_tensor(self, index, value):
        self.x = value

    def invoke(self):
        pass

    def get_tensor(self, index):
        logits = np.full((1, 3), -10.0, dtype=np.float32)
        logits[0, int(round(float(self.x[0, 0])))] = 10.0
        return logits


def test_run_config_counts_windows_and_detections():
    labels = [Label("Turdus merula", "Blackbird"), Label("Parus major", "Great Tit"),
              Label("Human vocal", "Human vocal")]
    rec = recording(b"x")
    wins = [np.full(WINDOW_SAMPLES, v, dtype=np.float32) for v in (0, 0, 1, 2)]

    def factory(path, labels, num_threads=None):
        return BirdNet(path, labels, interpreter=EchoInterpreter())

    result = run_config(Path("audio-model-fp16.tflite"), labels, [(rec, wins)], threads=1,
                        warmup=1, model_factory=factory, sha256="0" * 64)
    assert len(result.latencies_s) == 4
    (summary,) = result.recordings
    assert summary.expected_top1 == 2
    assert summary.top_species[0] == ("Turdus merula", 2)
    assert summary.human_max == pytest.approx(1 / (1 + np.exp(-10)))
    assert result.precision == "fp16"
    json.dumps(result.__dict__, default=lambda o: o.__dict__)  # serialisable for --json
