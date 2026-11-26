"""Synthetic PCM/model, real contracts, SQLite and display; no hardware claims."""
import json
from types import SimpleNamespace

import numpy as np
import pytest

from support.fake_broker import FakeBroker
from txori_kantua.audio.birdnet import Candidate, WINDOW_SAMPLES
from txori_kantua.audio.filtering import DetectionFilter
from txori_kantua.audio.pipeline import Inference, PublishingPipeline, Window, WindowQueue
from txori_kantua.display import DisplayController
from txori_kantua.lcd_station import DetectionDisplay
from txori_kantua.messaging.detections import DetectionPublisher
from txori_kantua.messaging.errors import MessagingError
from txori_kantua.messaging.timestamps import to_epoch_ms
from txori_kantua.storage import Store

STAMP = '2026-11-17T10:00:00Z'
TOPIC = 'txori/v1/station-01/detections'


class Model:
    def version(self): return 'synthetic-pipeline'
    def predict(self, samples): return np.array([.9])
    def top(self, scores, **kwargs):
        return [Candidate(0, 'Turdus merula', 'Blackbird', float(scores[0]))]


def engine(model=None):
    filtering = DetectionFilter(threshold=.5, region='test', revision='synthetic',
                                seasons={'test': {'11': ['Turdus merula']}})
    return Inference(model or Model(), filtering, 'station-01')


def window(stamp=STAMP):
    return Window(bytearray(b'\x01\x00' * WINDOW_SAMPLES), stamp)


def test_pipeline_reaches_sqlite_and_lcd_across_outage_and_duplicates(tmp_path):
    broker = FakeBroker()
    broker.deliveries = 3
    producer = broker.connection('inference', max_queued_messages=1)
    receiver, station = broker.connection('ingest'), broker.connection('station')
    store = Store(tmp_path/'events.sqlite')
    display = DetectionDisplay(station, DisplayController(warmup_ms=0))
    received = []
    def ingest(kind, event, topic):
        received.append(event)
        store.insert(kind, event)
    receiver.subscribe('detection', ingest)
    queue = WindowQueue()
    publisher = DetectionPublisher(producer)
    pipeline = PublishingPipeline(queue, engine(), publisher)
    try:
        broker.go_down()
        expected = []
        for stamp in (STAMP, '2026-11-17T10:00:03Z'):
            pcm = window(stamp)
            queue.put(pcm)
            expected.extend(pipeline.step())
            assert not any(pcm.pcm)
        assert publisher.pending == 1 and not received
        broker.come_up()
        assert pipeline.step() == []  # idle tick flushes without another bird
        assert publisher.pending == 0
        assert received == [expected[0]]*3 + [expected[1]]*3
        assert store.db.execute("SELECT count(*) FROM events WHERE kind='detection'").fetchone()[0] == 2
        frame = display.tick(pir=True, touch=False, monotonic_ms=0,
                             utc_ms=to_epoch_ms('2026-11-17T10:00:04Z'))
        assert 'Turdus merula' in ''.join(frame.rows)
        assert display.controller.latest_key[1] == expected[-1]['event_id']
        sent = [json.loads(payload) for payload in broker.published(TOPIC)]
        assert sent == expected
        assert all(not retain for topic, _, retain in broker.log if topic == TOPIC)
    finally:
        queue.close()
        for connection in (producer, receiver, station): connection.close()
        store.close()


def test_pending_event_is_independent_of_caller_mutation():
    broker = FakeBroker()
    connection = broker.connection('inference', max_queued_messages=1)
    publisher = DetectionPublisher(connection)
    broker.go_down()
    try:
        publisher.publish_event(engine().process(window())[0])
        original = engine().process(window('2026-11-17T10:00:03Z'))[0]
        expected = json.loads(json.dumps(original))
        returned = publisher.publish_event(original)
        original['species']['scientific_name'] = 'Parus major'
        returned['observed_at'] = '2026-11-18T00:00:00Z'
        broker.come_up()
        publisher.flush()
        assert json.loads(broker.published(TOPIC)[-1]) == expected
    finally:
        connection.close()


@pytest.mark.parametrize('change', [{'station_id': 'station-02'}, {'audio': 'forbidden'}, {'confidence': 2}])
def test_invalid_event_does_not_send_or_flush(change):
    broker = FakeBroker()
    connection = broker.connection('inference')
    try:
        event = engine().process(window())[0]
        event.update(change)
        publisher = DetectionPublisher(connection)
        with pytest.raises(MessagingError): publisher.publish_event(event)
        assert not broker.published(TOPIC)
    finally:
        connection.close()


def test_failure_wipes_current_and_queued_pcm():
    class Broken(Model):
        def predict(self, samples): raise RuntimeError('model failure')
    queue = WindowQueue()
    first, second = window(), window()
    queue.put(first); queue.put(second)
    pipeline = PublishingPipeline(queue, engine(Broken()), SimpleNamespace(flush=lambda: None))
    stop = SimpleNamespace(is_set=lambda: False)
    with pytest.raises(RuntimeError, match='model failure'): pipeline.run(stop)
    assert not any(first.pcm) and not any(second.pcm)
    assert queue.pop() is None


def test_conversion_failure_still_wipes_pcm():
    pcm = Window(bytearray(b'\x01'), STAMP)
    with pytest.raises(ValueError): engine().process(pcm)
    assert not any(pcm.pcm)


def test_worker_retries_on_idle_ticks_and_stops():
    calls = []
    queue = WindowQueue()
    stop = SimpleNamespace(is_set=lambda: len(calls) >= 2,
                           wait=lambda seconds: None)
    pipeline = PublishingPipeline(queue, engine(),
                                  SimpleNamespace(flush=lambda: calls.append('flush')))
    pipeline.run(stop)
    assert calls == ['flush', 'flush']
