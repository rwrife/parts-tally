# Hardware requirements

These are initial measurable targets. The requirements/risk issue may revise them with rationale before schematic capture.

## Electrical

| ID | Requirement |
|---|---|
| E-01 | Operate from a USB 5 V SELV source; no mains or onboard battery charging. |
| E-02 | Normal input current target below 500 mA; measure actual peak and steady current before release. |
| E-03 | Support one full-bridge, 4-wire load cell through a keyed or clearly labeled connector. |
| E-04 | Detect open/disconnected or persistently out-of-range sensor readings and withhold a count. |
| E-05 | Provide physical tare/calibrate input and local status indication without requiring network access. |
| E-06 | Expose safe USB/UART recovery and test points for power, ground, ADC signals, and bridge excitation. |
| E-07 | Carrier PCB must pass KiCad ERC/DRC with zero unexplained violations. |

## Measurement

| ID | Requirement |
|---|---|
| M-01 | Nominal full-scale load: 5 kg candidate; final safe working load must be derated from datasheet and fixture evidence. |
| M-02 | Tare range must include the intended removable bin and platform mass without ADC saturation. |
| M-03 | Known-count calibration accepts at least 10 identical samples and records sample count and net mass. |
| M-04 | Publish stable/unstable state; never silently turn an unstable reading into an authoritative count. |
| M-05 | Initial repeatability target: estimated count within ±1 piece for uniform parts whose unit mass is at least 20 times the measured stable noise band, verified by bench trials. |
| M-06 | Characterize warm-up drift, 10-minute creep, repeatability, hysteresis, off-center loading, and cable disturbance. |
| M-07 | Detect overload/out-of-range indication in firmware; mechanical overload stops remain mandatory. |

## Mechanical

| ID | Requirement |
|---|---|
| K-01 | Base footprint target no larger than 180 mm × 140 mm for the 5 kg prototype. |
| K-02 | Force path runs through base/load-cell/top plate, not through the PCB or connectors. |
| K-03 | Use replaceable common metric fasteners and publish printable CAD plus dimensioned assembly drawings. |
| K-04 | Provide non-slip feet, strain relief, and an enclosure opening that does not pinch the load-cell cable. |
| K-05 | Preserve the controller antenna keepout from copper, fasteners, load-cell metal, and enclosure features per manufacturer guidance. |

## Connectivity and data

| ID | Requirement |
|---|---|
| C-01 | Core tare/calibrate/count status remains usable if Internet and LAN are unavailable. |
| C-02 | First-run local setup must not require a cloud account. |
| C-03 | API is versioned; mutating operations require a per-device secret after provisioning. |
| C-04 | Device/app reconnect after Wi-Fi interruption without losing calibration or profiles. |
| C-05 | Export profiles/history as versioned JSON and counts/history as CSV; exclude credentials. |
| C-06 | Document retention limits and allow users to clear local history. |

## Environmental and use limits

| ID | Requirement |
|---|---|
| V-01 | Indoor dry workshop/office use only. |
| V-02 | Initial operating target 10–35 °C, non-condensing; validate selected parts against a wider rated range. |
| V-03 | Not certified for commerce, medical, food-safety, hazardous-process, or life-safety use. |
| V-04 | App warns that mixed, corroded, wet, or materially variable parts may not count reliably. |

## Cost and reproducibility

| ID | Requirement |
|---|---|
| R-01 | Module-prototype target: USD $35–$55 excluding a user-printed enclosure; re-price before ordering. |
| R-02 | Target under USD $75 including ordinary cables/fasteners, excluding phone/computer and tools. |
| R-03 | Every electrical BOM line has Manufacturer, MPN, package/footprint, source, and validation note before pre-fab signoff. |
| R-04 | Schematic symbol properties are the BOM source of truth; exported `bom/bom.csv` is tracked. |
| R-05 | Release includes editable KiCad/CAD source, firmware/app source, build instructions, licenses, and generated fabrication artifacts. |
