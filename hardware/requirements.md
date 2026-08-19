# Hardware and system requirements

**Requirements version:** 1.0
**Baseline date:** 2026-08-19
**Status:** Reviewed measurable targets; implementation and physical verification pending

The original target list was reviewed for ambiguity and testability before component selection or schematic capture. Requirement IDs remain stable for traceability. Rationale for material wording changes appears at the end.

## Electrical

| ID | Requirement | Verification |
|---|---|---|
| E-01 | Operate only from a compliant USB 5 V SELV source; include no mains interface or onboard battery charging. | Schematic/power-tree review; input inspection; bring-up checklist. |
| E-02 | Design for normal input current below 500 mA. Before release, measure and report steady and peak current for startup, idle sampling, active Wi-Fi, calibration, and status-indicator extremes; do not claim compliance from estimates alone. | Current-limited first power plus recorded instrument data. |
| E-03 | Support exactly one full-bridge, 4-wire load cell through a keyed or unambiguously labeled connector whose mating half, orientation, and E+/E-/S+/S- mapping are documented. | Datasheet/pinout review; continuity record; schematic/PCB inspection. |
| E-04 | Detect stale, open/disconnected, persistently out-of-range, and saturated sensor data and withhold count in each state. | Synthetic fixtures plus DISC-01 and SAT-01. |
| E-05 | Provide a physical tare/calibrate/recovery input and text/icon/color-capable local status behavior that remains usable without Internet or LAN. | Firmware target test plus WIFI-01 and accessibility review. |
| E-06 | Expose manufacturer-supported USB/UART recovery and accessible, labeled test points for USB input, each regulated rail, ground, ADC clock/data, bridge excitation, and safe bridge-input observation. | Schematic/PCB review and bring-up access inspection. |
| E-07 | Carrier schematic/PCB must pass KiCad ERC/DRC and applicable analyzers with zero unexplained violations; every narrow waiver is tracked with rationale and scope. | Recorded tool reports from exact source revision. |

## Measurement

| ID | Requirement | Verification |
|---|---|---|
| M-01 | The initial candidate full-scale load is 5 kg. The released safe working load must be explicitly derated from the selected load-cell datasheet, fixture geometry, fasteners, and overload-stop evidence. | Datasheet/fixture calculation plus controlled OVR-01 evidence. |
| M-02 | Tare must include the intended base-independent platform/bin dead load with documented headroom from ADC and mechanical limits. Tare is accepted only while stable and healthy. | Datasheet/span analysis; tare misuse tests; bench headroom record. |
| M-03 | Known-count calibration requires at least 10 identical samples and records sample count, stable net mass, unit mass, uncertainty/provisional state, tare/profile identity, active parameters, schema version, and time context. | Persistence/schema tests and COUNT-01 records. |
| M-04 | Publish stable/unstable and all no-count fault states. Never silently convert unstable, stale, disconnected, saturated, overload-indicated, below-tare, or invalid-calibration data into an authoritative count. | Golden synthetic tests, protocol/UI tests, physical fault tests. |
| M-05 | Initial repeatability target: for uniform parts whose calibrated unit mass is at least 20 times the measured stable P95-P5 noise band, stable estimates are within ±1 piece in the declared bench trial set. Report uncertainty and all misses; this target is pending REP-01/COUNT-01 evidence. | NOISE-01, REP-01, COUNT-01 with raw data. |
| M-06 | Characterize and publish zero/span noise, warm-up drift, at least 10-minute creep, repeatability, hysteresis, off-center loading, cable disturbance, and Wi-Fi activity effects using the procedures in `docs/verification-plan.md`. | Raw bench data and generated summary. |
| M-07 | Detect configured overload/out-of-range indication and withhold count. Mechanical overload stops remain mandatory; firmware indication is not structural protection. | Synthetic threshold tests and safe OVR-01. |
| M-08 | Count uses the reviewed tare/unit-mass/rounding/uncertainty model in `docs/architecture.md`; exact half ties round away from zero and negative inventory counts are never emitted. | Deterministic unit/golden tests. |
| M-09 | Minimum usable unit mass is `max(20 * measured stable noise band, characterized resolution floor)`; lighter/variable parts are rejected or clearly marked unsuitable rather than assigned false precision. | Calibration validation tests and COUNT-01. |

## Mechanical

| ID | Requirement | Verification |
|---|---|---|
| K-01 | Target a prototype base no larger than 180 mm × 140 mm; publish actual overall and bin-contact dimensions when CAD exists. | CAD measurement and assembly drawing. |
| K-02 | Force path runs only through bin/top plate, sensing/fixed load-cell mounts, rigid base, and feet—not PCB, connectors, enclosure walls, or cable. | CAD review and physical load-path inspection. |
| K-03 | Use replaceable common metric fasteners where compatible with the selected load cell; publish editable CAD, fastener schedule, and dimensioned assembly drawings. | Source/archive inspection and assembly trial. |
| K-04 | Provide non-slip feet, cable strain relief, and openings/bend radii that do not pinch or load the sensor cable. | CAD/assembly inspection plus CABLE-01. |
| K-05 | Preserve controller manufacturer antenna keepout from copper, components, load-cell metal, fasteners, cables, and enclosure features; carrier constraints must be enforceable rule areas rather than notes alone. | Datasheet citation, PCB keepout audit, mechanical clearance inspection. |
| K-06 | Provide adjustable or dimensionally controlled overload stops that engage before damaging cell deflection while not contacting during validated normal loading. | Drawing/tolerance review and safe OVR-01/post-test checks. |

## Connectivity and data

| ID | Requirement | Verification |
|---|---|---|
| C-01 | Physical tare/recovery/status and ongoing measurement remain usable when Internet and LAN are unavailable; no cloud account/service is required. | WIFI-01 and target behavior test. |
| C-02 | First-run setup is local and requires deliberate physical presence for credential establishment/reset. | Provisioning and security tests. |
| C-03 | API uses versioned `/api/v1`; mutating operations require an authenticated per-device session after provisioning, request validation, and idempotency/replay controls. | Protocol compatibility/security tests. |
| C-04 | Device/app recover from Wi-Fi interruption and event sequence gaps without losing valid profiles/calibration or inventing history. | WIFI-01, persistence and mock-device E2E tests. |
| C-05 | Export profiles/history as versioned JSON and counts/history as CSV with explicit units/corrections; credentials, session tokens, and Wi-Fi settings are excluded. | Export/import schema and secret-scanning tests. |
| C-06 | Retention limits are bounded and documented; users can preview import, clear history with confirmation, and distinguish device-authoritative data from browser cache. | Persistence tests and app E2E/accessibility checks. |
| C-07 | Stable/unstable, disconnected, saturated, overload, stale, authentication, and incompatible-version states are conveyed by text/icon and not color alone. | Automated accessibility checks and component/E2E tests. |

## Environmental and use limits

| ID | Requirement | Verification |
|---|---|---|
| V-01 | Indoor dry workshop/office use only; no condensation, washdown, outdoor, or hazardous-location claim. | Documentation/release review. |
| V-02 | Initial validated-use target is 10–35 °C non-condensing. Selected parts must have manufacturer ratings covering a wider margin; bench evidence must record ambient temperature rather than extrapolate. | Datasheet audit and bench logs. |
| V-03 | Product and UI state that it is not legal-for-trade or certified for commerce, medical, food-safety, hazardous-process, life-safety, or structural use. | Documentation/UI/release string checks. |
| V-04 | App warns that mixed, corroded, wet, contaminated, damaged, or materially variable parts may not count reliably. | Content and accessibility tests. |

## Cost and reproducibility

| ID | Requirement | Verification |
|---|---|---|
| R-01 | Module-prototype planning target is USD $35–$55 excluding user-printed enclosure. Every estimate has source/date or `TBD—verify`; re-price before ordering. | Timestamped sourcing record and BOM review. |
| R-02 | Target total under USD $75 including ordinary cables/fasteners and excluding phone/computer/tools; separately list non-schematic items and assumptions. | Consolidated electrical/non-electrical cost rollup. |
| R-03 | Before pre-fab signoff, every populated electrical BOM line has Manufacturer, exact MPN, package/footprint, supplier/source, datasheet, and validation/BOM note in KiCad symbol properties. | Schematic-backed BOM and datasheet coverage audit. |
| R-04 | KiCad schematic properties are electrical BOM source of truth; tracked `bom/bom.csv` is exported from them. Preliminary planning CSV never becomes competing truth. | Reproducible export/diff check. |
| R-05 | Release includes editable KiCad/mechanical CAD, firmware/app source, pinned build instructions, license notices, generated fabrication outputs, checksums, and a manifest tying compatible revisions. | Tagged archive and integrity validation. |
| R-06 | Evidence labels distinguish documentation/static analysis, datasheet review, simulation, software tests, target compile, bench testing, and field testing. | PR/release report validation. |

## Review rationale and changes from initial targets

| Change | Rationale |
|---|---|
| E-02 now names operating modes and requires measured peak/steady evidence. | “Below 500 mA” was not testable without modes, instrumentation, and an explicit no-estimate rule. |
| E-03/E-06 now require connector orientation, mating half, and named test points. | Generic “support” and “expose” language could pass while remaining unbuildable or unsafe to probe. |
| M-02/M-03 now define acceptance gates and stored metadata. | Tare/calibration needed deterministic rejection, traceability, and corruption behavior. |
| M-05 defines the noise band as stable P95-P5 and ties the target to a declared trial set. | “Noise band” and “verified by bench trials” were ambiguous and could hide cherry-picked results. |
| M-08/M-09 added. | Count rounding, uncertainty, negative values, and minimum usable mass were previously architecture prose rather than requirements. |
| K-06 added. | “Stops mandatory” lacked a testable normal-clearance/damaging-deflection relationship. |
| C-02/C-03/C-07 tightened. | Local-first did not by itself define physical presence, authenticated mutation, event/auth fault accessibility, or replay behavior. |
| R-06 added. | Prevents static/synthetic evidence from being reported as physical prototype testing. |
| All physical verification references named plan IDs. | Makes later evidence reproducible and exposes every pending gap. |

## Current evidence

Only this reviewable baseline and its automated contract checks exist. Component selection, datasheet verification, electrical design, software implementation, simulation, fabrication, bench characterization, and field testing are pending their dependency-ordered issues.
