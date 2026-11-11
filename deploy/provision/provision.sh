#!/usr/bin/env bash
# Base provisioning of the Raspberry Pi 5 for Txori Kantua (issue #2).
#
# Idempotent: it can be run several times. Each step checks the state before
# changing it and says what it does.
#
#   sudo ./provision.sh                  # safe steps
#   sudo ./provision.sh --harden-ssh     # also, SSH with keys only
#   sudo ./provision.sh --disable-swap   # also, no swap on disk (privacy)
#   sudo ./provision.sh --dry-run ...    # shows what it would do, changes nothing
#
# It does NOT install Mosquitto, Grafana or application services: that belongs
# to issues #13, #21 and #29.
#
# STATUS: written without access to the Raspberry Pi. It has not been run on
# real hardware. The first run must be done with --dry-run and reviewed.
set -euo pipefail

APP_USER="${TXORI_USER:-txori}"
APP_HOME="${TXORI_HOME:-/opt/txori-kantua}"
DATA_DIR="${TXORI_DATA_DIR:-/var/lib/txori-kantua}"
CONFIG_DIR="${TXORI_CONFIG_DIR:-/etc/txori-kantua}"
TIMEZONE="${TXORI_TIMEZONE:-Europe/Madrid}"
SSH_USER="${TXORI_SSH_USER:-${SUDO_USER:-}}"

DRY_RUN=0
HARDEN_SSH=0
DISABLE_SWAP=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --harden-ssh) HARDEN_SSH=1 ;;
    --disable-swap) DISABLE_SWAP=1 ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

log()  { printf '[provision] %s\n' "$*"; }
warn() { printf '[provision] WARNING: %s\n' "$*" >&2; }
die()  { printf '[provision] ERROR: %s\n' "$*" >&2; exit 1; }

run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '[provision] (dry-run) %s\n' "$*"
  else
    "$@"
  fi
}

# --------------------------------------------------------------------------
# Preliminary checks
# --------------------------------------------------------------------------
[ "$(uname -s)" = "Linux" ] || die "this script only runs on the Raspberry Pi (Linux)"
if [ "$DRY_RUN" -eq 0 ] && [ "$(id -u)" -ne 0 ]; then
  die "run with sudo (or use --dry-run)"
fi

ARCH="$(uname -m)"
if [ "$ARCH" != "aarch64" ]; then
  warn "architecture $ARCH: aarch64 expected (64-bit Raspberry Pi OS)"
fi

# --------------------------------------------------------------------------
# 1. System packages
# --------------------------------------------------------------------------
log "1/7 system packages"
PACKAGES=(python3 python3-venv python3-pip git ca-certificates sqlite3)
MISSING=()
for pkg in "${PACKAGES[@]}"; do
  dpkg -s "$pkg" >/dev/null 2>&1 || MISSING+=("$pkg")
done
if [ "${#MISSING[@]}" -gt 0 ]; then
  log "installing: ${MISSING[*]}"
  run apt-get update
  run apt-get install -y --no-install-recommends "${MISSING[@]}"
else
  log "already installed"
fi

# --------------------------------------------------------------------------
# 2. Time zone and clock synchronisation
# --------------------------------------------------------------------------
# Storage works in UTC; the time zone only affects local presentation. What
# matters is that the clock is synchronised: the Pi has no battery-backed clock
# and boots with an old time until it synchronises.
log "2/7 time zone and clock"
CURRENT_TZ="$(timedatectl show -p Timezone --value 2>/dev/null || echo unknown)"
if [ "$CURRENT_TZ" != "$TIMEZONE" ]; then
  run timedatectl set-timezone "$TIMEZONE"
else
  log "time zone is already $TIMEZONE"
fi
run timedatectl set-ntp true
if [ "$(timedatectl show -p NTPSynchronized --value 2>/dev/null)" = "yes" ]; then
  log "clock synchronised"
else
  warn "the clock is not synchronised yet; check the network and repeat collect_report.sh"
fi

# --------------------------------------------------------------------------
# 3. Unprivileged service user
# --------------------------------------------------------------------------
# System user with no shell or password: it runs the services, nobody logs in
# with it. Hardware groups (audio, i2c, gpio) are added by the issue that needs
# them, not this one.
log "3/7 service user $APP_USER"
if id "$APP_USER" >/dev/null 2>&1; then
  log "already exists"
else
  run useradd --system --home-dir "$APP_HOME" --shell /usr/sbin/nologin "$APP_USER"
fi

# --------------------------------------------------------------------------
# 4. Directories
# --------------------------------------------------------------------------
log "4/7 directories"
run install -d -o "$APP_USER" -g "$APP_USER" -m 0755 "$APP_HOME"
run install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$DATA_DIR"
# The service reads the configuration but does not modify it.
run install -d -o root -g "$APP_USER" -m 0750 "$CONFIG_DIR"

# --------------------------------------------------------------------------
# 5. Virtual environment
# --------------------------------------------------------------------------
# Nothing is installed with pip into the system Python. The application
# dependencies are installed into this venv by deploy/provision/install_app.sh.
log "5/7 virtual environment in $APP_HOME/venv"
if [ -x "$APP_HOME/venv/bin/python" ]; then
  log "already exists: $("$APP_HOME/venv/bin/python" --version 2>&1)"
else
  run sudo -u "$APP_USER" python3 -m venv "$APP_HOME/venv"
fi

# --------------------------------------------------------------------------
# 6. SSH with keys only (optional)
# --------------------------------------------------------------------------
log "6/7 SSH"
if [ "$HARDEN_SSH" -eq 1 ]; then
  [ -n "$SSH_USER" ] || die "unknown SSH login user; set TXORI_SSH_USER"
  KEYS="$(getent passwd "$SSH_USER" | cut -d: -f6)/.ssh/authorized_keys"
  # Safeguard: without a key already installed, disabling passwords leaves the
  # Pi unreachable over the network.
  if [ ! -s "$KEYS" ]; then
    die "$KEYS does not exist or is empty. Install the key with ssh-copy-id first and check that it works"
  fi
  DROPIN=/etc/ssh/sshd_config.d/50-txori-kantua.conf
  log "writing $DROPIN"
  if [ "$DRY_RUN" -eq 0 ]; then
    cat > "$DROPIN" <<'SSHD'
# Txori Kantua (issue #2): key-only access.
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
SSHD
    chmod 0644 "$DROPIN"
    # Validate before reloading: a broken configuration also locks you out.
    sshd -t || { rm -f "$DROPIN"; die "sshd rejects the configuration; $DROPIN has been removed"; }
    systemctl reload ssh 2>/dev/null || systemctl reload sshd
    warn "do NOT close this session: open another one with the key and check that it gets in"
  fi
else
  log "no changes (use --harden-ssh once the key works)"
fi

# --------------------------------------------------------------------------
# 7. Swap and memory dumps (optional, privacy)
# --------------------------------------------------------------------------
# docs/privacy.md: a memory page containing audio must not reach disk through
# swap or a dump. Full verification belongs to issue #11; this only prepares
# the base.
log "7/7 swap and dumps"
if [ "$DISABLE_SWAP" -eq 1 ]; then
  run swapoff -a
  if systemctl list-unit-files dphys-swapfile.service >/dev/null 2>&1; then
    run systemctl disable --now dphys-swapfile.service
  fi
  SYSCTL=/etc/sysctl.d/50-txori-kantua.conf
  LIMITS=/etc/security/limits.d/50-txori-kantua.conf
  if [ "$DRY_RUN" -eq 0 ]; then
    printf '# Txori Kantua: no dumps of processes with changed privileges.\nfs.suid_dumpable = 0\n' > "$SYSCTL"
    printf '# Txori Kantua: no memory dumps.\n* hard core 0\n' > "$LIMITS"
    sysctl --quiet --load "$SYSCTL"
  else
    log "(dry-run) write $SYSCTL and $LIMITS"
  fi
  warn "if the system uses another swap mechanism (zram, rpi-swap, fstab), review it by hand: collect_report.sh shows it"
else
  log "no changes (use --disable-swap; the report shows the current state)"
fi

log "done. Next step: deploy/provision/collect_report.sh"
