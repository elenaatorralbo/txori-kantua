import json
import sqlite3
from datetime import date, datetime, timezone

import pytest
from txori_kantua.storage import Store, connect_reader
from txori_kantua.messaging.events import new_detection, new_environment, reading


def detection(**kw):
    args=dict(station_id='station-01',scientific_name='Turdus merula',confidence=.8,
              observed_at='2026-11-17T10:00:00Z',window_end='2026-11-17T10:00:03Z',
              model_name='BirdNET',model_version='synthetic-test')
    args.update(kw)
    return new_detection(**args)


def test_duplicate_restart_backup_restore(tmp_path):
    path=tmp_path/'db.sqlite'; store=Store(path); event=detection()
    assert [store.insert('detection',event) for _ in range(3)] == [True,False,False]
    before=store.db.execute('SELECT received_at_ms FROM events').fetchone()[0]
    store.close(); store=Store(path)
    assert not store.insert('detection',event)
    assert store.db.execute('SELECT received_at_ms FROM events').fetchone()[0] == before
    backup=tmp_path/'backup.sqlite'; store.backup(backup); store.close()
    restored=Store(backup)
    assert restored.db.execute('SELECT count(*) FROM detections').fetchone()[0] == 1
    assert restored.db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    restored.close()
    db=connect_reader(path)
    with pytest.raises(sqlite3.OperationalError):
        db.execute('DELETE FROM events')
    db.close()


def test_invalid_and_collision_leave_original_intact(tmp_path):
    store=Store(tmp_path/'db'); event=detection(); store.insert('detection',event)
    with pytest.raises(ValueError):
        store.insert('detection',dict(event,confidence=.9))
    from txori_kantua.messaging.errors import MessagingError
    with pytest.raises(MessagingError):
        store.ingest('txori/v1/station-01/detections',b'{"audio":"private"}')
    assert store.db.execute('SELECT count(*) FROM events').fetchone()[0] == 1
    store.close()


def test_retention_defers_until_projection_and_preserves_summary(tmp_path):
    store=Store(tmp_path/'db')
    event=new_environment(station_id='station-01',observed_at='2026-01-10T10:00:00Z',
                          readings={'temperature':reading(12,'degC')})
    store.insert('environment',event)
    now=datetime(2026,11,17,tzinfo=timezone.utc)
    assert store.purge(now=now) == {'deleted':0,'deferred':1}
    store.project_day('station-01',date(2026,1,10))
    assert store.purge(now=now) == {'deleted':1,'deferred':0}
    saved=json.loads(store.db.execute('SELECT payload FROM daily_summaries').fetchone()[0])
    assert saved['environment']['temperature']['mean']==12
    store.close()


def test_late_observation_cannot_destroy_archived_daily_projection(tmp_path):
    store=Store(tmp_path/'db')
    event=new_environment(station_id='station-01',observed_at='2026-01-10T10:00:00Z',
                          readings={'temperature':reading(12,'degC')})
    store.insert('environment',event)
    store.maintain(now=datetime(2026,11,17,tzinfo=timezone.utc))
    original=store.db.execute('SELECT payload FROM daily_summaries').fetchone()[0]
    late=new_environment(station_id='station-01',observed_at=event['observed_at'],
                         readings={'temperature':reading(30,'degC')})
    with pytest.raises(ValueError,match='archived'): store.insert('environment',late)
    store.project_day('station-01',date(2026,1,10))
    assert store.db.execute('SELECT payload FROM daily_summaries').fetchone()[0]==original
    store.close()
