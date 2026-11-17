"""Audio recognition in bytes, files and payloads; synthetic data only."""

import base64
import json
import os
import time

import pytest

from txori_kantua.privacy.audit import synthetic_wav
from txori_kantua.privacy.detect import inspect_payload, scan_tree, sniff, sniff_file

WAV = synthetic_wav()


@pytest.mark.parametrize("header, kind", [
    (WAV[:16], "WAV"),
    (b"RF64\xff\xff\xff\xffWAVEds64", "WAV"),
    (b"FORM\x00\x00\x00\x00AIFFCOMM", "AIFF"),
    (b"fLaC\x00\x00\x00\x22", "FLAC"),
    (b"OggS\x00\x02\x00\x00", "Ogg (Vorbis/Opus/FLAC)"),
    (b"ID3\x04\x00\x00\x00\x00", "MP3 (ID3 tag)"),
    (b"\xff\xfb\x90\x64\x00\x00", "MPEG audio frame (MP3/AAC)"),
    (b"\xff\xf1\x50\x80\x00\x1f", "MPEG audio frame (MP3/AAC)"),
    (b"\x00\x00\x00\x20ftypM4A ", "MP4/M4A container"),
    (b"\x1aE\xdf\xa3\x01\x00\x00\x00", "Matroska/WebM"),
    (b"\x93NUMPY\x01\x00v\x00", "NumPy array"),
    (b"caff\x00\x01\x00\x00", "CAF"),
    (b".snd\x00\x00\x00\x18", "AU"),
    (b"#!AMR\n", "AMR"),
])
def test_known_containers_are_recognised(header, kind):
    assert sniff(header) == kind


@pytest.mark.parametrize("header", [
    b"", b"RIFF", b"RIFF\x00\x00\x00\x00AVI LIST", b'{"schema_version"',
    b"\x89PNG\r\n\x1a\n", b"SQLite format 3\x00", b"\xff\xff\xff\xff\xff\xff",
    b"\xff\xfb\xf0\x00",  # MPEG sync with an invalid bitrate index
])
def test_other_content_is_not_audio(header):
    assert sniff(header) is None


def test_file_found_by_content_despite_neutral_extension(tmp_path):
    hidden = tmp_path / "cache.bin"
    hidden.write_bytes(WAV)
    assert sniff_file(hidden) == "WAV"


def test_headerless_raw_pcm_found_by_extension(tmp_path):
    raw = tmp_path / "window.pcm"
    raw.write_bytes(bytes(9600))
    assert sniff_file(raw) == "audio extension .pcm"


def test_scan_tree_reports_audio_and_new_files(tmp_path):
    (tmp_path / "notes.txt").write_text("no audio here")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    (nested / "dump.dat").write_bytes(WAV)
    old = tmp_path / "old.txt"
    old.write_text("old")
    past = time.time() - 3600
    os.utime(old, (past, past))

    scan = scan_tree([tmp_path], newer_than=time.time() - 60)

    assert [f.location for f in scan.findings] == [str(nested / "dump.dat")]
    assert str(old) not in scan.new_files
    assert str(nested / "dump.dat") in scan.new_files
    assert scan.files_checked == 3


def test_scan_tree_does_not_follow_symlinks(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "x.wav").write_bytes(WAV)
    inside = tmp_path / "inside"
    inside.mkdir()
    (inside / "link.wav").symlink_to(outside / "x.wav")
    assert scan_tree([inside]).findings == []


def test_allowed_corpus_is_not_reported(tmp_path):
    import hashlib

    corpus = tmp_path / "corpus.wav"
    corpus.write_bytes(WAV)
    allowed = frozenset({hashlib.sha256(WAV).hexdigest()})
    assert scan_tree([tmp_path], allowed_sha256=allowed).findings == []


def test_missing_root_is_ignored(tmp_path):
    assert scan_tree([tmp_path / "missing"]).files_checked == 0


def _detection(**extra):
    event = {
        "schema_version": "1.0",
        "event_id": "a0a74d86-74b8-4a0c-a2b7-0b0d880766a4",
        "station_id": "station-01",
        "observed_at": "2026-11-17T09:00:00Z",
        "window_end": "2026-11-17T09:00:03Z",
        "species": {"scientific_name": "Turdus merula", "taxon_key": "eurbla"},
        "confidence": 0.87,
        "model": {"name": "BirdNET", "version": "2.4-fp32"},
    }
    event.update(extra)
    return json.dumps(event)


def test_valid_contract_examples_are_clean():
    from pathlib import Path

    examples = Path(__file__).resolve().parents[2] / "contracts" / "examples" / "valid"
    for path in examples.glob("*.json"):
        assert inspect_payload(path.read_bytes(), location=path.name) == [], path.name


@pytest.mark.parametrize("extra, reason", [
    ({"note": base64.b64encode(WAV).decode()}, "base64-encoded WAV"),
    ({"note": base64.urlsafe_b64encode(WAV).decode().rstrip("=")}, "base64-encoded WAV"),
    ({"note": "data:audio/wav;base64,AAAA"}, "data: URI"),
    ({"source": "/var/lib/txori-kantua/window-0001.wav"}, "audio file"),
    ({"samples": [0.0] * 4}, "suspicious key"),
    ({"x": [0.01] * 300}, "numeric array"),
    ({"x": "A" * 5000}, "opaque base64"),
])
def test_audio_smuggled_into_a_payload_is_found(extra, reason):
    findings = inspect_payload(_detection(**extra))
    assert findings and reason in findings[0].reason


def test_binary_payloads_are_reported():
    assert "WAV" in inspect_payload(WAV)[0].reason
    assert "non-text" in inspect_payload(bytes(range(128, 256)))[0].reason


def test_location_points_to_the_field():
    findings = inspect_payload(_detection(species={"scientific_name": "Turdus merula",
                                                   "audio": "x"}), location="msg")
    assert findings[0].location == "msg.species.audio"
