"""MQTT detection consumer and bounded, presence-driven LCD loop (#22).

The hardware factory is explicit: the installed JHD1802 backlight method is a
no-op and must not be mistaken for a working physical backlight adapter.
"""
import argparse
import importlib
from importlib.resources import files
import json
import logging
from pathlib import Path
import signal
import threading
import time

from .display import DisplayController
from .messaging.client import MqttConnection, MqttSettings

LOG = logging.getLogger(__name__)


def load_catalogue(path):
    """Load reviewed translations; absent languages use the scientific name."""
    path = files("txori_kantua").joinpath("bird_names.json") if path is None else Path(path)
    with path.open(encoding="utf-8") as stream:
        catalogue = json.load(stream)
    if not isinstance(catalogue, dict):
        raise ValueError('catalogue must map scientific names to translations')
    for name, translations in catalogue.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(translations, dict):
            raise ValueError('invalid catalogue entry')
        for language, value in translations.items():
            if language not in ('es', 'eu', 'en') or not isinstance(value, str) or not value.strip():
                raise ValueError('invalid catalogue language or translation')
    return catalogue


class DetectionDisplay:
    """Serialize network callbacks and UI state; retain only the latest event."""

    def __init__(self, mqtt, controller):
        self.mqtt, self.controller = mqtt, controller
        self._lock = threading.Lock()
        mqtt.subscribe('detection', self.receive)

    def receive(self, kind, event, topic):
        if event['station_id'] != self.mqtt.settings.station_id:
            return
        with self._lock:
            self.controller.receive(event)

    def tick(self, **inputs):
        with self._lock:
            self.controller.connected = self.mqtt.connected
            return self.controller.tick(**inputs)


class GpioInputs:
    """Pi input-only adapter; pin offsets and polarities come from the wiring."""

    def __init__(self, chip, pir_pin, touch_pin, pir_active, touch_active, *, driver=None):
        if min(chip, pir_pin, touch_pin) < 0 or pir_pin == touch_pin:
            raise ValueError('use distinct nonnegative GPIO offsets')
        if pir_active not in (0, 1) or touch_active not in (0, 1):
            raise ValueError('active levels must be 0 or 1')
        if driver is None:
            import lgpio as driver
        self.driver = driver
        self.pins = (pir_pin, touch_pin)
        self.active = (pir_active, touch_active)
        self.handle = driver.gpiochip_open(chip)
        try:
            for pin in self.pins:
                driver.gpio_claim_input(self.handle, pin)
        except BaseException:
            self.close()
            raise

    def read(self):
        values = []
        for pin, active in zip(self.pins, self.active):
            try:
                level = self.driver.gpio_read(self.handle, pin)
                values.append(level == active if level in (0, 1) else None)
            except Exception:
                # A failed input must not prevent the other one from working.
                values.append(None)
        return tuple(values)

    def close(self):
        if self.handle is not None:
            handle, self.handle = self.handle, None
            self.driver.gpiochip_close(handle)


def _cleanup(actions):
    for action in actions:
        try:
            action()
        except Exception:
            LOG.exception('LCD station cleanup failed')


def run(display, inputs, lcd, stop, *, interval=.02, clock=time.monotonic,
        utc=time.time, heartbeat=lambda: None):
    """Poll at 50 Hz; only write changed rows/backlight to the I2C device.

    lcd must provide write_rows(tuple[str, str]), set_backlight(bool), close().
    Neither clear() nor display-off is a substitute for set_backlight(False).
    """
    if not 0 < interval <= .1:
        raise ValueError('poll interval must be in (0, 0.1] seconds')
    previous = None
    try:
        lcd.set_backlight(False)
        while not stop.is_set():
            before = clock()
            pir, touch = inputs.read()
            frame = display.tick(pir=pir, touch=touch,
                                 monotonic_ms=int(clock()*1000), utc_ms=int(utc()*1000))
            # Extinguish first: a slow text write must not delay the timeout.
            if previous is None or frame.backlight != previous.backlight:
                lcd.set_backlight(frame.backlight)
            if frame.backlight and (previous is None or not previous.backlight or frame.rows != previous.rows):
                lcd.write_rows(frame.rows)
            previous = frame
            heartbeat()
            stop.wait(max(0, interval - (clock() - before)))
    finally:
        _cleanup((lambda: lcd.set_backlight(False), lcd.close, inputs.close))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('chip', 'pir-pin', 'touch-pin', 'warmup-ms', 'debounce-ms'):
        parser.add_argument('--'+option, type=int, required=True)
    for option in ('pir-active', 'touch-active'):
        parser.add_argument('--'+option, type=int, choices=(0, 1), required=True)
    parser.add_argument('--catalogue', help='JSON translations; defaults to bundled five-species catalogue')
    parser.add_argument('--lcd-factory', required=True,
                        help='module:callable returning a verified LCD/backlight adapter')
    args = parser.parse_args(argv)
    if (min(args.chip, args.pir_pin, args.touch_pin, args.warmup_ms) < 0
            or args.pir_pin == args.touch_pin or args.debounce_ms <= 0):
        parser.error('invalid GPIO or timing configuration')
    catalogue = load_catalogue(args.catalogue)
    controller = DisplayController(catalogue=catalogue, warmup_ms=args.warmup_ms,
                                   debounce_ms=args.debounce_ms)
    settings = MqttSettings.from_env(service='station')
    module, name = args.lcd_factory.split(':', 1)
    factory = getattr(importlib.import_module(module), name)
    logging.basicConfig(level=logging.INFO)
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    lcd = factory()
    try:
        for method in ('write_rows', 'set_backlight', 'close'):
            if not callable(getattr(lcd, method, None)):
                raise ValueError('LCD adapter must implement '+method)
        inputs = GpioInputs(args.chip, args.pir_pin, args.touch_pin,
                            args.pir_active, args.touch_active)
    except BaseException:
        actions = []
        if callable(getattr(lcd, 'set_backlight', None)):
            actions.append(lambda: lcd.set_backlight(False))
        if callable(getattr(lcd, 'close', None)):
            actions.append(lcd.close)
        _cleanup(actions)
        raise
    # On setup failure, attempt every cleanup without masking the cause.
    mqtt = None
    try:
        mqtt = MqttConnection(settings)
        display = DetectionDisplay(mqtt, controller)
        mqtt.start()
    except BaseException:
        actions = [lambda: lcd.set_backlight(False), lcd.close, inputs.close]
        if mqtt is not None:
            actions.append(mqtt.close)
        _cleanup(actions)
        raise
    try:
        run(display, inputs, lcd, stop)
    finally:
        mqtt.close()


if __name__ == '__main__':
    main()
