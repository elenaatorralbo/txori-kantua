# 0001 — Recognise birds locally with BirdNET V2.4 on LiteRT

- **Status:** Proposed
- **Proposed on:** 17/11/2026
- **Owner:** David Fernández — [DavidFernandezUD](https://github.com/DavidFernandezUD)
- **Issue:** [#8](https://github.com/elenaatorralbo/txori-kantua/issues/8)
- **Accepted on:** —

## Context

The station must recognise bird songs without sending audio anywhere
([privacy.md](../privacy.md), [ADR 0006](0006-transient-audio.md)), so
inference has to run on the Raspberry Pi 5 itself, next to capture, the
broker, ingest, the API and possibly Grafana
([ADR 0007](0007-retention.md) budgets about 800 MB and 30 % CPU for those).

Known for certain on 17/11/2026: the Pi runs Raspberry Pi OS Trixie, aarch64,
Python 3.13 ([recovery evidence](../evidence/2026-11-12-recovery/validation.md)).
The BirdNET V2.4 TFLite models load and produce correct results through our
wrapper on a desktop PC ([birdnet-feasibility.md](../birdnet-feasibility.md)).
Not known yet: latency, memory and temperature **on the Pi**.

## Decision

**Use BirdNET V2.4 (official TFLite export from Zenodo) through `ai-edge-litert`
on the Pi's CPU, analysing consecutive 3 s windows, if the Pi measurement
meets the budget below.** The precision (FP32, FP16 or INT8) and thread count
are the fastest configuration within budget, preferring fewer threads.

### Viability rule

The benchmark of #8 on the Pi declares the plan **viable** when one
configuration meets, over at least 20 windows of the authorised corpus:

| Measure | Budget | Reason |
|---|---|---|
| Inference p95 per 3 s window | ≤ 1.0 s | At most a third of each window, so capture never waits and other services keep CPU |
| Peak resident memory of the inference process | ≤ 512 MB | Leaves ADR 0007's infrastructure budget and OS headroom without disk swap (ADR 0006) |
| Temperature during 10 min at the station's pace | ≤ 80 °C, `get_throttled` = 0x0 | A throttled Pi falls behind unpredictably |
| Live run, 20 windows with the microphone | 0 capture overruns | Inference keeps the capture pace in practice |

### Plan to keep the capture pace

1. Capture and inference in separate threads with the bounded queue of
   ADR 0006 (two windows). If inference falls behind, the oldest window is
   dropped and counted: audio never accumulates.
2. If p95 is between 1 s and 3 s: still viable for the MVP, with one thread
   and a lower priority (`Nice`) so the rest of the station stays responsive;
   the dropped-window metric is shown in the health dashboard.
3. If p95 is above 3 s or memory exceeds the budget: try INT8, then analyse
   every other window (50 % coverage, declared as such), then move Grafana or
   storage to another machine ([architecture.md](../architecture.md)).
   **Audio and inference never leave the Pi.**

## Alternatives considered

| Alternative | For | Against | Why it is not chosen now |
|---|---|---|---|
| Full TensorFlow | Official BirdNET-Analyzer path | Hundreds of MB installed and in RAM on the Pi | LiteRT runs the same model files |
| `tflite-runtime` | Smaller than TensorFlow | No wheels after Python 3.11; the Pi has 3.13 | Would need another Python or a source build |
| `birdnet` / `birdnet-analyzer` packages | Maintained by the BirdNET team; file analysis, filters | File-oriented; pull pandas, pyarrow, scipy, librosa or TensorFlow | Our need is one in-memory window at a time |
| BirdNET+ V3.0 | Newer, more classes | Preview release on 17/11/2026 | Revisit after the MVP |
| Cloud API or a server on the network | Unlimited compute | Sends audio off the device | Forbidden by privacy.md |

## Consequences

- Dependencies: `numpy` and `ai-edge-litert` (extra `birdnet` in
  `pyproject.toml`); `ffmpeg` only for the evaluation corpus.
- The model files (~25–50 MB each) are downloaded by
  `deploy/provision/fetch_birdnet.sh` with fixed checksums, not stored in Git.
- Licence CC BY-NC 4.0: attribution in the documentation and dashboard;
  non-commercial use only.
- Detections are multi-label: the publisher (#18) must handle several species
  per window. Geographic/seasonal filtering (#17) is needed: without it the
  desktop run already produced an Australian species for a blackbird recording.

## Review criteria

- The Pi measurement does not meet the budget with any configuration.
- Sustained operation shows throttling or more than 5 % dropped windows.
- Recognition quality in #25 is unacceptable for the target species.
- BirdNET V2.4 files become unavailable or their licence changes.

## Evidence

- Desktop run, 17/11/2026: models, runtime, wrapper and corpus verified;
  numbers in [birdnet-feasibility.md](../birdnet-feasibility.md). **Not
  evidence of feasibility on the Pi.**
- Pending, David on the Pi: `benchmark run` (3 precisions × 1/2/4 threads),
  10-minute sustained run, `benchmark live` with the #7 microphone, privacy
  file audit. Reports go to `docs/evidence/` and the status of this ADR is
  then updated with the decision.
