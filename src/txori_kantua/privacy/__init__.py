"""Audio privacy safeguards and audit (issue #11).

``detect``
    Recognise audio in files and message payloads.
``system``
    Read-only checks of swap, core dumps and temporary storage.
``log_guard``
    Logging filter that keeps buffers out of log records.
``audit``
    Command line: ``python -m txori_kantua.privacy.audit --help``.
"""

from .detect import Finding, inspect_payload, scan_tree, sniff, sniff_file
from .log_guard import AudioLogFilter, install as install_log_guard
from .system import Check, Status, run_checks

__all__ = [
    "AudioLogFilter",
    "Check",
    "Finding",
    "Status",
    "inspect_payload",
    "install_log_guard",
    "run_checks",
    "scan_tree",
    "sniff",
    "sniff_file",
]
