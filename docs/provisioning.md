# Raspberry Pi provisioning and Python environment

Procedure of issue [#2](https://github.com/elenaatorralbo/txori-kantua/issues/2).

> **Status: not run on hardware.** The scripts have been written and reviewed
> without access to the Raspberry Pi 5. Only their syntax has been checked, and
> that the report degrades gracefully when a probe is missing. Until someone
> runs them on the Pi and attaches the report, **no acceptance criterion of #2
> is met**. If a step fails on the real Pi, the script is fixed in a PR: it is
> not fixed by hand on the device without leaving a trace.

Depends on [#1](https://github.com/elenaatorralbo/txori-kantua/issues/1)
(inventory and safe wiring): do not power on or connect peripherals without
that inventory.

## What each script does

| Script | Where it runs | What it does | Changes the system |
|---|---|---|---|
| `deploy/provision/provision.sh` | Pi, with `sudo` | Base packages, time zone and NTP, service user, directories, virtual environment; optionally key-only SSH and disabled swap | Yes, idempotently |
| `deploy/provision/install_app.sh` | Pi, with `sudo` | Installs the package into the virtual environment and, with `--freeze`, pins the versions | Only the virtual environment |
| `deploy/provision/collect_report.sh` | Pi, without `sudo` | Generates the evidence report in Markdown | No |

## Step by step

### 0. Before starting

1. Flash **64-bit Raspberry Pi OS** with Raspberry Pi Imager. In its advanced
   options: host name, personal user, **SSH public key** and network. Use Lite
   (no desktop) unless a screen is needed.
2. Note down power supply, cooling and storage medium: they go in the report
   and cannot be read by software.
3. Boot and check that SSH works **with the key**.

### 1. Clone and dry run

```bash
git clone https://github.com/elenaatorralbo/txori-kantua.git
cd txori-kantua
sudo deploy/provision/provision.sh --dry-run --harden-ssh --disable-swap
```

`--dry-run` shows each command without running it. Read the whole output the
first time.

### 2. Provision

```bash
sudo deploy/provision/provision.sh
```

It creates the system user `txori` (no shell or password), the directories and
the virtual environment:

| Path | Content | Permissions |
|---|---|---|
| `/opt/txori-kantua/venv` | Virtual environment | `txori` |
| `/opt/txori-kantua/app` | Copy of the installed code | `txori` |
| `/var/lib/txori-kantua` | Database and backups | `txori`, `0750` |
| `/etc/txori-kantua` | Configuration and credentials, outside Git | `root:txori`, `0750` |

The paths can be changed with `TXORI_HOME`, `TXORI_DATA_DIR`,
`TXORI_CONFIG_DIR`, `TXORI_USER` and `TXORI_TIMEZONE`.

### 3. Key-only SSH

```bash
sudo deploy/provision/provision.sh --harden-ssh
```

The script refuses to continue if the user does not already have a key in
`authorized_keys`, validates the configuration with `sshd -t` before reloading
and removes it if it is invalid. Even so: **do not close the current session**
until another one has been opened with the key.

### 4. Swap and dumps

```bash
sudo deploy/provision/provision.sh --disable-swap
```

[privacy.md](privacy.md) requires that a memory page containing audio does not
reach disk. This step disables swap and memory dumps. The full privacy
verification belongs to
[#11](https://github.com/elenaatorralbo/txori-kantua/issues/11); this only
prepares the base. Disabling swap reduces the memory margin: if the
measurement of [#8](https://github.com/elenaatorralbo/txori-kantua/issues/8)
shows that BirdNET does not fit without swap, it has to be decided with David,
not silently re-enabled.

### 5. Install the application

```bash
sudo deploy/provision/install_app.sh --with-dev
sudo -u txori /opt/txori-kantua/venv/bin/python -m pytest /opt/txori-kantua/app/tests -q
```

The contract tests must pass on the Pi just as on a laptop. If they pass, pin
the versions:

```bash
sudo deploy/provision/install_app.sh --freeze
git add deploy/requirements-pi.lock    # and open a PR
```

`deploy/requirements-pi.lock` **does not exist yet**: it can only be generated
on a real Pi. Once it exists, `install_app.sh` installs exactly those
versions.

### 6. Reboot and collect the evidence

```bash
sudo reboot
# after logging in again with the key:
deploy/provision/collect_report.sh --idle-seconds 300 > provisioning-report.md
```

Complete the "To fill in by hand" section and attach the report to issue #2
following [the evidence template](evidence/README.md).

## Mapping to the acceptance criteria

| Criterion of #2 | How it is checked | Status |
|---|---|---|
| After reboot, access works with keys and the clock is synchronised | Step 6: log in over SSH after `reboot`; the report shows "SSH with password: no" and "Clock synchronised: yes" | Pending hardware |
| A second member reproduces the environment from the instructions | Another person follows this document on a clean card and signs the report | Pending hardware and second person |
| Report records OS, Python, architecture, storage and idle temperature | `collect_report.sh` | Script ready; report pending |

## Development environment on a laptop

To work without the Pi, on any system:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

Requires Python 3.11 or later. Tests marked `hardware` or `broker` do not run
without their requirement.

## Known limitations

- Not run on a Raspberry Pi 5. Service names (`ssh`, `dphys-swapfile`) and the
  swap mechanism change between Raspberry Pi OS versions; the script warns
  instead of assuming, and the report shows the real state.
- It does not configure the network, firewall or automatic updates.
- It does not add the `txori` user to the hardware groups (`audio`, `i2c`,
  `gpio`): the issue that needs each peripheral does that, with its
  justification.
