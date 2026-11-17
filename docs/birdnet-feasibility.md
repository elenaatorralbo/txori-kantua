# BirdNET feasibility on the Raspberry Pi 5

Procedure and findings of issue [#8](https://github.com/elenaatorralbo/txori-kantua/issues/8).
The decision is recorded in [ADR 0001](adr/0001-edge-ai-birdnet.md).
Depends on [#7](https://github.com/elenaatorralbo/txori-kantua/issues/7) (capture)
for the live check only; the corpus benchmark does not need a microphone.

> **Status: not run on the Raspberry Pi.** The benchmark ran on a desktop
> PC on 17/11/2026 with the real BirdNET models and the real corpus. Those
> numbers prove that the tooling, the model files and the corpus work. They
> say **nothing about the Pi's latency, memory or temperature**, so no
> acceptance criterion of #8 is met yet.

## Selection

| Choice | Selected | Why | Rejected alternatives |
|---|---|---|---|
| Model | BirdNET **V2.4** "GLOBAL 6K" (6 522 classes, 3 s at 48 kHz) | The stable acoustic model; V3.0 was still a preview on Zenodo | BirdNET+ V3.0 preview (11K): not final, ONNX/PyTorch oriented |
| Distribution | Official TFLite exports, [Zenodo 10.5281/zenodo.15050749](https://doi.org/10.5281/zenodo.15050749), in FP32, FP16 and INT8 | Same artefacts the official `birdnet` package downloads; fixed checksums | Copies in third-party repositories |
| Runtime | **`ai-edge-litert`** (Google LiteRT, successor of TFLite) with its XNNPACK CPU delegate | Has aarch64 wheels for **Python 3.13**, the Python of the Pi's Raspberry Pi OS Trixie | `tflite-runtime` (no wheels after Python 3.11); full TensorFlow (hundreds of MB); `birdnet-analyzer` (requires TensorFlow, librosa); the `birdnet` package (pulls pandas, pyarrow, scipy, onnxruntime) |
| Wrapper | Own ~200-line module `txori_kantua.audio.birdnet` | Takes in-memory arrays (ADR 0006), no files; exposes exactly what the contract needs | The libraries above analyse files and add heavy dependencies |
| Decoding of the evaluation corpus | `ffmpeg` through a pipe into memory | Any format, resampling to 48 kHz included | librosa/scipy: large dependencies only for the benchmark |

### Licences

| Item | Licence | Consequence for us |
|---|---|---|
| BirdNET V2.4 model files | **CC BY-NC 4.0** (Zenodo record) | Allowed for this non-commercial university project, with attribution. A commercial reuse of the station would need another licence. Not committed to Git |
| `ai-edge-litert` | Apache 2.0 | No restriction |
| Corpus recordings | CC BY-SA 4.0 (Xeno-canto, via Wikimedia Commons) | Credit each author (manifest and report do); not redistributed by us |

## The evaluation corpus

Five recordings of common species in the Basque Country, chosen for licence
clarity and a known species, not for difficulty. Listed in
[`src/txori_kantua/audio/corpus.json`](../src/txori_kantua/audio/corpus.json)
with author, licence, source and SHA-256. Total ≈ 209 s → **71 windows** of 3 s
(the criterion asks for at least 20).

| Id | Species | Author | Licence |
|---|---|---|---|
| XC442745 | *Turdus merula* | James Ray | CC BY-SA 4.0 |
| XC507922 | *Erithacus rubecula* | Marie-Lan Taÿ Pamart | CC BY-SA 4.0 |
| XC405790 | *Parus major* | Dimitǎr Boevski | CC BY-SA 4.0 |
| XC405787 | *Fringilla coelebs* | Dimitǎr Boevski | CC BY-SA 4.0 |
| XC269087 | *Troglodytes troglodytes* | Alexander Kurthy | CC BY-SA 4.0 |

"Without voices" is checked, not assumed: the benchmark reports the highest
score of BirdNET's own *Human vocal / non-vocal / whistle* classes per
recording. All five scored 0.00. This is a screening aid, not a guarantee.

The files are downloaded to `~/.cache/txori-kantua/corpus/` and verified by
hash. They are an external evaluation fixture, not station audio; the privacy
audit can exclude them with `--allow-manifest src/txori_kantua/audio/corpus.json`.

## Running it on the Pi

```bash
# Once: decoder, runtime and models (models go to /opt/txori-kantua/models).
sudo apt install ffmpeg
pip install -e ".[birdnet,dev]"            # inside the project's virtual environment
sudo deploy/provision/fetch_birdnet.sh
TXORI_BIRDNET_MODEL_DIR=/opt/txori-kantua/models/birdnet-v2.4 pytest -m model

B="python -m txori_kantua.audio.benchmark"
M=/opt/txori-kantua/models/birdnet-v2.4

# 1. Download and verify the corpus.
$B fetch

# 2. Latency, memory and temperature: three precisions x 1, 2, 4 threads,
#    back to back (worst case). About 71 x 9 inferences.
$B run --model-dir $M --threads 1 2 4 --json bench.json > docs/evidence/YYYY-MM-DD-issue-8-benchmark.md

# 3. Sustained load, chosen configuration, 10 minutes at the station's pace:
#    temperature and throttling with the case and cooling actually used.
$B run --model $M/int8/audio-model-int8.tflite --threads 2 --realtime --sustain-seconds 600 \
    > docs/evidence/YYYY-MM-DD-issue-8-sustained.md

# 4. Capture pace: microphone and inference together (needs #7).
$B live --model $M/int8/audio-model-int8.tflite --threads 2 --windows 20 \
    > docs/evidence/YYYY-MM-DD-issue-8-live.md

# 5. Privacy: nothing written apart from the authorised corpus.
python -m txori_kantua.privacy.audit files --since <start> --allow-manifest src/txori_kantua/audio/corpus.json
```

Record in the report: power supply, cooling and case (they change the
temperature), whether Grafana/Mosquitto were running, and the swap mechanism
(`swapon --show`; ADR 0006 expects zram only). Each report already contains
the evidence header, the exact configuration and the model checksums.

### What the benchmark measures

| Metric | How |
|---|---|
| Inference latency p50/p95/max | Wall time of `invoke()` plus the score sigmoid, per window, after 2 warm-up windows |
| Real-time factor | 3 s ÷ p95 latency (above 1 means faster than real time) |
| CPU | Process CPU time ÷ wall time during inference (1.0 = one core busy) |
| Memory | Resident memory after loading and the process high-water mark (`VmHWM`, reset per configuration). Includes the decoded corpus (≈ 41 MB) |
| Temperature, clock, throttling | `thermal_zone0` and `scaling_cur_freq` after each window; `vcgencmd get_throttled` before and after |
| Sanity of the results | Per recording: windows where the expected species is the top-1 at score ≥ 0.5, best score of the expected species, most frequent top-1 species, best human-voice score |

### Budget used for the decision

From ADR 0001, configurable on the command line: **p95 ≤ 1 s** per 3 s window
(inference uses at most a third of the time, leaving room for capture, the
broker, ingest and Grafana), **peak RSS ≤ 512 MB** (ADR 0007 reserves about
800 MB for infrastructure), **temperature ≤ 80 °C** and **no throttling**.

## Mapping to the acceptance criteria

| Criterion of #8 | How it is checked | Status |
|---|---|---|
| Results of at least 20 windows and the exact configuration | Benchmark report: 71 windows, model checksums, runtime version, threads, pace, corpus manifest version | Tool ready; desktop run done; **Pi run pending** |
| p50/p95 inference and maximum memory | Results table and `--json` | Same |
| Viable/not viable decision with evidence and a plan to keep the capture pace | ADR 0001 decision rule + sustained and live runs | Rule and plan written; **decision pending Pi numbers** |

## Off-Pi run (tool verification only)

17/11/2026, AMD Ryzen 7 5800X (16 threads), Debian 12 x86_64, Python 3.11.2,
ai-edge-litert 2.3.0, 71 windows, back to back. Full output was produced by
`benchmark run --threads 1 2 4`.

| Model | Threads | p50 (ms) | p95 (ms) | Peak RSS (MB) |
|---|---|---|---|---|
| FP32 | 1 | 29 | 41 | 224 |
| FP32 | 4 | 32 | 34 | 223 |
| FP16 | 1 | 29 | 42 | 293 |
| FP16 | 4 | 24 | 33 | 329 |
| INT8 | 1 | 29 | 43 | 214 |
| INT8 | 2 | 25 | 28 | 215 |

A desktop core is several times faster than a Pi 5 core, so these latencies
cannot be transferred. What does transfer:

- **The models load and give sensible results through our wrapper.** Robin,
  great tit, chaffinch and wren are top-1 in most windows with scores
  0.99–1.00, with the same results in FP32, FP16 and INT8.
- **The blackbird recording is never recognised** (best score 0.25–0.34), and
  in one or two windows the top-1 is *Trichoglossus moluccanus*, an
  Australian lorikeet. That is the kind of false positive the location and
  season filter of [#17](https://github.com/elenaatorralbo/txori-kantua/issues/17)
  removes with BirdNET's meta-model (already included in each model archive).
  It also shows why `confidence` must be presented as a score.
- **FP16 uses ~70–100 MB more memory than FP32/INT8**, because it is expanded
  to FP32 at load time; INT8 is the smallest.
- Live mode with a real USB interface (no microphone attached): 5/5 windows,
  0 capture overruns, inference p95 45 ms.

## Answers for the detection contract

Requested in [interfaces.md](interfaces.md) ("What Javier needs from David").
Proposals for [#16](https://github.com/elenaatorralbo/txori-kantua/issues/16)
and [#18](https://github.com/elenaatorralbo/txori-kantua/issues/18), to agree
with Javier; nothing in the schema is changed by this issue.

| Question | Answer from the model |
|---|---|
| Scientific name | From the labels file (`Turdus merula_Eurasian Blackbird`). Non-species classes (`Human vocal`, `Dog`, `Engine`, `Noise`...) have no binomial name and must never be published; human classes in particular are excluded (privacy.md) |
| Taxonomic key | **V2.4 labels contain no taxonomic key.** `species.taxon_key` should stay optional; the scientific name is the identifier |
| Confidence | Sigmoid of the logit, 0–1, with BirdNET's sensitivity parameter (default 1.0). Not calibrated |
| Window start/end | 3.0 s windows at 48 kHz; `observed_at` = window start, `window_end` = start + 3 s |
| Model name and version | `BirdNET` and e.g. `GLOBAL_6K_V2.4-int8+sha256.c8354a476d3f` (≤ 64 characters, checked against the schema in the tests) |
| Several species per window? | **Yes.** The output is multi-label (independent sigmoids), so several species can exceed the threshold in the same window. Proposal: one event per species above the threshold, with `stable_event_id(station_id, observed_at, scientific_name, model_version)` so retries keep the id |
| Common names | The archive includes labels in 27 languages, including Spanish (`es.txt`: *Mirlo Común*) but **not Basque**. Useful for Elena's ES/EN catalogue ([#22](https://github.com/elenaatorralbo/txori-kantua/issues/22)); EU names must come from another source |

## Known limitations

- Only the corpus benchmark and the wrapper exist. Continuous capture
  ([#15](https://github.com/elenaatorralbo/txori-kantua/issues/15)),
  inference service ([#16](https://github.com/elenaatorralbo/txori-kantua/issues/16))
  and filtering ([#17](https://github.com/elenaatorralbo/txori-kantua/issues/17))
  are Sprint 2.
- Five recordings show that the pipeline works; they do not measure recognition
  quality. That is [#25](https://github.com/elenaatorralbo/txori-kantua/issues/25).
- Windows do not overlap. BirdNET-Analyzer can overlap windows for better
  recall at a higher CPU cost; to be considered only if the Pi has room.
