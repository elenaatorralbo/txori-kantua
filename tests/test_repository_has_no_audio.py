"""The repository itself must never carry audio (docs/privacy.md, issue #11).

.gitignore already excludes common audio extensions; this test also catches
audio committed under another name, by its content.
"""

import subprocess
from pathlib import Path

import pytest

from txori_kantua.privacy.detect import sniff_file

ROOT = Path(__file__).resolve().parents[1]


def tracked_files():
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True,
                             check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return [ROOT / name for name in out.decode().split("\0") if name]


def test_no_tracked_file_is_audio():
    offenders = [str(p.relative_to(ROOT)) for p in tracked_files()
                 if p.is_file() and sniff_file(p)]
    assert offenders == []
