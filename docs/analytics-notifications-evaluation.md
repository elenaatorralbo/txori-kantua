# Evaluation: anomaly alerts, Telegram, dawn chorus and period comparisons (issue #34)

**Optional, outside the MVP** ([scope](mvp-scope.md): these need history
that will not exist on 11/12, and Telegram adds a credential and an external
service). This document gives each proposal a hypothesis, the minimum data,
an estimate and a decision. Nothing here is implemented.

All four proposals require a distinction beyond the telemetry aggregates of
[#28](https://github.com/elenaatorralbo/txori-kantua/issues/28):
**absence of observations is not an ecological change.** A drop in detections
means something only when the station was listening. Every statistic below
is therefore computed **per verified analyzed-audio minute** for bird rates. This denominator
is not supplied by current telemetry coverage and remains a missing prerequisite.
Environmental statistics instead require valid readings of the metric evaluated.

## Common data requirements

| Requirement | Value (proposal) | Why |
|---|---|---|
| Verified analyzed audio in a day | ≥ 80 % of its minutes; currently unknown, not telemetry coverage of #28 | Below that, a quiet day and a station that was off look the same |
| Detection quality | Confidence ≥ the threshold set in #17, after the location/season filter | The #8 desktop run showed a blackbird never identified and an Australian lorikeet as top-1: unfiltered counts would produce false trends |
| Rate, not count | Detections per verified analyzed-audio hour | Compares periods with different listening time |
| Model version | Same `model.version` in both periods | A model change is not a change in the birds |

## 1. Environmental anomaly alerts

- **Hypothesis:** an unusual reading (sudden pressure drop, temperature far
  from the recent norm) is worth a notification, either as weather context or
  as a sign of a sensor fault.
- **Method:** rolling median and median absolute deviation over the previous
  7 days at the same hour, using only quality `ok` readings. A reading is
  anomalous when it is more than 4 MAD away for 3 consecutive readings. A
  pressure drop counts when it exceeds 3 hPa in 3 h (a common weather rule).
- **Minimum data:** 7 days with ≥ 80 % valid expected readings of the specific metric before the first alert. No
  alert while the window is incomplete.
- **False alerts:** sensor faults look like anomalies. #4 showed the DHT11
  drifting 4–5 degC above the BME280. Before any notification, compare
  against the second sensor or Euskalmet (#33). Evaluate on recorded history:
  alerts per week and the share confirmed by the reference.
- **Estimate:** 3 points.
- **Decision:** postpone until after v1.0.0. The useful first step is a
  **sensor-fault check** (DHT11 against BME280), not a weather alert.

## 2. Telegram notifications

- **Hypothesis:** a daily summary or a rare-species message keeps
  volunteers engaged without them opening the dashboard.
- **Design rules (mandatory if ever built):**
  - **Off by default.** It only starts when `TXORI_TELEGRAM_ENABLED=1`
    *and* a bot token and chat id are configured. Missing configuration is a
    disabled feature, not an error, and nothing is sent.
  - The token lives in the root-owned `.env` file (mode 0600). It never goes
    to Git, to logs (log the chat alias, never the token or the full URL) or
    to the MQTT/REST contracts.
  - **Opt-in per recipient:** only chats that subscribed explicitly. No
    personal data is stored apart from the chat id.
  - No location, no audio, no precise time of a sensitive species. Daily
    summary content only: species and counts of the local day.
  - Rate limit (e.g. one message per hour, one daily summary) and a
    bounded queue: an outage does not flood the chat when it recovers.
- **Minimum data:** none technically. Without #17 filtering, messages
  would spread false positives.
- **Estimate:** 2 points for the daily summary, 1 more for opt-in commands.
- **Decision:** postpone. It is the easiest to build but adds the only
  credential and outgoing service of the project.

## 3. Dawn chorus analysis

- **Hypothesis:** song activity peaks around sunrise, and the peak shifts
  with the season. It is a visible, explainable pattern for the demonstration.
- **Method:** detection rate per verified analyzed-audio 10-minute bin, relative to
  **local sunrise** computed for a generalised location (municipality,
  never the exact station, see #33), from −60 to +180 min. Show the median
  over days and its spread, not one day.
- **Minimum data:** ≥ 14 days, each with ≥ 80 % verified analyzed-audio coverage **in the dawn
  window** specifically; enough detections per bin to show a shape (a
  proposal: 20 or more). Bins without coverage are gaps, never zeros.
- **Pitfalls:** traffic or wind at dawn changes detectability, not birds.
  The clock change moves clock time, not sunrise-relative time, which is why
  sunrise-relative bins are used.
- **Estimate:** 3 points.
- **Decision:** the most promising one. Revisit after two weeks of real
  data with the #17 filter in place.

## 4. Period comparisons

- **Hypothesis:** comparing weeks or months shows seasonal changes in
  species and activity.
- **Method:** per species, detections per verified analyzed-audio hour in each period, with
  a confidence interval (Poisson rate). Report "no difference shown" when the
  intervals overlap. Never report a percentage change from tiny counts.
- **Minimum data:** both periods with ≥ 80 % verified analyzed-audio coverage, the same model
  version and filter settings, and ≥ 10 detections of the species in the
  larger period.
- **Pitfalls:** this is where "absence of observations" turns into false
  ecology. A week with the station off for three days reads as a drop if
  raw counts are used. The coverage normalisation and the minimum coverage
  are therefore mandatory, not refinements.
- **Estimate:** 2 points, on top of #28's aggregates.
- **Decision:** postpone. With the course's data volume, most comparisons
  would honestly say "no difference shown".

## Summary

| Proposal | Hypothesis | Minimum data | Estimate | Decision |
|---|---|---|---|---|
| Anomaly alerts | Unusual readings matter | 7 days ≥ 80 % coverage | 3 | Postpone; start with a sensor-fault check |
| Telegram | Summaries keep volunteers engaged | #17 filter in place | 2–3 | Postpone; off by default, opt-in |
| Dawn chorus | Activity peaks around sunrise | 14 days, dawn coverage ≥ 80 % | 3 | Most promising; revisit after real data |
| Period comparisons | Seasons change species and activity | Both periods ≥ 80 %, same model | 2 | Postpone |

## Acceptance criteria

| Criterion | Where |
|---|---|
| Each proposal has hypothesis, minimum data, estimate and decision | Sections 1–4 and summary |
| Telegram is not activated and publishes no credentials without explicit configuration | Section 2, design rules |
| The design separates absence of observations from real ecological changes | Common requirements (rate per covered hour, minimum coverage), sections 3–4 |

## Review correction

Telemetry minutes from environmental or health events, including failed capture
or inference, never establish listening coverage. Until an explicit completed-
window coverage contract is implemented, bird rates and ecological comparisons
remain disabled. Service availability alone is also insufficient. This addresses
the coverage prerequisite raised in PR #56; no notification is activated.
