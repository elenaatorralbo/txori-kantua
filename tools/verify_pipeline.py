"""Isolated Mosquitto acceptance harness; uses generated temporary credentials.

Run on Linux: python tools/verify_pipeline.py --mosquitto /path/to/mosquitto
--passwd /path/to/mosquitto_passwd. No production broker/service changes.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import threading
import time

from txori_kantua.api import create_app
from txori_kantua.ingest import Ingestor
from txori_kantua.messaging.client import MqttConnection,MqttSettings
from txori_kantua.messaging.events import new_detection
from txori_kantua.messaging.timestamps import now_timestamp


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
        acl=Path(__file__).resolve().parents[1]/'deploy/mosquitto/acl'
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
                if broker.poll() is not None: raise AssertionError('broker failed to start')
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
            subprocess.run([os.sys.executable,'-m','pytest','tests/broker','-q'],env=env,check=True)
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
            station.subscribe('detection',lambda k,e,t:inbox.append(e))
            publisher=connect('inference'); time.sleep(.2)
            event=new_detection(station_id='station-01',scientific_name='Turdus merula',confidence=.8,
                observed_at='2026-11-17T10:00:00Z',window_end='2026-11-17T10:00:03Z',
                model_name='BirdNET',model_version='synthetic-integration-test')
            for _ in range(3): assert publisher.publish('detection',event).wait(5)
            wait_until(lambda:consumer.stats['duplicates']>=2 and len(inbox)>=3)
            api=create_app(root/'events.sqlite').test_client()
            query={'from':'2026-11-17T00:00:00Z','to':'2026-11-18T00:00:00Z'}
            response=api.get('/api/v1/detections',query_string=query)
            assert response.status_code==200 and len(response.json['items'])==1
            broker.terminate(); broker.wait(timeout=5)
            wait_until(lambda:not publisher.connected)
            # Outage exercises the real queue/reconnect path; retain original ID/time.
            queued=publisher.publish('detection',event); assert queued.accepted
            time.sleep(args.outage_seconds)
            start(); assert publisher.wait_connected(10)
            wait_until(lambda:consumer.stats['duplicates']>=3)
            response=api.get('/api/v1/detections',query_string=query)
            assert len(response.json['items'])==1
            print(json.dumps({'utc':now_timestamp(),'result':'PASS','consumer':dict(consumer.stats),
                'lcd_consumer_deliveries':len(inbox),'stored_detections':1,'broker_restart':'PASS','outage_seconds':args.outage_seconds,
                'input':'synthetic metadata; no audio'},sort_keys=True))
        finally:
            stop.set()
            if worker: worker.join(timeout=5)
            if 'raw' in locals(): raw.disconnect(); raw.loop_stop()
            for c in clients: c.close()
            if broker and broker.poll() is None: broker.terminate(); broker.wait(timeout=5)
            log.close()


if __name__=='__main__': main()
