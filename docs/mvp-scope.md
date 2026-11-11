# MVP scope

Status: proposal by Javier ([#9](https://github.com/elenaatorralbo/txori-kantua/issues/9)),
pending team approval in planning. Date: 10/11/2026.

This document answers a single question: **what has to work on 11/12/2026 to
be able to say the MVP is accepted**, and what is explicitly left out. Nothing
here is implemented or tested because it is written down.

## In the MVP

The MVP is three capabilities. A capability is in only if it has a verifiable
acceptance criterion in [acceptance.md](acceptance.md).

### 1. Physical sensor → storage → dashboard

- Real temperature, humidity, pressure and light readings from the sensors
  connected to the Raspberry Pi 5.
- Publication of those readings as validated MQTT v1 events.
- Persistence with deduplication and a traceable identifier.
- Grafana dashboard that shows those readings and makes it possible to follow
  **one concrete physical change** from the sensor to the chart using its
  `event_id`.

### 2. Local bird recognition

- Audio capture in bounded windows in RAM, without writing audio to disk.
- Local inference with BirdNET and filtering by confidence and context.
- Publication of detections as MQTT v1 events, persisted and visible on the
  dashboard.
- With an authorised corpus if there are no real birds during the
  demonstration, and **declared as such**, without presenting it as live
  detection.

### 3. Interactive station

- PIR or touch switch the LCD screen on.
- The LCD shows information about the latest detection in ES/EU/EN.
- The LCD distinguishes "no recent data" from "no detections", and switches
  off after 20 ±1 s of inactivity.

### Cross-cutting, also in

- **Verified privacy:** audit of disk, persistent memory, payloads and traffic
  without audio ([#11](https://github.com/elenaatorralbo/txori-kantua/issues/11)).
- **Recovery:** 60 s broker outage, storage down, missing sensor and two full
  reboots without manual intervention
  ([#26](https://github.com/elenaatorralbo/txori-kantua/issues/26),
  [#29](https://github.com/elenaatorralbo/txori-kantua/issues/29)).
- **Reproducibility:** another team member installs the system following the
  documentation ([#30](https://github.com/elenaatorralbo/txori-kantua/issues/30)).
- **Versioned contracts** and automated tests
  ([#10](https://github.com/elenaatorralbo/txori-kantua/issues/10),
  [#27](https://github.com/elenaatorralbo/txori-kantua/issues/27)).

## Outside the MVP

"Outside" means that **it is not worked on until the MVP is accepted**, even if
there is time left. If anything on this list appears in a PR before 11/12, it is
rejected for scope, not for quality.

| Outside the MVP | Reason | Issue |
|---|---|---|
| Euskalmet integration | External dependency with no value for the acceptance criteria | [#33](https://github.com/elenaatorralbo/txori-kantua/issues/33) |
| Leaflet nature maps | Additional interface not required | [#33](https://github.com/elenaatorralbo/txori-kantua/issues/33) |
| Anomaly alerts, dawn chorus, period comparisons | They require history that will not exist on 11/12 | [#34](https://github.com/elenaatorralbo/txori-kantua/issues/34) |
| Notifications to Telegram or other channels | Adds credentials and an external service | [#34](https://github.com/elenaatorralbo/txori-kantua/issues/34) |
| Own web frontend on Flask | Grafana already covers visualisation ([ADR 0004](adr/0004-visualization.md)) | — |
| Exposing the system outside the local network | Requires TLS, authentication and limits that do not fit in the schedule | — |
| User authentication in the API | The API is only exposed on a restricted local network | — |
| Several stations or data federation | [ADR 0003](adr/0003-persistence.md) assumes a single writer | — |
| Mobile application | It was never in scope | — |
| Storing or transmitting audio, speaker identification, transcription | Forbidden by [privacy.md](privacy.md), not a scope cut | — |
| Retraining or fine-tuning the model | Outside the available time; BirdNET is used as is | — |
| InfluxDB | Discarded in [ADR 0003](adr/0003-persistence.md) | — |
| High availability, replication or failover | One station, one device | — |

## What is cut first if time runs out

Agreed cutting order, from what goes first to what goes last. Cutting means
**documenting the limitation**, not pretending it works.

1. The two optional investigations
   ([#33](https://github.com/elenaatorralbo/txori-kantua/issues/33),
   [#34](https://github.com/elenaatorralbo/txori-kantua/issues/34)): already out.
2. Daily aggregates and time statistics
   ([#28](https://github.com/elenaatorralbo/txori-kantua/issues/28)): the
   dashboard works without them on raw data within retention.
3. Dashboard richness: fewer panels, same data.
4. LCD multilingualism: degrade to ES plus scientific name, keeping the
   structure to add EU and EN.
5. Depth of detection filtering
   ([#17](https://github.com/elenaatorralbo/txori-kantua/issues/17)): a fixed
   confidence threshold instead of a seasonal and geographic filter.

**Never cut**, because they are the definition of the MVP or a non-negotiable
constraint: the sensor → dashboard flow, privacy verification, recovery after
reboot and event deduplication. If any of these is not met, the MVP is declared
incomplete with its limitations and **`v1.0.0` is not published**
([#32](https://github.com/elenaatorralbo/txori-kantua/issues/32)).

## Global acceptance condition

The MVP is accepted when **every** gate in [acceptance.md](acceptance.md) has
linked, dated evidence reviewed by someone other than whoever produced it.
Reaching 11/12 is not an acceptance condition.
