#!/usr/bin/env bash
# Installs and configures Mosquitto for Txori Kantua (issue #13).
#
#   sudo ./setup_broker.sh                 # installs, configures and creates missing credentials
#   sudo ./setup_broker.sh --rotate NAME   # generates a new password for a service
#   sudo ./setup_broker.sh --dry-run       # shows what it would do
#
# Credentials: one random password per service, generated ON the Pi.
#   /etc/mosquitto/txori-kantua.passwd        hashes, for the broker
#   /etc/txori-kantua/mqtt/<service>.env      clear-text password, for the service
# Neither goes into Git. Each service .env can only be read by root and the
# application group; systemd loads it with EnvironmentFile.
#
# STATUS: written without access to the Raspberry Pi; not run on real hardware.
set -euo pipefail

APP_USER="${TXORI_USER:-txori}"
CONFIG_DIR="${TXORI_CONFIG_DIR:-/etc/txori-kantua}"
SERVICES=(inference sensors monitor ingest station healthcheck)
HERE="$(cd "$(dirname "$0")" && pwd)"
PASSWD=/etc/mosquitto/txori-kantua.passwd
ACL=/etc/mosquitto/txori-kantua.acl
CONF=/etc/mosquitto/conf.d/txori-kantua.conf
ENV_DIR="$CONFIG_DIR/mqtt"

DRY_RUN=0
ROTATE=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --rotate) ROTATE="${2:?missing service name}"; shift 2 ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

log() { printf '[broker] %s\n' "$*"; }
die() { printf '[broker] ERROR: %s\n' "$*" >&2; exit 1; }
run() { if [ "$DRY_RUN" -eq 1 ]; then printf '[broker] (dry-run) %s\n' "$*"; else "$@"; fi; }

[ "$(uname -s)" = "Linux" ] || die "only runs on the Raspberry Pi (Linux)"
[ "$DRY_RUN" -eq 1 ] || [ "$(id -u)" -eq 0 ] || die "run with sudo"
id "$APP_USER" >/dev/null 2>&1 || [ "$DRY_RUN" -eq 1 ] || die "user $APP_USER does not exist: run deploy/provision/provision.sh first"

if [ -n "$ROTATE" ]; then
  printf '%s\n' "${SERVICES[@]}" | grep -qx "$ROTATE" || die "unknown service: $ROTATE"
fi

# --- 1. Packages ----------------------------------------------------------------
if dpkg -s mosquitto >/dev/null 2>&1 && dpkg -s mosquitto-clients >/dev/null 2>&1; then
  log "mosquitto already installed: $(mosquitto -h 2>/dev/null | head -n 1 || true)"
else
  run apt-get update
  run apt-get install -y --no-install-recommends mosquitto mosquitto-clients
fi

# --- 2. Configuration and ACL -----------------------------------------------------
log "installing configuration and ACL"
run install -o root -g root -m 0644 "$HERE/txori-kantua.conf" "$CONF"
# The ACL and the hashes are only read by the broker.
run install -o mosquitto -g mosquitto -m 0600 "$HERE/acl" "$ACL"

# --- 3. Credentials ----------------------------------------------------------------
run install -d -o root -g "$APP_USER" -m 0750 "$ENV_DIR"
if [ "$DRY_RUN" -eq 0 ] && [ ! -f "$PASSWD" ]; then
  install -o mosquitto -g mosquitto -m 0600 /dev/null "$PASSWD"
fi

make_credential() {
  local service="$1" env_file="$ENV_DIR/$1.env" password
  if [ "$DRY_RUN" -eq 1 ]; then
    log "(dry-run) generate password for $service in $env_file"
    return
  fi
  # 32 random bytes in hexadecimal: no characters that need escaping.
  password="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  # Restrictive umask BEFORE creating the file: it never exists readable by others.
  ( umask 0027
    printf 'TXORI_MQTT_USERNAME=%s\nTXORI_MQTT_PASSWORD=%s\n' "$service" "$password" > "$env_file" )
  chown root:"$APP_USER" "$env_file"
  chmod 0640 "$env_file"
  # -b receives the password as an argument: visible for an instant in root's
  # process list. Acceptable on a single-administrator machine.
  mosquitto_passwd -b "$PASSWD" "$service" "$password"
  log "credential for $service written to $env_file"
}

for service in "${SERVICES[@]}"; do
  if [ "$service" = "$ROTATE" ] || [ ! -f "$ENV_DIR/$service.env" ]; then
    make_credential "$service"
  else
    log "credential for $service already exists (use --rotate $service to change it)"
  fi
done
[ "$DRY_RUN" -eq 1 ] || chown mosquitto:mosquitto "$PASSWD"

# --- 4. Start -------------------------------------------------------------------------
run systemctl enable mosquitto
run systemctl restart mosquitto
if [ "$DRY_RUN" -eq 0 ]; then
  sleep 1
  systemctl is-active --quiet mosquitto || die "mosquitto does not start: journalctl -u mosquitto -n 50"
  log "mosquitto active"
  if [ -n "$ROTATE" ]; then
    log "restart the service that uses the $ROTATE credential so that it loads it"
  fi
fi

log "done. Check with: sudo deploy/mosquitto/check_broker.sh"
