import threading
import time
from types import SimpleNamespace

from txori_kantua.ingest import Ingestor
from txori_kantua.messaging.events import new_environment,reading
from txori_kantua.messaging.contracts import encode

class Client:
    def __init__(self): self.acks=[]
    def ack(self,mid,qos): self.acks.append((mid,qos))

def message(mid=1):
    return SimpleNamespace(topic='txori/v1/station-01/environment',qos=1,mid=mid,
        payload=encode('environment',new_environment(station_id='station-01',readings={'temperature':reading(20,'degC')})))

def test_invalid_payload_is_not_logged_and_is_acknowledged(tmp_path,caplog):
    c=Client(); consumer=Ingestor(tmp_path/'db'); msg=message()
    msg.payload=b'{"private_audio":"DO_NOT_LOG_THIS"}'
    consumer.receive(c,None,msg)
    assert c.acks==[(1,1)] and consumer.stats['invalid']==1
    assert 'DO_NOT_LOG_THIS' not in caplog.text

def test_overflow_does_not_ack_unstored_messages(tmp_path):
    c=Client(); consumer=Ingestor(tmp_path/'db',capacity=1)
    consumer.receive(c,None,message(1)); consumer.receive(c,None,message(2))
    assert not c.acks and consumer.pending.qsize()==1
    assert consumer.stats['queue_full']==1 and consumer.reconnect.is_set()

def test_failed_write_is_retried_before_ack(tmp_path,monkeypatch):
    from txori_kantua import ingest
    calls=[]
    class Flaky:
        def __init__(self,path): pass
        def insert(self,kind,event):
            calls.append(event['event_id'])
            if len(calls)==1: raise OSError('disk full')
            return True
        def close(self): pass
    monkeypatch.setattr(ingest,'Store',Flaky)
    c=Client(); consumer=Ingestor(tmp_path/'db'); msg=message()
    consumer.receive(c,None,msg)
    stop=threading.Event(); worker=threading.Thread(target=consumer.work,args=(c,stop)); worker.start()
    try:
        time.sleep(.1); assert not c.acks
        deadline=time.monotonic()+3
        while not c.acks and time.monotonic()<deadline: time.sleep(.02)
        assert c.acks==[(1,1)] and calls[0]==calls[1]
        assert consumer.stats['storage_errors']==1
    finally:
        stop.set(); worker.join(timeout=2)


def test_deep_json_and_nonfinite_numbers_do_not_stop_consumer(tmp_path):
    c=Client(); consumer=Ingestor(tmp_path/'db')
    for payload in [b'['*1500+b'0'+b']'*1500, b'{"confidence":NaN}']:
        msg=message(); msg.payload=payload
        consumer.receive(c,None,msg)
    consumer.receive(c,None,message(3))
    assert consumer.stats['invalid']==2
    assert consumer.pending.qsize()==1 and len(c.acks)==2
