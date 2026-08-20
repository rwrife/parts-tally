# Parts Tally risk register

**Register version:** 1.1
**Baseline date:** 2026-08-20

Likelihood and impact are design-time estimates (`Low`, `Medium`, `High`) rather than measured probabilities. Residual risk cannot be closed until the named evidence exists.

| ID | Hazard / failure mode | L | I | Consequence | Preventive/detective controls | Verification stage and evidence | Owner / issue | Residual status |
|---|---|---:|---:|---|---|---|---|---|
| RISK-ANALOG-01 | USB, digital, or RF noise corrupts the bridge measurement | High | High | Unstable or biased counts that appear plausible | Selected NAU7802 at initial 10 SPS/PGA128; 3.3 V DVDD/3.0 V AVDD boundary review; short paired bridge wiring; ground/return strategy; RF-condition measurements; stability/uncertainty gate | Datasheet review #2; NOISE-01; schematic/ERC #3; PCB/EMC/DRC #6 | Hardware/measurement (#2/#3/#4/#6) | Open; ADC selected and static checks complete, but excitation/noise/RF interaction unmeasured |
| RISK-RF-01 | Antenna is blocked by copper, cell metal, fasteners, or enclosure | Medium | Medium | Poor provisioning/reconnect, sampling interactions | XIAO 113991054 selected; preserve manufacturer antenna clearance; prototype clearance; enforceable all-layer/component/mechanical rule areas; avoid analog routing near antenna | Manufacturer guidance #2; layout audits #6; WIFI-01 and NOISE-01 | Hardware/mechanical (#2/#6) | Open; controller selected but fixture/enclosure geometry absent |
| RISK-MECH-01 | Overload/off-center force damages cell or routes load through PCB/connectors | Medium | High | Damage, sudden shift, misleading calibration, possible falling bin | TAL220B 5 kg selected; separate base/cell/top-plate load path; rated-load derating; rigid mounts; non-slip feet; adjustable stops; strain relief; prohibit unsupported loading | Datasheet/fixture review #2; CAD/DRC #6; OFFCENTER-01/OVR-01; post-test zero/span | Mechanical (#2/#6/#7) | Open; 120% safe-overload document exists but no fixture/stops/load evidence |
| RISK-CAL-01 | Wrong bin/sample count, unstable tare, or corrupt calibration is committed | Medium | High | Consistently wrong counts | Guided `Ncal >= 10`; stable/healthy gates; unit mass `>=20B`; atomic versioned storage; retain prior valid record; calibration audit metadata | Synthetic misuse/migration tests #4; COUNT-01; app E2E #5 | Firmware/app (#4/#5) | Open; domain and UI not implemented |
| RISK-CRED-01 | Lost/leaked local secret, unsafe reset, or insecure update locks out device or exposes mutation | Medium | Medium | Unauthorized changes or unrecoverable setup | Physical-presence setup/reset; per-device secret; no secrets in URL/log/export/cache; credential rotation; USB recovery; integrity/authenticity if OTA exists | Threat/protocol review #4; protocol tests; log/export tests; recovery procedure #7 | Firmware/app (#4/#5/#7) | Open; TLS/residual LAN decision pending |
| RISK-SOURCE-01 | Prototype candidate is retired, unavailable, wrong revision, or unsuitable for carrier | High | Medium | Unbuildable design or invalid pin/application assumptions | Exact 113991054/SEN-15242/NAU7802SGI/SEN-14729 selection; manufacturer source/hash manifest; 2026-08-20 price/stock snapshot; HX711 comparison; schematic properties as final BOM source | Selection record #2; BOM/datasheet audit #3/#7 | Hardware/BOM (#2/#3/#7) | Reduced but open: selection/source mismatch corrected; transient stock and actual purchased revisions must be rechecked |
| RISK-COUNT-01 | Unit variation, mixed/wet/corroded parts, drift, or rounding makes count misleading | High | High | User acts on incorrect stock state | Explicit uncertainty; no-count faults; minimum usable unit mass; known-count calibration; correction audit reason; unsuitable-part warning; non-certified disclaimer | Synthetic golden tests #4; REP-01/COUNT-01; accessible status tests #5; field evidence #7 | Measurement/product (#1/#4/#5/#7) | Open; only design model exists |

## Escalation rules

- A risk with High impact cannot be marked closed using only documentation or a render.
- A datasheet mitigates part-selection uncertainty but does not prove a specific assembly or layout.
- Synthetic tests prove deterministic policy behavior, not sensor performance.
- Bench tests require raw data and exact revisions; field evidence remains separate.
- Any newly discovered serious-harm use case is rejected rather than expanded into scope.

## Review cadence

Review this register at the start and end of issues #2 through #7. Each PR must update controls, evidence links, and residual status without deleting historical risks merely because work moved to another stage.
