# Planned module-prototype build and capture record

**Wiring revision:** MP-1.0<br>
**Status:** planned and statically reviewed; no physical assembly, continuity result, photograph, or bench data exists

## Exact module wiring

| From | To | Domain | Evidence |
|---|---|---|---|
| USB-C compliant 5 V SELV source | XIAO ESP32-C3 SKU 113991054 USB-C | 5 V input | Seeed 113991054 datasheet pp. 4–5 |
| XIAO `3V3` | SEN-15242 `3.3V/VCC` | 3.3 V logic supply | Seeed datasheet p. 5; SparkFun Qwiic Scale schematic p. 1 |
| XIAO `GND` | SEN-15242 `GND` | 0 V reference | Board pin labels/schematics |
| XIAO D4 / GPIO6 / SDA | SEN-15242 `SDA/SDIO` | 3.3 V open-drain I2C data | Seeed pinout workbook; NAU7802 Rev. 2.6 p. 6 |
| XIAO D5 / GPIO7 / SCL | SEN-15242 `SCL/SCLK` | 3.3 V open-drain I2C clock | Seeed pinout workbook; NAU7802 Rev. 2.6 p. 6 |
| SEN-15242 `E+` | TAL220B red | ~3.0 V excitation positive | TAL220B p. 1; SparkFun hookup guide “Load Cell Connections” |
| SEN-15242 `E-` | TAL220B black | excitation return | Same |
| SEN-15242 `A+` | TAL220B green | differential signal positive | Same |
| SEN-15242 `A-` | TAL220B white | differential signal negative | Same |

Use CAB-17261 or separately continuity-verified jumpers between the Qwiic connector and the XIAO header. Wire color is an assembly aid, never sufficient evidence. Record connector orientation and continuity on the actual units before applying power.

## Diagram

```text
USB 5 V SELV
    |
    v
Seeed XIAO ESP32-C3 (113991054)
  3V3  ------------------------------> 3V3/VCC
  GND  ------------------------------> GND
  D4 / GPIO6 / SDA ------------------> SDA       SparkFun Qwiic Scale
  D5 / GPIO7 / SCL ------------------> SCL       (SEN-15242 / NAU7802)
                                                    E+ ---> red   TAL220B
                                                    E- ---> black TAL220B
                                                    A+ <--- green TAL220B
                                                    A- <--- white TAL220B
```

This diagram is a planned wiring record, not a photograph or proof of assembly.

## Pre-power gate

Do not energize a build until all boxes can be completed against real units:

- [ ] Record XIAO, SEN-15242, and SEN-14729/TAL220B markings/revisions and purchase source.
- [ ] Build a rigid two-ended TAL220B fixture with the load direction from the manufacturer drawing, a separate force path, non-slip base, strain relief, and adjustable overload stops.
- [ ] Confirm electronics/cables are outside the force path and antenna clearance is unobstructed.
- [ ] Inspect for shorts/damage; identify XIAO 3V3/GND/D4/D5 by board orientation, not assumed header order.
- [ ] With power absent, continuity-check Qwiic GND/SDA/SCL/VCC and each load-cell lead to its terminal.
- [ ] Confirm no 5 V pull-up reaches SDA/SCL.
- [ ] First power from a current-limited USB source; record instrument make/model/settings and observed USB 5 V, 3V3, AVDD/E+, and current.
- [ ] While powered and current-limited, configure NAU7802 AVDD to 3.0 V nominal, channel 1, gain 128, 10 SPS; check calibration completion and `CAL_ERR`.
- [ ] Verify signed response with a small safe load. Correct S+/S− wiring if polarity is reversed; do not hide an unexplained reversal in software.
- [ ] Complete the metadata required by `docs/verification-plan.md` before calling any capture bench evidence.

No item above is checked in this revision because no physical hardware is available.

## Raw capture workflow

The capture tool accepts an integer raw code per line, `elapsed_s,raw_code`, or JSON lines. A future serial stream can be recorded without dropping provenance:

```bash
pio device monitor --raw | \
  python3 scripts/capture_samples.py evidence/raw/noise-wifi-off.csv \
    --condition wifi-off \
    --trial zero-01 \
    --metadata hardware_revision=MP-1.0 \
    --metadata controller_sku=113991054 \
    --metadata adc_sku=SEN-15242 \
    --metadata load_cell_sku=SEN-14729 \
    --metadata firmware_revision=${FIRMWARE_REVISION} \
    --metadata fixture_revision=${FIXTURE_REVISION} \
    --metadata adc_rate_sps=10 \
    --metadata pga=128 \
    --metadata ambient_c=${MEASURED_AMBIENT_C} \
    --metadata instrument=${INSTRUMENT_AND_ASSET_ID} \
    --metadata operator=${OPERATOR} \
    --metadata usb_supply=${USB_SUPPLY_AND_ASSET_ID}
```

The CSV and `.meta.json` sidecar are both evidence. The capture tool writes through temporary files, replaces the CSV/sidecar fail-closed, and records the CSV SHA-256 in the sidecar. Never edit raw rows to improve a result; append a new trial and document anomalies.

Analyze without invented stability thresholds:

```bash
python3 scripts/analyze_capture.py evidence/raw/noise-wifi-off.csv \
  --evidence-stage bench \
  --window-samples 20 \
  --output evidence/reports/noise-wifi-off.json
```

For `--evidence-stage bench`, the analyzer verifies the sidecar filename, sample count, SHA-256, signed 24-bit format, zero ignored input lines, and non-placeholder setup metadata before producing a report. The firmware capture stream must therefore contain only supported sample records; do not hide diagnostics with `--ignore-unparseable`. This computes noise, drift, outlier, repeatability, and rolling-window facts but deliberately reports stability as `not_evaluated_thresholds_missing`.

After NOISE-01 establishes reviewed raw-code thresholds, provide both together:

```bash
python3 scripts/analyze_capture.py evidence/raw/noise-wifi-off.csv \
  --evidence-stage bench \
  --window-samples 20 \
  --max-band <characterized-P95-minus-P5-codes> \
  --max-abs-slope <characterized-codes-per-second> \
  --output evidence/reports/noise-wifi-off.json
```

A generated report is not sufficient bench evidence unless its raw capture, sidecar, setup, revisions, instruments, ambient, fixture, and procedure are also present.

## Synthetic verification now available

The tracked `tests/fixtures/synthetic_capture.csv` contains two zero and two reference trials. It is intentionally synthetic and exercises the same metrics and threshold gating:

```bash
python3 scripts/analyze_capture.py tests/fixtures/synthetic_capture.csv \
  --evidence-stage synthetic-software \
  --window-samples 10 --max-band 4 --max-abs-slope 5 \
  --output /tmp/synthetic-report.json
python3 -m unittest discover -s tests -v
```

These commands verify software behavior only. They do not characterize NAU7802, TAL220B, Wi-Fi interaction, mechanics, or the module prototype.
