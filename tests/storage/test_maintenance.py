"""Backup, verification and restore tooling (issues #19, #29)."""
import json
import sqlite3
from datetime import datetime, timezone

import pytest
from txori_kantua import maintenance
from txori_kantua.maintenance import BackupError, counts, create_backup, restore_backup, verify_backup
from txori_kantua.messaging.events import new_detection, stable_event_id
from txori_kantua.storage import Store


def detection(i):
    """Same i, same event: the identifier is stable so a resend is a real duplicate."""
    return new_detection(station_id='station-01', scientific_name='Turdus merula', confidence=.8,
                         observed_at=f'2026-11-17T10:00:{i:02d}Z', window_end=f'2026-11-17T10:00:{i + 3:02d}Z',
                         model_name='BirdNET', model_version='synthetic-test',
                         event_id=stable_event_id('test-detection', i))


@pytest.fixture
def db(tmp_path):
    path = tmp_path / 'data' / 'events.sqlite'
    path.parent.mkdir()
    store = Store(path)
    for i in range(5):
        store.insert('detection', detection(i))
    store.close()
    return path


def test_hot_backup_while_the_writer_is_open(db, tmp_path):
    writer = Store(db)  # ingest still running
    try:
        backup = create_backup(db, tmp_path / 'backups')
        writer.insert('detection', detection(30))
    finally:
        writer.close()
    assert verify_backup(backup)['events'] == 5
    assert counts(db)['events'] == 6


def test_restore_recovers_the_controlled_copy_and_keeps_the_old_database(db, tmp_path):
    backup = create_backup(db, tmp_path / 'backups')
    store = Store(db)
    store.insert('detection', detection(40))
    store.close()
    with pytest.raises(FileExistsError):
        restore_backup(backup, db)
    assert counts(db)['events'] == 6
    assert restore_backup(backup, db, force=True)['events'] == 5
    assert (db.parent / 'events.sqlite.before-restore').is_file(), 'previous database moved aside'
    store = Store(db)  # writable again and still deduplicating
    assert store.insert('detection', detection(0)) is False
    store.close()


def test_restore_after_losing_the_database(db, tmp_path):
    backup = create_backup(db, tmp_path / 'backups')
    db.unlink()
    for suffix in ('-wal', '-shm'):
        db.with_name(db.name + suffix).unlink(missing_ok=True)
    assert restore_backup(backup, db)['events'] == 5


def test_a_corrupt_or_foreign_file_is_never_restored(db, tmp_path):
    corrupt = tmp_path / 'corrupt.sqlite'
    corrupt.write_bytes(b'not a database' * 100)
    foreign = tmp_path / 'foreign.sqlite'
    sqlite3.connect(foreign).executescript('CREATE TABLE other (x);')
    for bad in (corrupt, foreign, tmp_path / 'missing.sqlite'):
        with pytest.raises(BackupError):
            restore_backup(bad, db, force=True)
    assert counts(db)['events'] == 5, 'the live database is untouched'


def test_rotation_keeps_the_most_recent_backups(db, tmp_path):
    directory = tmp_path / 'backups'
    for day in range(1, 11):
        create_backup(db, directory, keep=7, now=datetime(2026, 11, day, tzinfo=timezone.utc))
    names = sorted(p.name for p in directory.iterdir())
    assert len(names) == 7 and names[0] == 'txori-20261104T000000Z.sqlite'
    with pytest.raises(FileExistsError):
        create_backup(db, directory, now=datetime(2026, 11, 10, tzinfo=timezone.utc))


def test_backup_of_a_missing_database_fails_cleanly(tmp_path):
    with pytest.raises(BackupError):
        create_backup(tmp_path / 'absent.sqlite', tmp_path / 'backups')
    assert not list((tmp_path / 'backups').glob('*'))


def test_cli_backup_verify_restore_stats(db, tmp_path, capsys):
    assert maintenance.main(['backup', '--db', str(db), '--dir', str(tmp_path / 'b')]) == 0
    backup = json.loads(capsys.readouterr().out)['backup']
    assert maintenance.main(['verify', backup]) == 0
    assert json.loads(capsys.readouterr().out)['counts']['events'] == 5
    assert maintenance.main(['restore', backup, '--db', str(db)]) == 1, 'refuses without --force'
    assert 'error' in capsys.readouterr().err
    assert maintenance.main(['restore', backup, '--db', str(db), '--force']) == 0
    capsys.readouterr()
    assert maintenance.main(['stats', '--db', str(db)]) == 0
    assert json.loads(capsys.readouterr().out)['counts'] == {'events': 5, 'daily_summaries': 0,
                                                              'availability_transitions': 0}
