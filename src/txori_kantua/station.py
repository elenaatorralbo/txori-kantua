"""Bounded sensor/LCD loop supervised by systemd; no network dependency."""
import logging
import os
import signal
import socket
import threading

LOG = logging.getLogger(__name__)


def notify(message):
    address = os.environ.get('NOTIFY_SOCKET')
    if address:
        if address.startswith('@'):
            address = '\0' + address[1:]
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
            client.sendto(message.encode(), address)


def run(sensor, lcd, stop, interval=5, heartbeat=lambda: None):
    previous = None
    try:
        while not stop.is_set():
            try:
                sample = sensor.read()
                row = f"T:{sample['temperature']:.1f}C H:{sample['humidity']:.0f}%"
                state = 'ok'
            except Exception as exc:
                row, state = 'Sensor sin datos', 'unavailable'
                if state != previous:
                    LOG.warning('Sensor unavailable: %s', exc)
            if state != previous and state == 'ok':
                LOG.info('Sensor recovered: %s', row)
            previous = state
            for index, text in enumerate(('Txori Kantua', row)):
                lcd.setCursor(index, 0)
                lcd.write(text[:16].ljust(16))
            # Only after a complete iteration, so a stuck driver trips watchdog.
            heartbeat()
            stop.wait(interval)
    finally:
        for component, action in ((sensor, 'close'), (lcd, 'clear')):
            try:
                getattr(component, action)()
            except Exception:
                LOG.exception('Hardware cleanup failed: %s', action)


def main():
    logging.basicConfig(level=logging.INFO)
    from grove.display.jhd1802 import JHD1802
    from txori_kantua.dht11 import DHT11
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    sensor = DHT11(int(os.environ.get('TXORI_DHT_PIN', '5')))
    try:
        lcd = JHD1802()
    except BaseException:
        sensor.close()
        raise
    notify('READY=1')
    run(sensor, lcd, stop, heartbeat=lambda: notify('WATCHDOG=1'))


if __name__ == '__main__':
    main()
