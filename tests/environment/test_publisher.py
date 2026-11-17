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
