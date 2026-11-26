"""Isolated Mosquitto acceptance harness; uses generated temporary credentials.

Run on Linux: python tools/verify_pipeline.py --mosquitto /path/to/mosquitto
--passwd /path/to/mosquitto_passwd. No production broker/service changes.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import tempfile
import threading
import time

from txori_kantua.api import create_app
from txori_kantua.audio.birdnet import Candidate, WINDOW_SAMPLES
from txori_kantua.audio.filtering import DetectionFilter
from txori_kantua.audio.pipeline import Inference, PublishingPipeline, Window, WindowQueue
from txori_kantua.display import DisplayController
from txori_kantua.lcd_station import DetectionDisplay
from txori_kantua.ingest import Ingestor
from txori_kantua.messaging.detections import DetectionPublisher
from txori_kantua.messaging.client import MqttConnection,MqttSettings
from txori_kantua.messaging.timestamps import now_timestamp, to_epoch_ms


class SyntheticModel:
    """Deterministic test scores, not BirdNET recognition evidence."""
    def version(self): return 'synthetic-integration-test'
    def predict(self, samples): return [.8]
    def top(self, scores, **kwargs):
        return [Candidate(0, 'Turdus merula', 'Blackbird', scores[0])]


def wait_until(condition,timeout=10):
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        if condition(): return
        time.sleep(.05)
    raise AssertionError('condition timed out')


def main():
    p=argparse.ArgumentParser(); p.add_argument('--mosquitto',required=True); p.add_argument('--passwd',required=True)
    p.add_argument('--outage-seconds',type=float,default=60)
    args=p.parse_args()
    if not 1 <= args.outage_seconds <= 300: p.error('outage must be between 1 and 300 seconds')
    import paho.mqtt.client as mqtt
    with tempfile.TemporaryDirectory(prefix='txori-mqtt-') as directory:
        root=Path(directory); (root/'mqtt').mkdir()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
        passwords={name:secrets.token_hex(24) for name in ('inference','sensors','monitor','ingest','station','healthcheck')}
        for i,(name,password) in enumerate(passwords.items()):
            subprocess.run([args.passwd,*(['-c'] if i==0 else []),'-b',str(root/'passwords'),name,password],check=True)
            (root/'mqtt'/f'{name}.env').write_text(f'TXORI_MQTT_USERNAME={name}\nTXORI_MQTT_PASSWORD={password}\n')
        acl=root/'acl'
        shutil.copyfile(Path(__file__).resolve().parents[1]/'deploy/mosquitto/acl',acl)
        (root/'broker.conf').write_text(f'''listener {port} 127.0.0.1
allow_anonymous false
password_file {root}/passwords
acl_file {acl}
persistence true
persistence_location {root}/
autosave_interval 1
message_size_limit 16384
max_queued_messages 1000
max_inflight_messages 20
''')
        broker=None; clients=[]; stop=threading.Event(); worker=None
        log=(root/'broker.log').open('w')
        def start():
            nonlocal broker
            broker=subprocess.Popen([args.mosquitto,'-c',str(root/'broker.conf')],stdout=log,stderr=log)
            def ready():
                if broker.poll() is not None:
                    log.flush()
                    raise AssertionError('broker failed to start: '+(root/'broker.log').read_text()[-3000:])
                try:
                    with socket.create_connection(('127.0.0.1',port),timeout=.2): return True
                except OSError: return False
            wait_until(ready)
        def connect(service):
            c=MqttConnection(MqttSettings(service=service,station_id='station-01',port=port,
                username=service,password=passwords[service],reconnect_max_seconds=2))
            clients.append(c); c.start(); assert c.wait_connected(5); return c
        try:
            start()
            # Existing real-broker ACL, anonymous login, last-will and bounded queue tests.
            env={**os.environ,'TXORI_BROKER_TESTS':'1','TXORI_MQTT_PORT':str(port),'TXORI_CONFIG_DIR':str(root)}
            subprocess.run([os.sys.executable,'-m','pytest','tests/broker','-q',
                            '-o',f'cache_dir={root}/pytest-cache'],env=env,check=True)
            consumer=Ingestor(root/'events.sqlite')
            raw=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='txori-pipeline-ingest',
                            clean_session=False,manual_ack=True)
            raw.username_pw_set('ingest',passwords['ingest'])
            subscribed=threading.Event()
            raw.on_connect=lambda c,u,f,r,p:c.subscribe('txori/v1/station-01/#',qos=1)
            raw.on_subscribe=lambda *args:subscribed.set()
            raw.on_message=consumer.receive
            raw.connect('127.0.0.1',port); raw.loop_start()
            worker=threading.Thread(target=consumer.work,args=(raw,stop)); worker.start()
            assert subscribed.wait(5)
            station=connect('station'); inbox=[]
            display=DetectionDisplay(station,DisplayController(warmup_ms=0))
            def receive_detection(kind,event,topic):
                display.receive(kind,event,topic)
                inbox.append(event)
            station.subscribe('detection',receive_detection)
            publisher=connect('inference'); time.sleep(.2)
            detections=DetectionPublisher(publisher)
            windows=WindowQueue()
            filtering=DetectionFilter(threshold=.5,region='test',revision='synthetic',
                                      seasons={'test':{'11':['Turdus merula']}})
            pipeline=PublishingPipeline(windows,Inference(SyntheticModel(),filtering,'station-01'),detections)
            pcm=Window(bytearray(b'\x01\x00'*WINDOW_SAMPLES),'2026-11-17T10:00:00Z')
            windows.put(pcm)
            event=pipeline.step()[0]
            assert not any(pcm.pcm)
            for _ in range(2): detections.publish_event(event)
            wait_until(lambda:consumer.stats['duplicates']>=2 and len(inbox)>=3)
            assert all(received==event for received in inbox)
            frame=display.tick(pir=True,touch=False,monotonic_ms=0,
                               utc_ms=to_epoch_ms(event['window_end']))
            assert 'Turdus merula' in ''.join(frame.rows)
            api=create_app(root/'events.sqlite').test_client()
            query={'from':'2026-11-17T00:00:00Z','to':'2026-11-18T00:00:00Z'}
            response=api.get('/api/v1/detections',query_string=query)
            assert response.status_code==200 and len(response.json['items'])==1
            broker.terminate(); broker.wait(timeout=5)
            wait_until(lambda:not publisher.connected)
            # Outage exercises the real queue/reconnect path; retain original ID/time.
            detections.publish_event(event)
            time.sleep(args.outage_seconds)
            start(); assert publisher.wait_connected(10)
            wait_until(lambda:consumer.stats['duplicates']>=3)
            response=api.get('/api/v1/detections',query_string=query)
            assert len(response.json['items'])==1
            print(json.dumps({'utc':now_timestamp(),'result':'PASS','consumer':dict(consumer.stats),
                'lcd_consumer_deliveries':len(inbox),'stored_detections':1,'broker_restart':'PASS','outage_seconds':args.outage_seconds,
                'input':'synthetic PCM in RAM and synthetic model; no recorded audio',
                'inference_to_lcd':'PASS'},sort_keys=True))
        finally:
            stop.set()
            if worker: worker.join(timeout=5)
            if 'raw' in locals(): raw.disconnect(); raw.loop_stop()
            for c in clients: c.close()
            if broker and broker.poll() is None: broker.terminate(); broker.wait(timeout=5)
            log.close()


if __name__=='__main__': main()
