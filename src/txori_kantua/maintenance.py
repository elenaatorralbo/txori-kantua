"""Backup, verification and restore of the event database (issues #19, #29).

Command line::

    txori-storage backup  [--db PATH] --dir DIRECTORY [--keep 7]
    txori-storage verify  BACKUP
    txori-storage restore BACKUP [--db PATH] [--force]
    txori-storage stats   [--db PATH]

``backup`` can run while ingest is running: it opens its own read-only
connection and ``VACUUM INTO`` reads a consistent snapshot. ``restore``
**requires ingest and the API to be stopped**, because it replaces the file.

The database only holds metadata (``storage.SCHEMA``); a backup never contains
audio or credentials.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .storage import Store

__all__ = ["DEFAULT_DATABASE", "create_backup", "verify_backup", "restore_backup", "rotate_backups",
           "counts", "main"]

DEFAULT_DATABASE = "/var/lib/txori-kantua/events.sqlite"
BACKUP_PREFIX = "txori-"
BACKUP_SUFFIX = ".sqlite"
#: Tables whose row counts must survive a backup/restore round trip.
TABLES = ("events", "daily_summaries", "availability_transitions")


class BackupError(Exception):
    """A backup cannot be created, verified or restored."""


def _readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=30)


def counts(path: str | Path) -> dict[str, int]:
    """Row count per table, read-only."""
    path = Path(path)
    if not path.is_file():
        raise BackupError(f"database {path} does not exist")
    # closing(): a sqlite3 connection used as a context manager commits but does not close.
    with closing(_readonly(path)) as conn:
        return {table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in TABLES}


def verify_backup(path: str | Path) -> dict[str, int]:
    """Check that a backup is a sound Txori Kantua database and return its row counts."""
    path = Path(path)
    if not path.is_file():
        raise BackupError(f"backup {path} does not exist")
    try:
        conn = _readonly(path)
        try:
            result = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if result != "ok":
                raise BackupError(f"backup {path} fails integrity_check: {result}")
            names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            missing = [t for t in TABLES if t not in names]
            if missing:
                raise BackupError(f"backup {path} is not an event database (missing {', '.join(missing)})")
            return {table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in TABLES}
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise BackupError(f"backup {path} is not a readable database: {exc}") from exc


def rotate_backups(directory: str | Path, *, keep: int) -> list[Path]:
    """Delete the oldest backups, keeping ``keep``. Returns the deleted paths."""
    if keep < 1:
        raise ValueError("keep must be at least 1")
    backups = sorted(Path(directory).glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}"))
    removed = backups[:-keep]
    for path in removed:
        path.unlink()
    return removed


def create_backup(db_path: str | Path, directory: str | Path, *, keep: int = 7,
                  now: datetime | None = None) -> Path:
    """Consistent hot backup, verified before rotating old ones.

    A faulty backup is deleted and never displaces a good one.
    """
    db_path, directory = Path(db_path), Path(directory)
    if not db_path.is_file():
        raise BackupError(f"database {db_path} does not exist")
    directory.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    destination = directory / f"{BACKUP_PREFIX}{stamp}{BACKUP_SUFFIX}"
    if destination.exists():
        raise FileExistsError(f"{destination} already exists")
    try:
        with closing(_readonly(db_path)) as conn:
            conn.execute("VACUUM INTO ?", (str(destination),))
    except sqlite3.Error as exc:
        destination.unlink(missing_ok=True)
        raise BackupError(f"could not create the backup: {exc}") from exc
    try:
        verify_backup(destination)
    except BackupError:
        destination.unlink(missing_ok=True)
        raise
    rotate_backups(directory, keep=keep)
    return destination


def restore_backup(backup: str | Path, db_path: str | Path, *, force: bool = False) -> dict[str, int]:
    """Replace the database with a verified backup. **Ingest and API must be stopped.**

    The current database is moved aside as ``<name>.before-restore``, never
    deleted, so the restore can be undone.
    """
    backup, db_path = Path(backup), Path(db_path)
    expected = verify_backup(backup)
    if db_path.exists():
        if not force:
            raise FileExistsError(f"{db_path} already exists: use --force to replace it")
        aside = db_path.with_name(db_path.name + ".before-restore")
        aside.unlink(missing_ok=True)
        os.replace(db_path, aside)
    # WAL files belong to the previous database; SQLite would replay them on the copy.
    for suffix in ("-wal", "-shm"):
        db_path.with_name(db_path.name + suffix).unlink(missing_ok=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = db_path.with_name(db_path.name + ".restoring")
    shutil.copyfile(backup, temporary)
    os.replace(temporary, db_path)
    # Opening it as the writer would leaves it in WAL mode and proves it is usable.
    Store(db_path).close()
    restored = counts(db_path)
    if restored != expected:
        raise BackupError(f"restored database does not match the backup: {restored} != {expected}")
    return restored


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="txori-storage", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    default_db = os.environ.get("TXORI_DATABASE", DEFAULT_DATABASE)

    p = sub.add_parser("backup", help="consistent hot backup with rotation")
    p.add_argument("--db", default=default_db)
    p.add_argument("--dir", required=True)
    p.add_argument("--keep", type=int, default=7)
    p = sub.add_parser("verify", help="check the integrity of a backup")
    p.add_argument("backup")
    p = sub.add_parser("restore", help="replace the database with a backup (ingest and API stopped)")
    p.add_argument("backup")
    p.add_argument("--db", default=default_db)
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("stats", help="row count per table")
    p.add_argument("--db", default=default_db)

    args = parser.parse_args(argv)
    try:
        if args.command == "backup":
            path = create_backup(args.db, args.dir, keep=args.keep)
            print(json.dumps({"backup": str(path), "counts": verify_backup(path)}))
        elif args.command == "verify":
            print(json.dumps({"backup": args.backup, "integrity": "ok", "counts": verify_backup(args.backup)}))
        elif args.command == "restore":
            print(json.dumps({"restored": args.db, "counts": restore_backup(args.backup, args.db, force=args.force)}))
        else:
            print(json.dumps({"db": args.db, "counts": counts(args.db)}))
    except (BackupError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
