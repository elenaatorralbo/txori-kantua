"""Durable MQTT consumer: acknowledge only after commit; bounded retry queue."""
from __future__ import annotations

import logging
import os
import queue
import signal
import threading
import time
from collections import Counter

from .messaging.contracts import decode
from .messaging.errors import MessagingError
from .messaging.client import MqttSettings
from .messaging.events import availability
from .messaging.contracts import encode
from .messaging.topics import availability_topic
from .storage import Store

LOG=logging.getLogger(__name__)


class Ingestor:
    """Worker owns SQLite; network thread enqueues at most capacity metadata messages.

    A rejected queue entry is never ACKed. Reconnect with the persistent session
    redelivers it. Invalid payloads are ACKed and counted without logging content.
    """
    def __init__(self,path,capacity=1000):
        if capacity<1: raise ValueError('capacity must be positive')
        self.path=path
        self.pending=queue.Queue(maxsize=capacity)
        self.stats=Counter()
        self.reconnect=threading.Event()

    def receive(self,client,userdata,msg):
        try:
            kind,event=decode(msg.topic,msg.payload)
        except MessagingError:
            self.stats['invalid']+=1
            LOG.warning('invalid event rejected bytes=%d',len(msg.payload))
            client.ack(msg.mid,msg.qos)
            return
        try:
            self.pending.put_nowait((kind,event,msg.mid,msg.qos))
        except queue.Full:
            self.stats['queue_full']+=1
            self.reconnect.set()

    def work(self,client,stop):
        store=Store(self.path)
        maintenance_at=time.monotonic()+60
        try:
            while not stop.is_set():
                if time.monotonic()>=maintenance_at:
                    try: store.maintain()
                    except Exception: LOG.warning("retention maintenance deferred")
                    maintenance_at=time.monotonic()+60
                try: item=self.pending.get(timeout=.2)
                except queue.Empty: continue
                kind,event,mid,qos=item
                delay=1
                while not stop.is_set():
                    try:
                        inserted=store.insert(kind,event)
                    except ValueError:
                        self.stats['conflicting_id']+=1
                        LOG.error('conflicting event identity rejected')
                        client.ack(mid,qos)
                        break
                    except Exception:
                        # Keep only the current metadata item plus the bounded queue.
                        self.stats['storage_errors']+=1
                        LOG.warning('storage unavailable; event remains unacknowledged')
                        stop.wait(delay); delay=min(60,delay*2)
                        continue
                    self.stats['inserted' if inserted else 'duplicates']+=1
                    client.ack(mid,qos)
                    break
                self.pending.task_done()
        finally:
            store.close()


def main():
    import paho.mqtt.client as mqtt
    logging.basicConfig(level=logging.INFO)
    settings=MqttSettings.from_env(service='ingest')
    consumer=Ingestor(os.environ.get('TXORI_DATABASE','/var/lib/txori-kantua/events.sqlite'))
    stop=threading.Event()
    for sig in (signal.SIGINT,signal.SIGTERM): signal.signal(sig,lambda *_:stop.set())
    client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
        client_id=f'txori-{settings.station_id}-ingest',clean_session=False,manual_ack=True)
    client.username_pw_set(settings.username,settings.password)
    topic=availability_topic(settings.station_id,'ingest')
    def state(status):
        return encode('availability',availability(station_id=settings.station_id,service='ingest',status=status))
    client.will_set(topic,state('offline'),qos=1,retain=True)
    client.reconnect_delay_set(1,60)
    def connected(c,u,f,reason,p):
        if not reason.is_failure:
            c.subscribe(f'txori/v1/{settings.station_id}/#',qos=1)
            c.publish(topic,state('online'),qos=1,retain=True)
    client.on_connect=connected
    client.on_message=consumer.receive
    worker=threading.Thread(target=consumer.work,args=(client,stop),daemon=True)
    worker.start()
    client.connect_async(settings.host,settings.port,settings.keepalive)
    client.loop_start()
    try:
        while not stop.wait(1):
            if not worker.is_alive():
                raise RuntimeError('ingest worker stopped')
            if consumer.reconnect.is_set():
                # Wait for room, then replay unacknowledged messages from broker.
                if consumer.pending.qsize()<consumer.pending.maxsize//2+1:
                    client.disconnect(); client.loop_stop()
                    client.connect_async(settings.host,settings.port,settings.keepalive)
                    client.loop_start(); consumer.reconnect.clear()
    finally:
        stop.set(); worker.join(timeout=5)
        if client.is_connected():
            client.publish(topic,state('offline'),qos=1,retain=True).wait_for_publish(2)
        client.disconnect(); client.loop_stop()


if __name__=='__main__': main()
