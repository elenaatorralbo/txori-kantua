import threading
from unittest.mock import Mock
import pytest
from txori_kantua.station import run


def test_sensor_failure_is_visible_and_does_not_stop_lcd():
    stop = threading.Event()
    sensor, lcd = Mock(), Mock()
    sensor.read.side_effect = [OSError('missing'), {'temperature': 21.0, 'humidity': 50}]
    beats = []
    def heartbeat():
        beats.append(True)
        if len(beats) == 2:
            stop.set()
    run(sensor, lcd, stop, interval=0, heartbeat=heartbeat)
    assert [c.args[0] for c in lcd.write.call_args_list] == [
        'Txori Kantua    ', 'Sensor sin datos', 'Txori Kantua    ', 'T:21.0C H:50%   ']
    sensor.close.assert_called_once()
    lcd.clear.assert_called_once()


def test_lcd_error_reaches_supervisor_without_false_heartbeat():
    sensor, lcd, heartbeat = Mock(), Mock(), Mock()
    sensor.read.return_value = {'temperature': 21, 'humidity': 50}
    lcd.write.side_effect = OSError('bus lost')
    lcd.clear.side_effect = OSError('cleanup also fails')
    with pytest.raises(OSError, match='bus lost'):
        run(sensor, lcd, threading.Event(), heartbeat=heartbeat)
    heartbeat.assert_not_called()
    sensor.close.assert_called_once()
