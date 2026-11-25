"""Read four channels and publish validated metadata every 30 seconds (#14)."""
import argparse
import logging
import json
import math
import signal
import threading
import time
from collections import Counter

from .i2c import open_bus
from .sensors import Bme280Source, LightSource, sample_all
from ..messaging.client import MqttConnection, MqttSettings
from ..messaging.events import new_environment, reading

# Explicit source selection: never silently switch temperature to another device.
CHANNELS={'temperature':'bme280.temperature','humidity':'bme280.humidity',
          'pressure':'bme280.pressure','light':'light.raw'}


def sample_event(sources,station_id,*,started):
    samples={sample.channel:sample for sample in sample_all(sources,started=started)}
    values={}
    for metric,channel in CHANNELS.items():
        sample=samples[channel]
        values[metric]=reading(sample.value,sample.unit,sample.quality)
    return new_environment(station_id=station_id,readings=values,
                           observed_at=min(s.utc for s in samples.values()))


def run(sources, mqtt, stop, *, interval=30, samples=0, seconds=0,
        ack_timeout=2, clock=time.monotonic):
    """Publish bounded observations and distinguish queue acceptance from PUBACK.

    ``unconfirmed`` means no acknowledgement within the timeout, not definite
    loss. MQTT may deliver it later with the same event_id. No duplicate retry
    or unbounded secondary queue is created here.
    """
    if (not math.isfinite(interval) or not 2 <= interval <= 3600
            or samples < 0 or not math.isfinite(seconds) or seconds < 0
            or not math.isfinite(ack_timeout) or not 0 <= ack_timeout <= interval):
        raise ValueError('invalid publication limits')
    stats = Counter()
    started = clock()
    while not stop.is_set() and (not seconds or clock() - started < seconds):
        before = clock()
        event = sample_event(sources, mqtt.settings.station_id, started=started)
        result = mqtt.publish('environment', event)
        stats['samples'] += 1
        stats['accepted' if result.accepted else 'dropped'] += 1
        confirmed = result.wait(ack_timeout) if result.accepted else False
        if result.accepted:
            stats['confirmed' if confirmed else 'unconfirmed'] += 1
        for metric, value in event['readings'].items():
            stats[f'{metric}.{value["quality"]}'] += 1
        logging.info('environment event_id=%s accepted=%s confirmed=%s quality=%s',
                     event['event_id'], result.accepted, confirmed,
                     ','.join(f'{k}:{v["quality"]}' for k, v in event['readings'].items()))
        if samples and stats['samples'] >= samples:
            break
        delay = max(0, interval - (clock() - before))
        if seconds:
            delay = min(delay, max(0, seconds - (clock() - started)))
        stop.wait(delay)
    return {**stats, 'elapsed_s': round(clock() - started, 3)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--interval',type=float,default=30)
    p.add_argument('--bus',type=int,default=1)
    p.add_argument('--bme-address',type=lambda x:int(x,0),choices=(0x76,0x77),default=0x76)
    p.add_argument('--light-channel',type=int,choices=range(8),default=0)
    p.add_argument('--samples',type=int,default=0,help='0 runs until stopped')
    p.add_argument('--seconds',type=float,default=0,help='bounded duration; 0 runs until stopped')
    args=p.parse_args()
    if (not math.isfinite(args.interval) or not 2 <= args.interval <= 3600
            or args.samples<0 or not math.isfinite(args.seconds) or args.seconds<0 or args.bus<0):
        p.error('invalid interval, duration, bus or sample count')
    logging.basicConfig(level=logging.INFO)
    settings=MqttSettings.from_env(service='sensors')
    stop=threading.Event()
    for sig in (signal.SIGTERM,signal.SIGINT): signal.signal(sig,lambda *_:stop.set())
    bus=open_bus(args.bus)
    sources=[]
    try:
        sources=[Bme280Source(bus,addresses=(args.bme_address,)),LightSource(bus,channel=args.light_channel)]
        with MqttConnection(settings) as mqtt:
            stats=run(sources,mqtt,stop,interval=args.interval,samples=args.samples,seconds=args.seconds)
        print(json.dumps(stats,sort_keys=True))
    finally:
        try:
            for source in sources:
                source.close()
        finally:
            bus.close()


if __name__=='__main__': main()
