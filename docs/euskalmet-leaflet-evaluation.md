# Evaluation: Euskalmet context and Leaflet nature maps (issue #33)

**Optional, outside the MVP.** This document is the research result that #33
asks for. It does not commit anyone to building anything: whether to build is
a separate decision, recorded at the end. Sources were checked on 17/11/2026;
the points marked *to confirm* must be checked on the official page before
any implementation.

## 1. Euskalmet weather context

**What it would add.** Outdoor conditions from the nearest Euskalmet station
(temperature, humidity, pressure, precipitation, wind) shown next to our own
readings, and a reference to validate our sensors. The second use is the
most valuable one today. #4 needs reference values, and the BME280 measures
absolute pressure that can be compared with a nearby station once both are
reduced to the same altitude.

| Aspect | Finding |
|---|---|
| Access | REST API published on Open Data Euskadi ([API page](https://opendata.euskadi.eus/api-euskalmet/-/api-de-euskalmet/)). It needs an API key obtained by registering on the portal. The exact authentication flow is *to confirm* on the official page: third-party directories disagree on the base URL. |
| Licence | Open Data Euskadi publishes under **CC BY 4.0** according to its [datos.gob.es entry](https://datos.gob.es/es/iniciativas/open-data-euskadi): reuse is allowed with **attribution of the source** ("Euskalmet – Basque Government"). Whether the API data carry exactly that licence is *to confirm*. |
| Limits | No published request quota found. Hourly polling for one station is negligible, but treat the limit as unknown and cache the responses. |
| Privacy | Only outgoing requests for a public station. Nothing of ours is sent apart from the key. The key is a credential: it goes to the `.env` file, never to Git (CONTRIBUTING). |
| Dependency | An external service on the Internet. The station works offline by design (ADR 0003, local SQLite), so this can only be an **optional** dashboard layer. If it fails, the panel shows "no external data". It must never block ingest or the dashboard. |

**Effort (relative points, like the backlog):** 3. That covers registration
and key handling (1), a client with cache and failure handling (1), and a
panel plus attribution (1). One more point for a documented pressure
comparison (altitude reduction).

**Risks.** An undocumented API change or quota; a key leaked in a log;
confusion between outdoor and indoor values (the panel must label the
source clearly); licence terms different from the portal default.

## 2. Leaflet map of nearby natural areas

**What it would add.** A map for visitors with the area around the station
and nearby protected spaces, as context for the detected species.

| Aspect | Finding |
|---|---|
| Library | Leaflet (BSD-2). Only the base map tiles raise usage questions. |
| Base map | OpenStreetMap tiles need the "© OpenStreetMap contributors" **attribution**. The OSMF tile policy forbids heavy use without permission and requires a valid Referer/User-Agent ([OSM wiki: blocked tiles](https://wiki.openstreetmap.org/wiki/Blocked_tiles), [attribution](https://wiki.openstreetmap.org/wiki/Lacking_proper_attribution)). A classroom demo is light use. A public deployment should use another tile provider or self-hosted tiles. |
| Natural areas | Protected-space layers (e.g. Natura 2000) are published by the Basque Government and the EU; the licence of the specific layer is *to confirm* when choosing it. |
| **Sensitive locations** | The MQTT contract forbids precise coordinates, and `station_id` is non-geographic. A map must **not** place detections: the location of rare or breeding birds is sensitive. Show only a generalised area (e.g. a 10 km grid cell or the municipality) and never per-detection points. |
| Offline | Without Internet the tiles do not load. The map is optional, like the Euskalmet panel. |

**Effort:** 3. That covers a static page or Grafana panel with Leaflet (1),
a generalised station area and attribution (1), and choosing and checking a
natural-area layer and its licence (1).

**Risks.** Revealing sensitive bird locations (highest: a design rule,
not a technical detail); being blocked by the OSM tile servers; layer
licences that do not allow redistribution.

## 3. Comparison and decision

| | Value | Effort | Main risk | MVP dependency |
|---|---|---|---|---|
| Euskalmet context | **High** for sensor validation, medium for visitors | 3–4 | External API and key handling | None: optional panel |
| Leaflet map | Medium for visitors | 3 | Revealing sensitive locations | None: optional page |

**Decision (proposal for the team):**

1. **Do not implement either in the MVP.** Neither is needed by any MVP
   criterion, and both add an Internet dependency to an offline system.
2. **Use Euskalmet now, manually, as a reference** for the #4 reports
   (pressure and temperature at the same time from the nearest station,
   written in the report with attribution). This takes no code.
3. If there is time after the v1.0.0 release (#32), build the Euskalmet panel
   first. The map comes after it, and only with the generalised-area rule.

No prototype was built: the issue allows "if it exists", and the decision
above does not need one.

## Acceptance criteria

| Criterion | Where |
|---|---|
| Document compares value, effort and risks of both proposals | Sections 1–3 |
| A prototype, if it exists, identifies external data and attribution | No prototype; attribution requirements recorded for both data sources |
| No MVP dependency requires external services from this research | Section 3, decision 1; both are optional layers that fail closed |
