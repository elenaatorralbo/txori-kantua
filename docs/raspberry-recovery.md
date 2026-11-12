# Raspberry Pi station recovery

The old installation was erased before its logs could be recovered. Its cause
of disconnection is unknown. The previous station unit restarted indefinitely
every five seconds and had no CPU/memory limits; this was a risk, not a proven
root cause.

## Installed configuration

The station runs as `txori` (no login or sudo), with root-owned code under
`/opt/txori-kantua`. It uses the system Python and a copy of the Grove driver
(commit `15505cb15014a19c30a02ddbef239eaa0a784ee3`). SSH remains an independent
system service; the station cannot change SSH configuration, networking, boot
files or its own source. It has access only to I2C/GPIO and Unix sockets.
This restoration covers the DHT11 on GPIO 5 and the JHD1802 LCD. MQTT,
SQLite ingestion and Grafana are not restored by this installer.

- A timer starts the station once, 90 seconds after boot. SSH does not wait
  for the application. No network-online or broker dependency.
- Three starts maximum within five minutes; 30 seconds between retries.
  After repeated failures, it stays failed until manually restarted or rebooted.
- A complete sensor/display iteration sends a watchdog heartbeat. A 30-second
  stall kills only the service; stopping has a 10-second timeout.
- CPU: 25% of one core. Tasks: 8. Address space: 192 MiB per process, including
  mapped libraries; per-user task limit: 8. Core dumps are disabled.
- MemoryHigh/MemoryMax are additional protections where the kernel supports
  memory cgroups. On this Pi's initial boot they were disabled by the kernel
  command line, so these settings alone MUST NOT be described as enforced.
  LimitAS and LimitNPROC are independent of memory cgroups and were inspected
  on the running service. This program has one process and worker threads.
- Sensor read errors display `Sensor sin datos`; LCD errors reach the supervisor.
  Logs record sensor state changes, not every reading. Output is rate limited.

## Stop and disable from SSH

Run `sudo txori-safe-off`, or use the equivalent commands below.

```sh
sudo touch /boot/firmware/TXORI_DISABLED
sudo systemctl disable --now txori-kantua.timer
sudo systemctl stop txori-kantua.service
```

The flag also blocks manual starts and remains effective across reboots. No
need to delete code. Inspect the error with:

```sh
systemctl status txori-kantua --no-pager
journalctl -u txori-kantua -n 60 --no-pager
```

After repairing:

```sh
sudo rm /boot/firmware/TXORI_DISABLED
sudo systemctl reset-failed txori-kantua
sudo systemctl start txori-kantua
sudo systemctl enable txori-kantua.timer
```

## Recovery without SSH

With the Raspberry powered off, insert its SD into the Mac and create an empty
file named exactly `TXORI_DISABLED` (no extension) in the root of the FAT boot
partition, alongside `config.txt`. Eject, reinsert and boot. The application
will be skipped; SSH still needs working power, boot media and networking.

Application isolation cannot guarantee access during power failure, broken
Wi-Fi, SD corruption, kernel hangs or a hardware/I2C fault inside the kernel.
A systemd watchdog cannot immediately kill a task stuck in uninterruptible
kernel I/O. No automatic whole-device reboot is configured.

## Reinstallation and validation

`deploy/provision/install_station.py` installs only on a fresh target, from an
extracted source bundle, with `~/grove.py` already present for user `mprsq`.
It checks hardware devices and imports, verifies systemd units, and starts the
station manually. It deliberately does not enable the timer. Validate normal
readings, crash recovery, watchdog recovery, retry exhaustion and the disable
flag before enabling the timer. Test SSH from separate connections throughout,
then reboot to validate the delayed startup.
