# Detection publishing

Issue [#18](https://github.com/elenaatorralbo/txori-kantua/issues/18). Seam
between inference (David, [#16](https://github.com/elenaatorralbo/txori-kantua/issues/16)
and [#17](https://github.com/elenaatorralbo/txori-kantua/issues/17)) and the
consumers: persistence ([#19](https://github.com/elenaatorralbo/txori-kantua/issues/19))
and LCD station ([#22](https://github.com/elenaatorralbo/txori-kantua/issues/22)).

> **Status.** The publisher is implemented and tested against an in-memory
> simulated broker (`pytest tests/messaging/test_detection_publisher.py`). It
> is **not integrated with real inference**, which does not exist yet, nor
> tested against Mosquitto: that test is in `tests/broker` and runs on the Pi.
> The acceptance criteria of #18 are met only in simulation.

## For whoever produces detections (David)

All inference has to do is hand over one `InferenceResult` for each species
that passes its filter:

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

`event_id` is deterministic: it is derived from the station, the window start
and end and the scientific name. Consequences:

| Situation | Result |
|---|---|
| The same detection is published twice | Same `event_id`, same bytes; persistence keeps one |
| Inference restarts and analyses the same window again | Same `event_id` |
| The same instant arrives as a `datetime` and as a string | Same `event_id` (normalised to milliseconds) |
| Two species in the same window | Two events, two `event_id` |
| Same window and species with another confidence | Same `event_id`: it is the same observation. Persistence keeps the first one received |

The last row is a decision: if David prefers a reanalysis with another
confidence to replace the previous one, it has to be agreed before #19.

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
| A valid event reaches two independent consumers | `test_an_event_reaches_two_independent_consumers`; with a real broker, `test_detection_reaches_ingest_and_station` | In simulation; pending on the Pi |
| A retry keeps the identifier and does not change `observed_at` | `test_retry_keeps_identifier_observed_at_and_bytes`, `test_broker_down_delivers_on_return_without_changing_the_event` | In simulation |
| No message carries samples, audio paths or precise coordinates | `test_no_published_message_carries_audio_paths_or_coordinates`, `test_inference_result_has_no_fields_for_audio_or_location`, plus the negative contract examples | Verified by contract; the real traffic audit belongs to #11 |
