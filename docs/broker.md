# MQTT broker: Mosquitto

Configuration and operation of the local event bus, issue
[#13](https://github.com/elenaatorralbo/txori-kantua/issues/13).

> **Status: not run against a real broker.** There is no Mosquitto on the
> development machine. It is verified **without a broker** that the connection
> does what it should (tests with a paho double and with real paho without a
> connection) and that the ACL file expresses the agreed permissions
> (simulation of topic matching). That Mosquitto enforces it that way is exactly
> what the tests in `tests/broker` check, **pending execution on the Pi**. Until
> then no acceptance criterion of #13 is met.

## Decisions

| Decision | Reason |
|---|---|
| The broker listens **only on `127.0.0.1:1883`** | Every MVP service runs on the Pi. What does not listen on the network cannot be attacked from the network |
| **No TLS** on that listener | Traffic does not leave the device. TLS on loopback adds certificates to manage without protecting anything |
| **TLS mandatory** if a network listener is opened | User and password would travel in clear text. The block is ready and commented out in the configuration; enabling it requires recording the decision here |
| **Anonymous access forbidden** | Acceptance criterion; also, the ACLs are based on the user |
| **MQTT user = service name** | Enables the rule `pattern write .../availability/%u`: each service publishes only its own availability |
| **One random password per service**, generated on the Pi | No credential goes through Git or anyone's laptop; compromising one service does not give access to another's topics |
| **Persistent sessions** and on-disk persistence | The broker queues QoS 1 messages for ingest while it restarts |
| **16 KiB** per-message limit in the broker | The same as the contract: a larger message is rejected before reaching a consumer |

## Permissions per service

Source: [`deploy/mosquitto/acl`](../deploy/mosquitto/acl). Anything not listed
is denied.

| User | Can publish | Can read | Owner |
|---|---|---|---|
| `inference` | `…/detections` | — | David / Javier |
| `sensors` | `…/environment` | — | Elena |
| `monitor` | `…/health` | `…/availability/+` | Erik |
| `ingest` | — | all of `txori/v1/#` | Javier |
| `station` | — | `…/detections`, `…/availability/+` | Elena |
| `healthcheck` | — | — | Javier |
| everyone | its own `…/availability/<user>` | its own `…/availability/<user>` | — |

If a service needs a permission it does not have, the ACL file is changed in a
PR; it is not given another service's credential.

## Installation

Requires the [provisioning](provisioning.md) to have been run first.

```bash
sudo deploy/mosquitto/setup_broker.sh --dry-run   # review
sudo deploy/mosquitto/setup_broker.sh
sudo deploy/mosquitto/check_broker.sh
```

`setup_broker.sh` installs Mosquitto, copies the configuration and ACL, and
generates the missing credentials:

| File | Content | Permissions |
|---|---|---|
| `/etc/mosquitto/conf.d/txori-kantua.conf` | Configuration | `root`, `0644` |
| `/etc/mosquitto/txori-kantua.acl` | ACL | `mosquitto`, `0600` |
| `/etc/mosquitto/txori-kantua.passwd` | Password hashes | `mosquitto`, `0600` |
| `/etc/txori-kantua/mqtt/<service>.env` | `TXORI_MQTT_USERNAME` and `TXORI_MQTT_PASSWORD` | `root:txori`, `0640` |

None of the last three goes into Git (`.gitignore` already excludes `.env.*`).
Changing a password: `sudo deploy/mosquitto/setup_broker.sh --rotate sensors`
and restart the service that uses it.

## How a service connects

```python
from txori_kantua import messaging as m

settings = m.MqttSettings.from_env(service="sensors")   # reads TXORI_MQTT_* and TXORI_STATION_ID
with m.MqttConnection(settings) as mqtt:
    mqtt.publish("environment", event)
```

The service receives its variables with `EnvironmentFile=` in its systemd unit
([#29](https://github.com/elenaatorralbo/txori-kantua/issues/29)). The
connection takes care of:

- Registering the `offline` Last Will and publishing a retained `online` on
  connecting.
- Reconnecting with a backoff between 1 and 60 s and repeating the
  subscriptions.
- Validating against the contract what it publishes and what it receives. An
  invalid received message is counted and logged (size and reason, **never its
  content**) without stopping the consumer.
- Bounding the outgoing queue while disconnected to 1,000 messages; when full,
  `publish` returns `accepted=False` instead of growing.

## Health check

`deploy/mosquitto/check_broker.sh` runs a full cycle with the `healthcheck`
credential: it checks that the service is active, that an **anonymous client
is rejected**, and that a retained QoS 1 publish comes back through a
subscription.

| Exit code | Meaning |
|---|---|
| 0 | Healthy |
| 1 | The `mosquitto` service is not active |
| 2 | It does not accept the credential, or does not deliver what is published |
| 3 | **It accepts an anonymous client**: security failure |

## Verification of the acceptance criteria

On the Pi, with the broker configured:

```bash
sudo TXORI_BROKER_TESTS=1 \
     TXORI_BROKER_RESTART_CMD="systemctl restart mosquitto" \
     /opt/txori-kantua/venv/bin/python -m pytest /opt/txori-kantua/app/tests/broker -v
```

| Criterion of #13 | Test | Status |
|---|---|---|
| Authorised publisher publishes and authorised consumer receives a v1 event | `test_authorised_publisher_publishes_and_authorised_consumer_receives` | Pending execution on the Pi |
| Anonymous client and writes outside the ACL are rejected | `test_anonymous_client_is_rejected`, `test_wrong_password_is_rejected`, `test_write_outside_acl_reaches_no_consumer`, `test_a_service_cannot_declare_another_one_down`, `test_read_outside_acl_receives_nothing` | Pending execution on the Pi |
| Restarted broker allows reconnection and updates availability | `test_after_restarting_the_broker_clients_reconnect_and_availability_updates`, `test_last_will_publishes_offline_if_the_service_dies` | Pending execution on the Pi |

Verified without a broker, on the development machine (`pytest tests/messaging`):
Last Will and `online` compliant with the contract, reconnection that repeats
subscriptions, bounded outgoing queue with real paho, invalid messages that do
not stop the consumer and permissions of the ACL file.

## Known limitations

- With MQTT 3.1.1 the broker **acknowledges** a publish denied by the ACL and
  then discards it: the producer does not find out. That is why the test checks
  that the message is not delivered, not that the publish fails.
- The `observed_at` of an `offline` coming from the Last Will is the connection
  time, not the failure time. Whoever needs to know when a service went down
  uses their own reception time.
- `mosquitto_passwd -b` receives the password as an argument, visible for an
  instant in root's process list.
- The Mosquitto and `paho-mqtt` versions validated on the Pi are **not
  recorded**; write them here when running the verification.
