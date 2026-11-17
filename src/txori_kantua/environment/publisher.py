"""Read four channels and publish validated metadata every 30 seconds (#14)."""
import argparse
import logging
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


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--interval',type=float,default=30)
    p.add_argument('--bus',type=int,default=1)
    p.add_argument('--bme-address',type=lambda x:int(x,0),default=0x76)
    p.add_argument('--light-channel',type=int,default=0)
    p.add_argument('--samples',type=int,default=0,help='0 runs until stopped')
    args=p.parse_args()
    if not 2 <= args.interval <= 3600 or args.samples<0: p.error('invalid interval or sample count')
    logging.basicConfig(level=logging.INFO)
    settings=MqttSettings.from_env(service='sensors')
    stop=threading.Event()
    for sig in (signal.SIGTERM,signal.SIGINT): signal.signal(sig,lambda *_:stop.set())
    stats=Counter(); started=time.monotonic()
    bus=open_bus(args.bus)
    sources=[Bme280Source(bus,addresses=(args.bme_address,)),LightSource(bus,channel=args.light_channel)]
    try:
        with MqttConnection(settings) as mqtt:
            while not stop.is_set():
                before=time.monotonic()
                event=sample_event(sources,settings.station_id,started=started)
                result=mqtt.publish('environment',event)
                stats['accepted' if result.accepted else 'dropped']+=1
                stats['samples']+=1
                logging.info('environment event_id=%s accepted=%s quality=%s',event['event_id'],
                    result.accepted,','.join(f'{k}:{v["quality"]}' for k,v in event['readings'].items()))
                if args.samples and stats['samples']>=args.samples:
                    result.wait(5)
                    break
                stop.wait(max(0,args.interval-(time.monotonic()-before)))
    finally:
        for source in sources: source.close()
        bus.close()
        logging.info('publisher counters=%s',dict(stats))


if __name__=='__main__': main()
