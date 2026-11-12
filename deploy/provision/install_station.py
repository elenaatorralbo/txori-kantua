"""Run as root on the Pi, from an extracted, reviewed source bundle.

Installs only the sensor/LCD service. Leaves autostart disabled for validation.
"""
from pathlib import Path
import os
import shutil
import subprocess


def call(*args):
    return subprocess.run(args, check=True, text=True)


assert os.geteuid() == 0
source = Path(__file__).resolve().parents[2]
target = Path('/opt/txori-kantua')
assert not target.exists(), 'Existing install: back up and review before replacing'
assert Path('/dev/i2c-1').exists()
assert Path('/dev/gpiochip0').exists()
call('/usr/bin/python3', '-c', 'import smbus2, lgpio')
if subprocess.run(['id', 'txori'], capture_output=True).returncode:
    call('useradd', '--system', '--user-group', '--home-dir', str(target), '--shell', '/usr/sbin/nologin', 'txori')
call('usermod', '-aG', 'i2c,gpio', 'txori')
target.mkdir(mode=0o755)
shutil.copytree(source/'src', target/'src')
shutil.copytree('/home/mprsq/grove.py/grove', target/'grove.py/grove')
for path in target.rglob('*'):
    path.chmod(0o755 if path.is_dir() else 0o644)
for name in ('txori-kantua.service', 'txori-kantua.timer'):
    shutil.copy2(source/'deploy/systemd'/name, Path('/etc/systemd/system')/name)
call('systemd-analyze', 'verify', '/etc/systemd/system/txori-kantua.service', '/etc/systemd/system/txori-kantua.timer')
shutil.copy2(source/'deploy/provision/txori-safe-off', '/usr/local/sbin/txori-safe-off')
Path('/usr/local/sbin/txori-safe-off').chmod(0o755)
call('systemctl', 'daemon-reload')
call('systemctl', 'start', 'txori-kantua.service')
print('STATION_INSTALLED_MANUAL_START_ONLY')
