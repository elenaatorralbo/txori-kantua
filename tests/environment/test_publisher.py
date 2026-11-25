from txori_kantua.environment.sensors import Source, Channel, Unavailable
from txori_kantua.environment.publisher import sample_event
from txori_kantua.messaging.contracts import validate

class Bme(Source):
    channels=(Channel('bme280.temperature','temperature','degC',(-40,85)),
        Channel('bme280.humidity','humidity','percent',(0,100)),
        Channel('bme280.pressure','pressure','hPa',(300,1100)))
    def read(self):
        return {'bme280.temperature':20,'bme280.humidity':50,'bme280.pressure':1000}

class Light(Source):
    channels=(Channel('light.raw','light','raw',(0,1000)),)
    def read(self): raise Unavailable('disconnected')


def test_bad_sensor_does_not_block_three_good_channels():
    event=sample_event([Bme(),Light()],'station-01',started=0)
    validate('environment',event)
    assert len(event['readings'])==4
    assert event['readings']['light']=={'value':None,'unit':'raw','quality':'unavailable'}
    assert event['readings']['temperature']['value']==20
    assert event['event_id']!=sample_event([Bme(),Light()],'station-01',started=0)['event_id']


class Timer:
    def __init__(self): self.now = 0
    def is_set(self): return False
    def wait(self, seconds): self.now += seconds


def test_simulated_30_minutes_deliver_four_channels_and_unique_events():
    from support.fake_broker import FakeBroker
    from txori_kantua.environment.publisher import run
    class WorkingLight(Light):
        def read(self): return {'light.raw': 123}
    timer = Timer()
    broker = FakeBroker()
    sender = broker.connection('sensors')
    receiver = broker.connection('ingest')
    received = []
    receiver.subscribe('environment', lambda kind, event, topic: received.append(event))
    stats = run([Bme(), WorkingLight()], sender, timer, seconds=1800, clock=lambda: timer.now)
    assert stats['elapsed_s'] == 1800
    assert stats['samples'] == stats['confirmed'] == 60
    assert len({event['event_id'] for event in received}) == 60
    for metric in ('temperature', 'humidity', 'pressure', 'light'):
        assert stats[metric+'.ok'] == 60
    assert received[0]['readings']['light']['unit'] == 'raw'
    sender.close()
    receiver.close()


def test_outage_queue_rejection_recovery_and_sensor_failure():
    from support.fake_broker import FakeBroker
    from txori_kantua.environment.publisher import run
    timer = Timer()
    broker = FakeBroker()
    sender = broker.connection('sensors', max_queued_messages=1)
    received = []
    receiver = broker.connection('ingest')
    receiver.subscribe('environment', lambda kind, event, topic: received.append(event))
    broker.go_down()
    stats = run([Bme(), Light()], sender, timer, samples=2, clock=lambda: timer.now)
    assert stats['accepted'] == stats['unconfirmed'] == stats['dropped'] == 1
    assert stats.get('confirmed', 0) == 0
    assert stats['temperature.ok'] == stats['light.unavailable'] == 2
    broker.come_up()
    assert len(received) == 1
    assert received[0]['readings']['light']['value'] is None
    sender.close()
    receiver.close()
