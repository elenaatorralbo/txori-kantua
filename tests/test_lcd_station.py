"""Software integration only: fake MQTT, GPIO and backlight, no physical evidence."""
import json
from types import SimpleNamespace

import pytest

from support.fake_broker import FakeBroker
from txori_kantua.display import DisplayController
from txori_kantua.lcd_station import DetectionDisplay, GpioInputs, load_catalogue, run
from txori_kantua.messaging.events import new_detection
from txori_kantua.messaging.timestamps import to_epoch_ms

STAMP = to_epoch_ms('2026-11-25T10:00:00Z')


def detection(**changes):
    values = dict(station_id='station-01', scientific_name='Turdus merula', confidence=.9,
                  observed_at='2026-11-25T10:00:00Z', window_end='2026-11-25T10:00:03Z',
                  model_name='BirdNET', model_version='synthetic')
    values.update(changes)
    return new_detection(**values)


def test_mqtt_to_screen_reconnect_expiry_and_station_isolation():
    broker = FakeBroker()
    mqtt = broker.connection('station')
    sender = broker.connection('inference')
    screen = DetectionDisplay(mqtt, DisplayController(warmup_ms=0))
    def tick(ms, **kw):
        return screen.tick(pir=True, touch=False, monotonic_ms=ms, utc_ms=STAMP+ms, **kw)
    sender.publish('detection', detection())
    assert 'Turdus' in ''.join(tick(0).rows)
    broker.go_down()
    assert 'conexion' in ''.join(tick(1).rows)
    broker.come_up()
    assert 'Turdus' in ''.join(tick(2).rows)
    broker.inject('txori/v1/station-01/detections', b'{}')
    assert mqtt.stats['invalid'] == 1
    screen.receive('detection', detection(station_id='station-02', scientific_name='Parus major'), '')
    assert 'Turdus' in ''.join(tick(3).rows)
    assert 'Sin datos' in ''.join(tick(300001).rows)
    mqtt.close()
    sender.close()


class ClockStop:
    def __init__(self, end=21):
        self.now, self.end = 0., end
    def is_set(self):
        return self.now >= self.end
    def wait(self, delay):
        self.now += delay


class Lcd:
    def __init__(self, timer, fail=False):
        self.timer, self.fail = timer, fail
        self.lights, self.rows, self.closed = [], [], False
    def set_backlight(self, on):
        self.lights.append((self.timer.now, on))
    def write_rows(self, rows):
        if self.fail:
            raise OSError('I2C unavailable')
        self.rows.append(rows)
    def close(self):
        self.closed = True


@pytest.mark.parametrize('fail', [False, True])
def test_loop_physical_adapter_calls_timeout_and_cleanup(fail):
    timer = ClockStop()
    lcd = Lcd(timer, fail)
    closed = []
    inputs = SimpleNamespace(read=lambda: (True, False), close=lambda: closed.append(True))
    controller = DisplayController(warmup_ms=0)
    if fail:
        with pytest.raises(OSError):
            run(controller, inputs, lcd, timer, clock=lambda: timer.now, utc=lambda: STAMP/1000)
    else:
        run(controller, inputs, lcd, timer, clock=lambda: timer.now, utc=lambda: STAMP/1000)
        assert len(lcd.rows) == 1  # no redundant 50 Hz I2C writes
        off = [at for at, on in lcd.lights if not on and at > 0]
        assert 20 <= off[0] <= 20.1
    assert lcd.closed and closed == [True]
    assert lcd.lights[-1][1] is False


def test_long_name_pages_and_language_fallback(tmp_path):
    path = tmp_path/'catalogue.json'
    path.write_text(json.dumps({'Turdus merula': {'es': 'Un nombre de ave extraordinariamente largo'}}))
    controller = DisplayController(warmup_ms=0, catalogue=load_catalogue(path))
    controller.connected = True
    controller.receive(detection())
    frames = []
    def tick(ms, pressed=False):
        return controller.tick(pir=True, touch=pressed, monotonic_ms=ms, utc_ms=STAMP)
    frames.append(tick(0))
    for n in range(4):
        tick(n*300+60)
        tick(n*300+100, True)
        frames.append(tick(n*300+160, True))
        tick(n*300+200)
    assert frames[0].rows != frames[1].rows
    assert any(f.language == 'eu' and 'Turdus' in ''.join(f.rows) for f in frames)
    assert all(len(row) == 16 for f in frames for row in f.rows)


@pytest.mark.parametrize('value', [[], {'bird': []}, {'bird': {'fr':'oiseau'}}, {'bird': {'es': 2}}])
def test_invalid_catalogue(value, tmp_path):
    path = tmp_path/'catalogue.json'
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        load_catalogue(path)


def test_gpio_failure_does_not_hide_other_input():
    closed = []
    def read(handle, pin):
        if pin == 16:
            raise OSError('unavailable')
        return 1
    driver = SimpleNamespace(gpiochip_open=lambda n: 7, gpio_claim_input=lambda *a: None,
                             gpio_read=read, gpiochip_close=lambda h: closed.append(h))
    inputs = GpioInputs(0, 16, 18, 1, 1, driver=driver)
    assert inputs.read() == (None, True)
    inputs.close()
    inputs.close()
    assert closed == [7]


def test_bundled_catalogue_covers_evaluation_species():
    from importlib.resources import files
    catalogue = load_catalogue(None)
    corpus = json.loads(files('txori_kantua.audio').joinpath('corpus.json').read_text())
    assert set(catalogue) == {r['species'] for r in corpus['recordings']}
    assert all(set(names) == {'es', 'eu', 'en'} for names in catalogue.values())


def test_mqtt_start_failure_releases_all_hardware(monkeypatch):
    import sys
    import txori_kantua.lcd_station as module
    closed = []
    lcd = SimpleNamespace(write_rows=lambda rows: None,
                          set_backlight=lambda enabled: closed.append(('backlight', enabled)),
                          close=lambda: closed.append('lcd'))
    inputs = SimpleNamespace(close=lambda: closed.append('inputs'))
    def fail():
        raise OSError('network startup failed')
    mqtt = SimpleNamespace(subscribe=lambda *args: None, start=fail,
                           close=lambda: closed.append('mqtt'))
    monkeypatch.setenv('TXORI_STATION_ID', 'station-01')
    monkeypatch.setitem(sys.modules, 'test_board', SimpleNamespace(create=lambda: lcd))
    monkeypatch.setattr(module, 'GpioInputs', lambda *args: inputs)
    monkeypatch.setattr(module, 'MqttConnection', lambda *args: mqtt)
    monkeypatch.setattr(module.signal, 'signal', lambda *args: None)
    with pytest.raises(OSError, match='network startup failed'):
        module.main(['--chip', '0', '--pir-pin', '16', '--touch-pin', '18',
                     '--warmup-ms', '0', '--debounce-ms', '50', '--pir-active', '1',
                     '--touch-active', '1', '--lcd-factory', 'test_board:create'])
    assert closed == [('backlight', False), 'lcd', 'inputs', 'mqtt']
