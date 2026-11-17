"""Audit command line, including the control self-test of issue #11."""

import io
import json
import sys

from txori_kantua.privacy.audit import control_payload, main, synthetic_wav


def test_control_self_test_detects_and_cleans_up(tmp_path, capsys):
    assert main(["control", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "**NO**" not in output
    assert list(tmp_path.iterdir()) == []


def test_control_payload_is_otherwise_a_detection():
    event = json.loads(control_payload())
    assert event["species"]["scientific_name"] == "Turdus merula"
    assert "clip" in event


def test_files_exit_code(tmp_path, capsys):
    (tmp_path / "ok.txt").write_text("metadata only")
    assert main(["files", str(tmp_path)]) == 0
    (tmp_path / "leak.tmp").write_bytes(synthetic_wav())
    assert main(["files", str(tmp_path)]) == 1
    assert "leak.tmp" in capsys.readouterr().out


def test_files_lists_new_files_since_marker(tmp_path, capsys):
    marker = tmp_path / "marker"
    marker.write_text("")
    (tmp_path / "created.txt").write_text("x")
    main(["files", "--since", str(marker), str(tmp_path)])
    assert "created.txt" in capsys.readouterr().out


def test_files_allow_manifest(tmp_path):
    import hashlib

    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "XC1.wav").write_bytes(synthetic_wav())
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"recordings": [
        {"sha256": hashlib.sha256(synthetic_wav()).hexdigest()}]}))
    assert main(["files", "--allow-manifest", str(manifest), str(corpus)]) == 0


def test_payloads_from_mosquitto_sub(monkeypatch, capsys):
    lines = (
        b"txori/v1/station-01/detections " + json.dumps({"confidence": 0.5}).encode() + b"\n"
        + b"txori/v1/station-01/detections " + control_payload() + b"\n"
    )
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(lines)))
    assert main(["payloads", "--mqtt"]) == 1
    output = capsys.readouterr().out
    assert "txori/v1/station-01/detections (line 2)" in output
    # The smuggled field is reported twice: by its name and by its content.
    assert "line 2).clip`: base64-encoded WAV" in output
    assert "Payloads inspected: 2; findings: 2." in output


def test_system_runs_on_a_fake_root(tmp_path, capsys):
    (tmp_path / "proc").mkdir()
    (tmp_path / "proc" / "swaps").write_text("Filename Type Size Used Priority\n/swapfile file 1 0 -2\n")
    assert main(["system", "--root", str(tmp_path)]) == 1
    assert "/swapfile" in capsys.readouterr().out
