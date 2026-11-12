# Raspberry Pi recovery validation — 2026-11-12

Physical Pi 5, user `mprsq`, Raspberry Pi OS / Debian 13 aarch64.
Grove JHD1802 and DHT11 on GPIO 5; systemd 257.
The old SD was reimaged before investigation: original failure cause unknown.

## Completed checks before reboot

- Fresh SSH connections succeeded throughout application failure tests.
- SSH independently enabled and active; firmware power status `throttled=0x0`.
- Root-owned station code, unprivileged `txori`, four running tasks, limit eight.
- Real reading observed: `T:27.0C H:59%`; later `T:25.4C H:59%`.
- SIGKILL at 16:45:06: service restarted at 16:45:36 and read the sensor.
- SIGSTOP at 16:45:38: watchdog killed stalled process at 16:46:07;
  supervisor launched replacement at 16:46:37.
- Repeated forced failures exhausted restart budget at 16:47:42:
  journal `Start request repeated too quickly`; service remained failed,
  SSH remained active. systemd kept `Result=signal`, not `start-limit-hit`.
  The initial test assertion expected the latter; log and state inspection
  verified actual rate-limit enforcement. Test harness corrected accordingly.
- `sudo txori-safe-off` successfully stopped the app and set the SD flag.
  A manual start with flag present returned `MainPID=0`, `ConditionResult=no`.
  Removing the flag and starting restored the station to active.
- CPU cgroup: `cpu.max = 25000 100000` (25% of one core).
- LimitAS: 201326592 bytes; LimitNPROC: 8; TasksMax: 8.
  A separate transient `txori` process with the same LimitAS rejected a
  256 MiB allocation with MemoryError (`MEMORY_LIMIT_ENFORCED`).
- Memory cgroup controller absent at initial boot; MemoryMax alone is not
  enforced there. Effective per-process limits tested independently.
- Two unit tests pass: sensor outage/recovery, LCD write failure plus cleanup
  failure preserving original error and withholding watchdog heartbeat.
- `systemd-analyze verify` passed on the installed service and timer.

The tests cover application failures, not physical unplugging of peripherals,
SD corruption, loss of Wi-Fi, whole-system memory exhaustion or kernel hangs.

## Reboot and delayed automatic startup

- Fresh boot ID confirmed; SSH accepted a new connection at uptime 13.28 s.
- At uptime 88.66 s: SSH active, timer active, station inactive (`MainPID=0`).
- Station started at 16:50:51 and became active at 16:50:52.
- At uptime 97.03 s: SSH active, station active (`MainPID=1941`).
- Sensor reading after boot: `T:25.4C H:59%`; `throttled=0x0`.
- Timer enabled for subsequent boots. Emergency disable flag removed after test.
