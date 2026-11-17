#!/usr/bin/env bash
# Broker health check (issue #13).
#
#   sudo ./check_broker.sh            # readable output; exit code 0 if healthy
#
# Uses the "healthcheck" credential, which can only publish and read its own
# availability: a full cycle of authentication, ACL, QoS 1 publish and
# delivery, without touching any data topic. It works as a manual check and as
# a systemd ExecStartPost or timer (issue #29).
#
# Exit codes: 0 healthy; 1 the service is not active; 2 the credential is not
# accepted or nothing is delivered; 3 an anonymous client IS ACCEPTED (security
# failure).
set -u

CONFIG_DIR="${TXORI_CONFIG_DIR:-/etc/txori-kantua}"
STATION="${TXORI_STATION_ID:-station-01}"
HOST="${TXORI_MQTT_HOST:-127.0.0.1}"
PORT="${TXORI_MQTT_PORT:-1883}"
ENV_FILE="$CONFIG_DIR/mqtt/healthcheck.env"
TOPIC="txori/v1/$STATION/availability/healthcheck"

say() { printf '[check] %s\n' "$*"; }

if command -v systemctl >/dev/null 2>&1 && ! systemctl is-active --quiet mosquitto; then
  say "FAIL: the mosquitto service is not active"; exit 1
fi

[ -r "$ENV_FILE" ] || { say "FAIL: cannot read $ENV_FILE (run with sudo)"; exit 2; }
# shellcheck disable=SC1090
. "$ENV_FILE"

NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
PAYLOAD="{\"schema_version\":\"1.0\",\"station_id\":\"$STATION\",\"service\":\"healthcheck\",\"status\":\"online\",\"observed_at\":\"$NOW\"}"

# 1. An anonymous client must be rejected.
if mosquitto_pub -h "$HOST" -p "$PORT" -t "$TOPIC" -m "$PAYLOAD" -q 1 >/dev/null 2>&1; then
  say "SECURITY FAILURE: the broker accepts anonymous clients"; exit 3
fi
say "ok: anonymous client rejected"

# 2. Retained QoS 1 publish and read back with the credential.
if ! mosquitto_pub -h "$HOST" -p "$PORT" -u "$TXORI_MQTT_USERNAME" -P "$TXORI_MQTT_PASSWORD" \
     -t "$TOPIC" -m "$PAYLOAD" -q 1 -r >/dev/null 2>&1; then
  say "FAIL: the broker rejects the healthcheck credential"; exit 2
fi
RECEIVED="$(mosquitto_sub -h "$HOST" -p "$PORT" -u "$TXORI_MQTT_USERNAME" -P "$TXORI_MQTT_PASSWORD" \
            -t "$TOPIC" -q 1 -C 1 -W 5 2>/dev/null || true)"
if [ "$RECEIVED" != "$PAYLOAD" ]; then
  say "FAIL: what was published does not come back (received: ${RECEIVED:-nothing})"; exit 2
fi
say "ok: QoS 1 publish and delivery with credential"
say "broker healthy at $HOST:$PORT"
