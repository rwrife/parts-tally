# Prototype verification plan

**Plan version:** 1.1
**Baseline date:** 2026-08-20
**Execution status:** UNEXECUTED — no physical prototype, instrument data, or raw samples are present

This plan defines evidence required by later issues. A checked-in plan, synthetic fixture, render, successful build, or static analyzer is not bench evidence.

## Evidence rules

Every executed bench record must include:

- UTC date/time, operator, hardware/firmware/app revisions, controller/ADC/load-cell MPNs and revisions;
- fixture drawing/revision, fasteners, overload-stop setting, bin/platform identity, applied masses/known parts;
- USB supply, ambient temperature, warm-up time, instrument make/model/asset identifier and relevant settings;
- unedited timestamped raw ADC samples plus derived outputs and active filter/stability parameters;
- exact command/script version, pass/fail calculation, anomalies, and links to photos only when photos depict the real setup;
- separate declarations for static analysis, simulation, software tests, bench tests, and field tests.

Raw data must be retained in an open format. Reports may summarize but never replace it.

## Safety prerequisites for physical work

Do not execute load tests until all are true:

1. exact load-cell datasheet/rated load and wiring are verified;
2. rigid base, fixed/sensing mounts, top plate, non-slip feet, strain relief, and mechanical overload stops are installed;
3. PCB/modules/cables are outside the force path;
4. unpowered inspection and continuity checks pass;
5. first power uses a current-limited USB source;
6. overload tests use a controlled fixture and stop below the manufacturer's damaging limit.

## Static and synthetic gate

| ID | Stage | Procedure | Pass criterion | Current status |
|---|---|---|---|---|
| DOC-01 | Documentation/static | Run `python3 scripts/validate_contract.py` and `python3 -m unittest discover -s tests -v`. | Both exit 0; all required IDs/documents/contracts agree. | Implemented by this issue; result belongs in PR evidence. |
| SYN-01 | Synthetic software | Feed deterministic zero, step, vibration, drift, creep, disconnect, saturation, stale, and restart fixtures to the measurement domain. | Golden outputs preserve no-count states, bounded recovery, and deterministic count/uncertainty. | Partial: #2 raw capture/analyzer synthetic fixture verifies noise/drift/repeatability/stability calculations and threshold gating; measurement-domain fault/count fixtures remain #4. |
| PROTO-READY-01 | Pre-bench | Review datasheets, wiring, mechanical load path, stops, instrument list, and raw capture path. | Reviewer signs all prerequisites; exact revisions recorded. | Partial: exact selected chain, planned wiring, capture path, and datasheet review exist. No purchased revisions, fixture/stops, instruments, continuity, or signoff exist. |

## Characterization matrix

Unless a selected datasheet imposes a tighter limit, use loads at approximately 0%, 10%, 25%, 50%, 75%, and 90% of the validated safe working load. Do not infer kilograms from raw ADC codes before calibration.

| ID | Measurement | Repeatable procedure | Planned metric / pass rule | Current status |
|---|---|---|---|---|
| NOISE-01 | Zero-load noise | Warm up per selected-device guidance; record at least 10 minutes at empty stable tare with Wi-Fi off, idle, and active traffic conditions. | Report sample rate, raw/code and gram standard deviation, P95-P5 band `B`, peak-to-peak, slope, outlier rate, and RF-condition deltas. Establish thresholds; no advance pass value is fabricated. | Unexecuted |
| REP-01 | Repeatability | Apply/remove each reference load at least 10 times, approaching consistently and allowing stability gate to settle. | For parts meeting `u >= 20B`, known-count estimates meet the ±1-piece target in the declared confidence/trial set; report all misses. | Unexecuted |
| HYS-01 | Hysteresis | Measure the same points on ascending and descending load cycles, at least 3 cycles. | Report maximum same-point difference in grams and pieces; acceptance threshold set from load-cell datasheet/application needs before execution. | Unexecuted |
| WARM-01 | Warm-up drift | From cold power-on, record unloaded and one mid-load reference for at least 30 minutes without retare. | Report offset/span change versus time and derived minimum warm-up guidance. Release requirement is evidence-based guidance, not assumed zero drift. | Unexecuted |
| CREEP-01 | 10-minute creep | Apply a stable mid/high reference load and record continuously for at least 10 minutes after initial settling. | Report change at 1, 5, and 10 minutes plus slope and count effect; set/verify policy for count withholding or guidance. | Unexecuted |
| OFFCENTER-01 | Off-center loading | Place the same safe reference load at center and documented corners/edges of the intended bin contact area. | Report maximum deviation and count impact. Any test risking fixture damage is skipped, not improvised. | Unexecuted |
| CABLE-01 | Cable disturbance | At zero and a reference load, perform a scripted gentle cable movement without changing applied load. | No silent authoritative count change; report induced band/offset and validate strain relief/recovery. | Unexecuted |
| DISC-01 | Disconnect/open bridge | Safely disconnect each supported sensor/module connection using an approved fixture. | Device reaches `disconnected` or another explicit no-count fault within a characterized time; no stale count remains authoritative; reconnection is explicit. | Unexecuted |
| SAT-01 | ADC saturation/out-of-range | Use a safe electrical fixture or bounded mechanical condition approved from the datasheet; do not overload the cell. | `saturated`/out-of-range is reported and count withheld; recovery requires valid stable samples. | Unexecuted |
| OVR-01 | Overload indication/stops | Exercise the validated overload-indication threshold while mechanical stops protect the load cell. Never exceed rated/damaging limits. | `overload_indicated`, count withheld, stops engage as designed, and post-test zero/span checks show no damage. | Unexecuted |
| WIFI-01 | Wi-Fi interruption | During stable sampling, disable AP/LAN, create event gaps, reconnect, and repeat power/network transitions. | Physical status and local measurement continue; profiles/calibration persist; client detects sequence gap and refreshes without inventing missed history. | Unexecuted |
| COUNT-01 | Known-count trials | For at least three uniform part types spanning usable unit masses, calibrate with documented `Ncal`, then blind-test multiple counts and corrections. | Report estimated count, uncertainty, actual count, stable/no-count state, errors, and whether ±1 target applies. Mixed/variable parts are explicitly unsuitable. | Unexecuted |

## Calibration misuse and recovery checks

Later firmware/app tests must also cover:

- known count below 10;
- calibration while unstable, disconnected, stale, saturated, or overload-indicated;
- negative net mass beyond zero band;
- unit mass below `20B`;
- corrupt, interrupted, old-schema, and non-finite calibration records;
- bin/profile mismatch and changed mechanical fixture;
- request replay/idempotency, credential rotation, factory reset, and USB recovery;
- import preview with incompatible schema and secret-like fields.

Each must fail safely, retain the last valid state where appropriate, and avoid producing an authoritative count.

## Requirement traceability

| Requirement | Primary test evidence |
|---|---|
| E-02 | Supply current measurements during NOISE-01/WIFI-01 plus first-power log |
| E-04 | DISC-01, SAT-01, stale synthetic fixture |
| M-02/M-03 | PROTO-READY-01, calibration misuse tests, COUNT-01 |
| M-04/M-05 | NOISE-01, REP-01, COUNT-01, synthetic tests |
| M-06 | WARM-01, CREEP-01, HYS-01, OFFCENTER-01, CABLE-01 |
| M-07 | SAT-01, OVR-01 |
| K-02/K-04/K-05 | Fixture inspection, OFFCENTER-01, CABLE-01, RF condition comparison |
| C-01/C-04 | WIFI-01 and power-cycle synthetic/target tests |
| V-02 | Ambient record across all bench tests; selected-part ratings review |

## Pending evidence statement

As of this baseline, all physical rows are **Unexecuted**. There is no claim of module assembly, sensor characterization, prototype testing, fabrication, or field use. Issue #2 may execute only the subset supported by hardware actually available; missing work remains a named gap.

The issue #2 software subset is repeatable with:

```bash
python3 scripts/analyze_capture.py tests/fixtures/synthetic_capture.csv \
  --evidence-stage synthetic-software --window-samples 10 \
  --max-band 4 --max-abs-slope 5 --output /tmp/synthetic-report.json
python3 -m unittest discover -s tests -v
```

This is synthetic software evidence only. It does not change any physical row to executed.
