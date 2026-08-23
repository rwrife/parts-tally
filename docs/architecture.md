# Parts Tally system architecture

**Architecture version:** 1.1
**Baseline date:** 2026-08-20
**Status:** Firmware domain, target adapters, protocol routes, native tests, and ESP32-C3 target compile implemented; physical verification pending

This document defines the module-prototype boundary and the later carrier-board boundary. It is not evidence that either assembly exists. The companion machine-readable summary is [`architecture-contract.json`](architecture-contract.json).

## 1. Safety and product boundary

Parts Tally is a USB-powered, SELV-only workshop aid. It is not legal-for-trade, safety-certified, medical, food-safety, life-safety, or suitable for hazardous-process control. It never switches mains and has no battery charger. A displayed count is an estimate derived from calibrated unit mass, not an authoritative inventory or weight.

The design must preserve explicit `unstable`, `stale`, `disconnected`, `saturated`, `overload_indicated`, `uncalibrated`, and `calibration_invalid` states. None may be silently converted into a count.

## 2. Architecture overview

```text
USB 5 V SELV
    |
    +--> controller module power/regulation ----> status LED + button
    |                |
    |                +--> local storage (settings/profiles/history)
    |                +--> local HTTP/WebSocket transport --> PWA
    |
    +--> bridge ADC/reference/excitation --> 4-wire load cell
                    |                         |
                    +--> raw samples          +--> mechanical load path
                              |
                              v
                 health checks -> filtering -> stability gate
                              -> tare/calibration -> mass + uncertainty
                              -> count estimate or explicit no-count state
```

### Subsystem ownership

| Subsystem | Owns | Must not own |
|---|---|---|
| Mechanical assembly | Base, fixed/sensing load-cell mounts, top plate/bin cradle, overload stops, feet, cable strain relief | PCB structural loads or count calculation |
| Load cell + bridge ADC | Excitation, differential bridge conversion, raw conversion samples, hardware fault indications where available | Tare, rounding, profiles, network behavior |
| Firmware drivers | ADC/button/LED/clock/storage/transport adapters and target-specific recovery | Measurement policy embedded in GPIO/network code |
| Measurement domain | Health checks, filtering, stability, tare, calibration, mass, count, uncertainty, no-count decisions | HTTP/WebSocket or flash APIs |
| Device services | Versioned persistence, bounded history, provisioning, authenticated `/api/v1`, event sequencing | Browser-only state as authoritative calibration |
| Companion PWA | Guided setup/calibration, status, corrections, thresholds, export/import preview, accessibility | Direct hardware access or hidden count inference |

## 3. Power and electrical boundaries

1. Input is a compliant 5 V USB SELV source only.
2. The module prototype is powered through the selected controller board's supported USB input.
3. The selected module chain is XIAO ESP32-C3 113991054 plus SparkFun SEN-15242/NAU7802 and SEN-14729/TAL220B. It uses 3.3 V I2C logic and begins with 3.0 V nominal bridge excitation; the boundary-condition voltage and noise remain measurement gates.
4. Normal current is a design target below 500 mA, not a measured claim. Peak and steady current must be measured on real hardware before release.
5. Recovery remains available over the controller's documented USB/UART path without LAN access.
6. The carrier revision adds protection, decoupling, named test points, connector protection, and ground/return strategy from manufacturer application guidance.

## 4. Measurement data flow

### 4.1 Terms

For each accepted ADC sample:

- `r[i]`: raw ADC code with monotonic timestamp.
- `f[i]`: filtered code after fault rejection and bounded outlier filtering.
- `T`: stored tare code for a specific bin/profile.
- `S`: calibrated scale factor in grams per code.
- `m = (f - T) * S`: net mass in grams.
- `Ncal`: known calibration sample count, at least 10.
- `mcal`: stable net mass of the known sample.
- `u = mcal / Ncal`: calibrated unit mass in grams per piece.
- `B`: measured stable noise band in grams, defined as `P95 - P5` over a stationary window after filtering.

No implementation may substitute an arbitrary constant for `S`, `u`, or `B` and still call the result calibrated.

### 4.2 Sample health and filtering

The pipeline processes timestamped samples in this order:

1. Reject or fault stale, missing, impossible, saturated, or disconnected samples before filtering.
2. Apply a bounded outlier rule that cannot conceal a sustained step. The exact algorithm is selected and golden-tested in issue #4.
3. Compute a rolling center, `P95 - P5` noise band, slope, outlier rate, and sample age.
4. Reset the stability dwell timer after a step, health fault, excessive spread, excessive slope, or excessive outlier rate.

The initial ADC baseline is 10 SPS, channel 1, PGA 128; 80 SPS is a separate comparison condition. Stability/noise thresholds are not frozen without characterization. The implementation must use named, persisted, bounded parameters and record the active values in diagnostics.

### 4.3 Stability contract

A reading is `stable` only when all conditions are true:

- at least two seconds and at least 20 accepted samples are in the current stationary window;
- no sensor health fault is active;
- sample age is within the configured stale limit;
- `P95 - P5` is at or below the characterized stability-band limit;
- absolute fitted slope is at or below the characterized drift limit;
- no unacknowledged load step occurred during the dwell period; and
- the outlier rate is within the characterized limit.

The two-second/20-sample floor is a baseline requirement. Issue #2 may tighten it with recorded evidence. It may not be weakened merely to make noisy data appear stable.

### 4.4 Tare and zero behavior

- Tare is accepted only from a stable, healthy, unsaturated reading.
- Tare is profile/bin-specific and records raw tare, timestamp/uptime context, firmware/schema version, and active measurement parameters.
- A net mass whose magnitude is within the active zero band may be displayed as zero mass.
- A negative net mass outside the zero band yields `below_tare` and withholds count; it is not clamped into a valid count.
- A changed bin, fixture, or load path requires a new tare and may require recalibration.

### 4.5 Known-count calibration

Calibration is committed only when:

1. empty-bin tare is valid;
2. the known sample contains `Ncal >= 10` identical pieces;
3. the sample reading is stable and healthy;
4. `mcal > 0` and neither tare nor sample approaches ADC saturation;
5. derived unit mass `u` is at least `20 * B`; and
6. stored values pass finite/range/schema checks.

A failed condition produces an explicit reason and preserves the previous valid calibration.

### 4.6 Count and uncertainty model

For a valid stable net mass and calibration:

```text
q = m / u
n = nearest integer to q, with exact half ties rounded away from zero
```

Negative `n` is never emitted as inventory. The firmware instead reports `below_tare` or zero within the zero band.

The baseline conservative uncertainty is:

```text
Um = max(B, drift_allowance, calibration_residual)
Uq = ceil(Um/u + abs(m)*Uu/(u*u) + 0.5)
```

where `Uu` is the stored unit-mass uncertainty from repeated calibration evidence or a conservative sample-variation bound. The final response contains both `estimatedCount = n` and `uncertaintyPieces = Uq`; it never drops uncertainty to imply exactness.

If repeated calibration evidence is unavailable, `Uu` uses a documented conservative default and the profile is marked `provisional`. Issue #2 must characterize the initial default before release.

### 4.7 Minimum usable part and no-count rules

The minimum usable unit mass for a setup is:

```text
u_min = max(20 * B, characterized_resolution_floor)
```

Count is withheld when any of these applies:

| State | Trigger | Required behavior |
|---|---|---|
| `uncalibrated` | No valid tare/scale/unit mass | Show guided calibration; no count |
| `unstable` | Stability contract fails | Show mass/raw diagnostics if safe; no authoritative count |
| `stale` | Last accepted sample exceeds limit | No count; report age |
| `disconnected` | Open bridge/module/transport evidence | No count; recovery guidance |
| `saturated` | ADC near or at conversion rail | No count; remove load/check wiring |
| `overload_indicated` | Validated raw/mass threshold exceeded | No count; remove load and inspect mechanical stops |
| `below_tare` | Negative mass beyond zero band | No count; check bin/tare |
| `calibration_invalid` | Non-finite/out-of-range/corrupt/migrated-invalid record | Preserve fault and require recalibration |
| `uncertainty_excessive` | `Uq` exceeds configured profile limit | Withhold count; report diagnostics and require a better calibration/part/setup |

## 5. Firmware task and interface boundaries

The implementation in issue #4 uses dependency-injected interfaces:

- `IAdcReader` returns timestamped raw samples and hardware fault metadata.
- `IMeasurementPipeline` consumes samples and returns health, stability, mass, count, uncertainty, and diagnostics.
- `ICalibrationStore` persists versioned tare/calibration records atomically.
- `IClock` provides monotonic time separately from optional wall-clock time.
- `IStorage` provides bounded, migration-tested persistence.
- `IProtocolTransport` maps typed domain commands/events to HTTP/WebSocket.
- `IButton` and `IStatusIndicator` preserve local tare/recovery/status access.

Measurement acquisition must not block watchdog/network servicing. Network failure must not stop local sampling or physical status. Storage writes must not occur on every sample.

## 6. Storage and data authority

| Data | Authority | Browser cache allowed? | Exported? |
|---|---|---|---|
| Device settings/schema | Device | Read-only copy | Yes, excluding secrets |
| Calibration profiles and tare | Device | Read-only/cache for UX | Yes |
| Thresholds | Device | Pending edit until acknowledged | Yes |
| Bounded history/corrections | Device | Paginated cache | Optional JSON; CSV |
| Wi-Fi credentials/device secret/session tokens | Device secure/platform storage | No | Never |
| PWA preferences/selected device | Browser | Yes | Optional app settings only |

Every persistent record has a schema version. Migrations are atomic and tested against corruption/interruption. A corrupt calibration never falls back to a plausible-looking count.
Wi-Fi and device credentials are retained in ESP32 NVS and excluded from logs, status, JSON
backup/export, and CSV. NVS is not a secure element or encryption boundary; physical flash
extraction can expose those secrets.

## 7. Provisioning, API, and app boundary

- Every boot retains a direct AP; a power-up button hold opens the physical-presence setup session,
  and stored credentials additionally start a nonblocking STA attempt.
- No cloud account or Internet connection is required.
- After provisioning, mutating `/api/v1` operations require a per-device secret/session and idempotency identifier.
- WebSocket events are sequenced; clients refresh status after a gap.
- UI components use a typed transport adapter and never call HTTP/WebSocket directly.
- Core button/status behavior remains available without LAN or Internet.
- Protocol v1 documents plaintext-HTTP residual LAN risk; authenticated TLS is not claimed.

The finalized contract is in [`protocol.md`](protocol.md). Framework-independent guards, routes,
and schemas are implemented, and the direct AP/STA plus HTTP/WebSocket adapters compile for the
target. Their execution on ESP32 hardware remains bench work.

## 8. Mechanical load path

```text
bin -> top plate/cradle -> sensing end of load cell
                         -> fixed end of load cell -> rigid base -> feet -> bench
```

The PCB, USB connector, ADC board, cable, and enclosure walls are outside the force path. Adjustable mechanical stops engage before damaging deflection. Off-center and overload tests are prohibited until the fixture, stops, and rated-load evidence exist.

## 9. Module prototype versus carrier revision

| Concern | Module prototype | Carrier revision |
|---|---|---|
| Controller | Seeed XIAO ESP32-C3 SKU 113991054 | Same validated module or justified exact replacement |
| ADC | SparkFun SEN-15242 / Nuvoton NAU7802 | NAU7802SGI plus Rev. 2.6 reference application components in KiCad |
| Wiring | Short labeled harness per `hardware/interfaces.md` | Keyed connector and named nets/test points |
| Power | Supported controller USB input | Reviewed USB/protection/regulation/decoupling |
| RF | Physical clearance around module antenna | Enforced copper/component/mechanical keepout |
| Evidence | Datasheet review + synthetic harness, then bench data if hardware exists | ERC/DRC/analyzers, fabrication, then bench evidence |

## 10. Verification stages and gates

1. **Documentation/static:** this architecture, requirements, risk register, protocol, and contract checks.
2. **Datasheet/selection (#2):** exact MPNs/SKUs, pinouts, application circuits, voltage/current, package, lifecycle, sourcing, and fixture dimensions.
3. **Synthetic/software (#2/#4/#5):** raw-capture parser, golden sample streams, firmware native tests, target compile, protocol compatibility, PWA tests/build.
4. **Schematic/layout (#3/#6):** real KiCad sources, ERC/DRC/analyzers, footprint/pad/pin verification, BOM/datasheet coverage.
5. **Bench:** real assembled fixture with dated raw data for the procedures in `verification-plan.md`.
6. **Field:** separate prolonged workshop use; never inferred from bench or simulation.

No later stage may be claimed from an earlier stage's evidence.

## 11. Open decisions delegated by dependency order

- #2 residual bench work: actual purchased revisions, excitation/noise/RF characterization, fixture evidence, and characterized stability thresholds. These remain explicitly unexecuted because no hardware is available.
- #3: protection/regulation, exact button/status/carrier-connector selections, footprints, debug/test points, and schematic-backed BOM.
- #4: filtering implementation, storage schema, authentication/session details, logging, recovery, and target build.
- #5: accessible workflows, caching behavior, and offline/PWA platform limits.
- #6: PCB stackup/layout/keepouts and mechanical dimensions/overload stops.
- #7: real bring-up, fabrication outputs, licenses, release manifest, and remaining gaps.

## 12. Current evidence

Completed: requirements/architecture contracts; manufacturer-document selection of XIAO 113991054, SEN-15242/NAU7802SGI, and SEN-14729/TAL220B; exact planned module wiring; a source/hash manifest; and tested raw-capture/analysis software with synthetic fixtures.

Not completed: PCB layout, app, electrical simulation, fabrication, assembly, continuity checks, execution of the NAU7802/NVS/network adapters on hardware, bench measurements, or field testing. Firmware native tests and a target compile are software evidence only. Datasheet review is not physical validation.
