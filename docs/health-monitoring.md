# Health monitoring (issue #24)

`python -m txori_kantua.health.monitor` emits one
[health event](../contracts/mqtt/health.schema.json) every 30 s: CPU, used
memory, SoC temperature, free disk, uptime and the status of each station
service. Each event is validated against the contract before it leaves the
process. **Panel and MQTT publication are pending:** the event goes to stdout
(journald) until the publisher of [#18](https://github.com/elenaatorralbo/txori-kantua/issues/18)
and the broker of [#13](https://github.com/elenaatorralbo/txori-kantua/issues/13)
exist; the panel belongs to the Grafana work of
[#21](https://github.com/elenaatorralbo/txori-kantua/issues/21).

## Fields

| Field | Source | When unknown |
|---|---|---|
| `cpu_percent` | `/proc/stat`, averaged over the interval, whole device | `null` (first sample has nothing to compare with) |
| `memory_used_bytes` | `/proc/meminfo`: `MemTotal - MemAvailable` | `null` |
| `cpu_temperature_c` | `/sys/class/thermal/thermal_zone0/temp` (SoC) | `null`, also outside -40..150 degC |
| `disk_free_bytes` | `statvfs` of `--disk-path` (where the database lives), space available to users | `null` |
| `uptime_seconds` | `/proc/uptime` | `null` |
| `services` | `systemctl show` per unit | `failed` |

These are the fields the contract already lists; this answers the open
question on health fields in [interfaces.md](interfaces.md). Throttling is not in
the contract; it is measured by the BirdNET benchmark of #8.

## Service status

| systemd | Health status |
|---|---|
| `active/running` (or `exited` for a oneshot) | `healthy` |
| `activating`, `reloading`, `deactivating` | `degraded` |
| `active`, but `NRestarts` grew since the last check | `degraded` (crash loop) |
| `inactive` (stopped), `failed`, unit not found, systemctl unavailable | `failed` |

A controlled stop (`systemctl stop`) is **not healthy**. The monitored units
are passed with `--service name=unit`; today only `station=txori-kantua.service`
exists. Capture, inference, ingest and API are added as they are deployed.

## Thresholds

Logged as a warning (`budget exceeded`) with the `event_id` of the event.
They come from measured or decided budgets and are reviewed with the Pi
measurements of #8:

| Metric | Threshold | Origin |
|---|---|---|
| SoC temperature | >= 80 degC | ADR 0001 viability rule |
| Used memory | >= 3 GiB of 4 GiB | Leaves 1 GiB free; BirdNET peak RSS ≤ 512 MB (ADR 0001) |
| Free disk | <= 1 GiB | Degraded mode (ADR 0007, #26) |
| CPU | >= 90 % | Capture must keep pace with inference (#8 live mode) |

## Logs

- One JSON object per line on stderr: `ts`, `level`, `logger`, `msg`,
  `event_id`, `service`, `status`, `systemd`. Exceptions keep only their type
  and message. A status is logged when it **changes**, not every 30 s.
- Rotation by journald with
  [`deploy/journald/90-txori-journal.conf`](../deploy/journald/90-txori-journal.conf):
  64 MiB total, 8 MiB files, 30 days. Check with `journalctl --disk-usage`.
- The monitor never touches audio. The events contain only numbers and
  service names: no paths, credentials, IP addresses or user names.

## Installation

```sh
sudo install -m 0644 deploy/systemd/txori-health.service /etc/systemd/system/
sudo install -D -m 0644 deploy/journald/90-txori-journal.conf /etc/systemd/journald.conf.d/90-txori-journal.conf
sudo systemctl restart systemd-journald
sudo systemctl daemon-reload && sudo systemctl enable --now txori-health.service
journalctl -u txori-health -o cat -n 5
```

The unit runs as a dynamic user without capabilities, 64 MiB memory and 5 %
CPU. `systemctl show` needs no privileges.

## Acceptance criteria mapping

| Criterion | Status |
|---|---|
| Panel shows resources and the last update of each service | Pending #21 (Grafana) and #13/#18 (transport). Fields ready |
| Controlled stop of a service produces a non-healthy status | Implemented and tested; checked on the Pi with the station stopped (see PR) |
| Logs rotate with a documented limit, no credentials or audio | journald drop-in above; JSON logs reviewed |
