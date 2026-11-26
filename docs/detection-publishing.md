# Detection publishing

Issue [#18](https://github.com/elenaatorralbo/txori-kantua/issues/18). Seam
between inference (David, [#16](https://github.com/elenaatorralbo/txori-kantua/issues/16)
and [#17](https://github.com/elenaatorralbo/txori-kantua/issues/17)) and the
consumers: persistence ([#19](https://github.com/elenaatorralbo/txori-kantua/issues/19))
and LCD station ([#22](https://github.com/elenaatorralbo/txori-kantua/issues/22)).

The audio `PublishingPipeline` connects the existing `Inference` output to MQTT
without rebuilding its events. Tests cover synthetic inference, broker outages,
SQLite deduplication and the LCD consumer. This does not establish recognition
quality or microphone/hardware acceptance on the Raspberry Pi.

## Existing audio pipeline

```python
from txori_kantua.audio.pipeline import Inference, PublishingPipeline, WindowQueue
from txori_kantua.messaging import DetectionPublisher, MqttConnection, MqttSettings

windows = WindowQueue(capacity=2)
inference = Inference(model, detection_filter, station_id)
with MqttConnection(MqttSettings.from_env(service="inference")) as connection:
    pipeline = PublishingPipeline(windows, inference, DetectionPublisher(connection))
    pipeline.run(stop)
```

The capture producer supplies `Window` objects to `windows` from another thread;
`model`, `detection_filter`, `station_id` and the stop event are supplied by the
application. Stop capture before shutting down the worker. `run` wipes queued
PCM on exit; inference wipes each processed buffer even on conversion/model
failure. Model failures propagate to the caller for supervision.

`step()` handles one queued window and returns its original metadata events.
The worker also calls `flush()` on idle ticks, so recovery needs no new bird.
`publish_event(event)` validates the contract, station and payload size before
sending, and keeps a private copy for retries. Caller mutations cannot alter
pending events. Use the publisher from one worker thread. Queue acceptance is
not proof of broker acknowledgement; pending metadata is lost on process exit.

## For whoever produces detections (David)

External adapters that do not already build v1 events can still hand over one
`InferenceResult` per accepted species:

```python
from txori_kantua import messaging as m

connection = m.MqttConnection(m.MqttSettings.from_env(service="inference"))
connection.start()
publisher = m.DetectionPublisher(connection)

# for each detection accepted after the filtering of #17:
publisher.publish(m.InferenceResult(
    scientific_name="Turdus merula",
    confidence=0.87,
    window_start=start,         # timezone-aware datetime, or RFC 3339 with Z
    window_end=end,
    model_name="BirdNET",
    model_version=version,      # the real version of the loaded model
))

# in the main loop, when there are no new detections:
publisher.flush()
```

- `publish` **does not block**: if the broker is not there, the event waits in
  the outgoing queue and goes out on reconnection.
- `publish` raises `MessagingError` if the result cannot form a valid event
  (confidence outside 0–1, a name that is not scientific, an empty window). It
  is a defect of the caller: it is not silenced.
- `InferenceResult` has, on purpose, no field for samples, file paths or
  coordinates. If inference needs to pass something else, the contract is
  changed ([contracts/README.md](../contracts/README.md)); a field is not added
  here.
- Credentials arrive through the environment (`TXORI_MQTT_*`,
  `TXORI_STATION_ID`); see [broker.md](broker.md).

## Identity and retries

For pipeline events, `publish_event` preserves `event_id`, `observed_at`, model
version and all other fields exactly. The existing inference ID uses station,
window timestamp, scientific name and model version. Do not convert these events
to `InferenceResult`, which would generate a different ID.

The legacy `publish(InferenceResult)` API retains its existing identity rule
(station, normalized window start/end and scientific name) for compatibility.
For that API:

| Situation | Result |
|---|---|
| The same detection is published twice | Same `event_id`, same bytes; persistence keeps one |
| Inference restarts and analyses the same window again | Same `event_id` |
| The same instant arrives as a `datetime` and as a string | Same `event_id` (normalised to milliseconds) |
| Two species in the same window | Two events, two `event_id` |
| Same window and species with another confidence | Same `event_id`; storage rejects a conflicting payload and retains the original |

A changed payload under an existing ID is a conflict, not a retry. Neither
publishing API silently updates a stored observation.

## What happens without a connection

1. The event goes into the connection's outgoing queue (1,000 messages).
2. If that queue is full, it stays pending in the publisher (another 1,000) and
   is retried with `flush()`.
3. If that is also full, **the oldest** is discarded, counted in
   `publisher.stats["dropped"]` and a warning with its `event_id` is logged.

Everything in memory and metadata only: about 400 bytes per event, less than
1 MB in the worst case. There is no queue on disk.

## "Latest detection" on a separate topic: not implemented

The issue makes it conditional on approval, and it has not been approved.
Current state, according to [mqtt.md](mqtt.md): the LCD subscribes to
`…/detections` and keeps the latest valid one in RAM.

The drawback is that, after restarting, the LCD knows nothing until the next
detection. If Elena needs it for #22, the proposal is a retained topic
`txori/v1/{station_id}/detections/latest` with the same event, which the LCD
must expire by `observed_at` (mqtt.md proposal: 5 minutes). It requires
approving it, adding it to the contract with its examples and to the ACL.
Until then nothing retained is published with detections.

## Acceptance criteria

| Criterion of #18 | Test | Status |
|---|---|---|
| A valid event reaches two independent consumers | `test_an_event_reaches_two_independent_consumers`; with a real broker, `test_detection_reaches_ingest_and_station` | Simulation and local Mosquitto; Raspberry deployment pending |
| A retry keeps the identifier and does not change `observed_at` | `test_retry_keeps_identifier_observed_at_and_bytes`, `test_broker_down_delivers_on_return_without_changing_the_event` | Simulation and local Mosquitto restart |
| No message carries samples, audio paths or precise coordinates | `test_no_published_message_carries_audio_paths_or_coordinates`, `test_inference_result_has_no_fields_for_audio_or_location`, plus the negative contract examples | Verified by contract; the real traffic audit belongs to #11 |

## Reproduce with local Mosquitto, without a Raspberry Pi

From the repository root, with Docker running:

```sh
docker build -f deploy/ci/broker.Dockerfile -t txori-local-broker-test .
docker run --rm --network none txori-local-broker-test
```

The build needs internet access for dependencies. The test container runs as an
unprivileged user, has no external network or published ports, and uses generated
temporary credentials with the repository ACL. The build context excludes Git
metadata, local environments and credentials. Versions are resolved during the
build; this is a repeatable procedure, not a locked production image.

The harness runs real-broker authentication/ACL/Last Will checks, then sends
synthetic PCM through inference/filtering, MQTT, SQLite/API and the LCD controller.
It verifies duplicate suppression and recovery after a 60-second broker outage.
The standalone restart pytest is skipped because the harness owns the broker
process and performs that restart itself. No microphone, real BirdNET weights,
physical LCD or Raspberry system services are tested.

Validation on 26 November 2026: macOS suite **595 passed, 10 skipped**
(4.80 s). In the local Linux ARM64 container (Python 3.13, Mosquitto 2.0.21,
paho-mqtt 2.2.0), **8 broker tests passed**, with the standalone restart test
skipped in favour of the harness restart. The harness returned `PASS` at
`2026-11-26T10:13:48.054Z`: outage 60 seconds, four LCD-consumer deliveries,
one stored detection, and `inference_to_lcd`/`broker_restart` both `PASS`.
These are synthetic input/model results against real Mosquitto, not physical
Raspberry or BirdNET accuracy evidence.
