# Parts Tally A0 assembly, calibration, and bring-up

**Applies to:** carrier A0, firmware 0.2.0, protocol `parts-tally/v1`, app 0.1.0
**Evidence state:** instructions and acceptance plan only; no physical prototype, continuity record, instrument data, or field result exists.

This is a USB/SELV-only, non-certified counting aid. It is not legal-for-trade. Never connect mains, exceed the TAL220B 5 kg rated load, use the platform structurally, or use the count as the sole control for safety-critical stock.

## 1. Parts and tools

Use the exact schematic-backed parts in `bom/bom.csv` and non-schematic items in `bom/non-schematic-items.csv`. Before ordering, re-check every supplier ID and stock observation; C189895 has conflicting public availability results. Required bench equipment:

- current-limited 5 V SELV USB supply or USB power analyzer with current limiting;
- DMM with continuity/diode/voltage modes and identified probes;
- 3.3 V UART adapter (never 5 V logic) for J3 if USB recovery is insufficient;
- known masses or uniform counted parts whose provenance/count is recorded;
- rigid printed base/platform, specified fasteners, strain relief, non-slip feet, and four adjusted overload stops;
- ESD-safe soldering/rework equipment and magnification.

Record instrument make/model/asset ID, settings, UTC time, operator, ambient temperature, all hardware markings, firmware commit, fixture revision, and applied references before calling any result bench evidence.

## 2. Board and connector orientation

### Power and controller

```text
USB-C J1 VBUS
  -> D1 TVS and C11
  -> F1 500 mA hold PPTC
  -> D2 reverse-current Schottky
  -> TP2 +5V_XIAO -> U1 XIAO regulator
  -> TP3 +3V3 -> U2 DVDD and digital pull-ups
  -> U2 internal LDO -> TP5 AVDD_3V0 / bridge excitation
```

J1 is power-only: D+/D-/SBU are intentionally unconnected. Use U1's own USB-C port for programming/recovery. Do not connect both USB inputs without first reviewing the intended power path.

### Load-cell connector J2

View pin numbering from the board silkscreen/assembly drawing and verify the purchased connector drawing; do not infer it from wire color alone.

```text
J2 pin 1  E+  AVDD_3V0  -> TAL220B red    (excitation +)
J2 pin 2  E-  GND        -> TAL220B black  (excitation return)
J2 pin 3  S+  LC_S+      -> TAL220B green  (signal +)
J2 pin 4  S-  LC_S-      -> TAL220B white  (signal -)
```

Continuity-check every harness conductor end-to-end before insertion. Swapping S+/S- reverses sign; correct the documented harness rather than hiding an unexplained reversal in firmware. Swapping excitation and signal pairs is prohibited.

### UART J3 and user controls

```text
J3.1 +3V3     J3.2 GND     J3.3 UART_TX (D6/GPIO21)
J3.4 UART_RX (D7/GPIO20; 3.3 V logic only)
SW1 dedicated active-low tare/calibrate/recovery input (D1/GPIO3)
D3 red/green/blue channels are active-low through R8/R9/R10 (220 ohm)
```

### Named test points

| TP | Net | Expected powered state | Purpose |
|---|---|---|---|
| TP1 | VBUS | approximately USB input, nominal 5 V | connector-side input |
| TP2 | +5V_XIAO | below TP1 by F1/D2 losses | protected module input |
| TP3 | +3V3 | nominal 3.3 V | controller/ADC logic |
| TP4 | GND | 0 V reference | probe reference |
| TP5 | AVDD_3V0 | nominal 3.0 V after firmware config | ADC analog supply/excitation |
| TP6 | I2C_SDA | 3.3 V idle; open-drain traffic | bus data |
| TP7 | I2C_SCL | 3.3 V idle; open-drain traffic | bus clock |
| TP8 | AIN+ | low-level bridge input; do not short/inject | filtered ADC input + |
| TP9 | AIN- | low-level bridge input; do not short/inject | filtered ADC input - |
| TP10 | VBG | ADC reference node; compare only with NAU7802 procedure | diagnostic/reference |

These are expected design states, not measured tolerances. Record actual values and the DMM reference point. Stop on negative/unstable rails, excessive current, smoke, heat, odor, or unexpected continuity.

## 3. Mechanical assembly

1. Print `hardware/mechanical/parts-tally-platform.scad` outputs using a documented material/process. Inspect for cracks, warping, blocked insert pockets, and dimensional error.
2. Fit the two TAL220B mounting passages at the documented 40 mm center spacing. Confirm the load direction against the manufacturer drawing.
3. Attach the fixed end to the base and the sensing end only to the platform. The force path must be bin -> platform -> sensing end -> fixed end -> base -> feet. The PCB and cables must not carry load.
4. Mount the PCB on independent M3 standoffs. Preserve the XIAO antenna no-metal/no-fastener volume.
5. Install strain relief without pinching the load-cell cable. Keep bridge conductors paired and away from USB/radio wiring.
6. Install M4 inserts, nylon-tip set screws, jam nuts, and solid platform contact pads. The CAD's 0.8 mm nominal gap is not an acceptance measurement.
7. With a controlled conservative proof load below the TAL220B 120% FS safe-overload boundary, adjust all four stops evenly and lock them. Never use the 150% ultimate overload as a test target.
8. Confirm no rocking, PCB contact, cable tension, or fastener contact bypasses the load cell.

## 4. Soldering and assembly controls

1. Inspect bare boards against Edge.Cuts, drill map, assembly SVGs, and Gerbers before population.
2. Verify polarized/oriented parts: D1/D2, D3 pin 1/channel map, J1, J2 pin 1, U2 pin 1, U1 orientation, and J3 pin 1.
3. J1 has two bottom-tented but unfilled through-vias in VBUS pads. Obtain assembler approval for solder wicking or hand-solder/rework and inspect both sides. Tenting is not plugging.
4. Clean flux around U2 bridge inputs and high-impedance/reference nodes. Inspect for solder bridges and contamination under magnification.
5. Do not install the load cell until unpowered board checks pass.

## 5. Bring-up checklist

Every box below is initially unchecked. A future operator must copy this checklist into a dated unit record rather than editing this baseline to imply execution.

### A. Unpowered inspection and continuity

- [ ] Record PCB serial/markings, exact populated MPNs, assembly source, and photos of the real unit.
- [ ] Inspect orientation, solder joints, antenna keepout, via-in-pad joints, connector damage, and mechanical separation.
- [ ] Confirm no short between GND and TP1/TP2/TP3/TP5; record resistance after capacitor charging settles.
- [ ] Confirm J1 shell/GND and J2 pin 2 connect to TP4.
- [ ] Confirm J2 pins 1/2/3/4 reach TP5/GND/bridge paths as documented and are not mutually shorted.
- [ ] Continuity-check all four harness wires and connector orientation.
- [ ] Confirm the load cell/fixture/stops/strain relief are installed and the PCB is outside the force path.

### B. Current-limited USB first power

- [ ] Disconnect the load cell initially unless the reviewed procedure requires it connected.
- [ ] Set a documented 5 V current limit; begin conservatively and never exceed the design's 500 mA normal-current target.
- [ ] Apply power while observing current. Stop immediately on current limiting, heat, odor, smoke, unstable rails, or unexpected LED behavior.
- [ ] Record TP1, TP2, TP3, quiescent/current-limited supply current, and component temperatures by a stated method.
- [ ] Program firmware 0.2.0 through U1 USB-C; retain full build/upload logs and binary hash.

### C. Programmer and recovery

- [ ] Verify normal USB enumeration and upload.
- [ ] If normal upload fails, use the XIAO manufacturer's BOOT/RESET recovery sequence; SW1 is not a substitute for board recovery controls.
- [ ] If needed, connect J3 using 3.3 V UART only and cross TX/RX correctly.
- [ ] Verify factory reset/session recovery does not create an authoritative count and preserves explicit setup state.

### D. ADC and raw readings

- [ ] Configure U2 for 3.0 V nominal AVDD, channel 1, PGA 128, internal RC, 10 SPS, and required calibration; reject `CAL_ERR`.
- [ ] Record TP5 and bridge excitation across J2 pins 1-2. Stop if the load-cell 3 V minimum or U2 DVDD-to-AVDD margin is not met.
- [ ] Verify SDA/SCL idle near 3.3 V and capture bus traffic if diagnostics are needed.
- [ ] Record unedited signed 24-bit raw readings at zero load; verify no stale/disconnected/saturated fault.
- [ ] Apply a small safe load. Confirm the sign and return-to-zero response; correct S+/S- wiring if reversed.

### E. Tare and calibration

- [ ] Warm up for the characterized period; until WARM-01 exists, record elapsed warm-up rather than claiming it is sufficient.
- [ ] Place the intended empty bin, wait for a stable state, and tare.
- [ ] Add at least 10 identical known parts; use more when unit mass/noise requires it. Enter the exact known count.
- [ ] Reject calibration while unstable, disconnected, stale, saturated, overload-indicated, or below the `20B` unit-mass/noise criterion.
- [ ] Remove/reapply the sample and record raw code, net grams, estimated count, uncertainty, state, and actual count.

### F. Network/app and known-count trials

- [ ] Provision only on the intended local network/direct mode; record firmware/app revisions.
- [ ] Connect app 0.1.0 to protocol `parts-tally/v1`; verify explicit disconnected/stale/fault UI states.
- [ ] Exercise reconnect and event-gap refresh without retaining a stale authoritative count.
- [ ] Run COUNT-01 with at least three uniform part types and preserve every miss/correction.
- [ ] Execute the remaining `docs/verification-plan.md` matrix (repeatability, hysteresis, drift, creep, off-center, cable, disconnect, saturation, overload indication, Wi-Fi interruption).

## 6. Calibration procedure and evidence capture

Use `scripts/capture_samples.py` exactly as documented in `hardware/module-prototype.md`. Preserve the CSV and `.meta.json` sidecar together. For bench classification, metadata must be non-placeholder and the analyzer verifies sample count, input format, sidecar name, and SHA-256. Never edit raw rows; create a new trial and document anomalies.

Do not choose stability/noise thresholds from synthetic fixtures. NOISE-01 establishes `B` and drift limits from real Wi-Fi-off/idle/active captures. The ±1 piece objective applies only when unit mass and the declared uncertainty trial set support it.

## 7. Troubleshooting and recovery

| Symptom | Safe checks | Recovery / escalation |
|---|---|---|
| Supply current limit trips | Remove USB; inspect J1, D1, F1, D2, U1 orientation and rail shorts | Do not increase the limit to force startup; isolate the short and repeat unpowered checks |
| TP1 present, TP2 absent/low | Check F1 continuity, D2 polarity/drop, solder wicking at J1 vias | Repair only with documented rework; replace damaged protection parts |
| TP3 absent | Check U1 orientation, +5V_XIAO, module USB conflict | Recover/program U1 separately; do not backfeed 3V3 |
| TP5 absent/wrong | Confirm U2 DVDD, firmware LDO setting, CAL_ERR, C5/C6/U2 joints | Stop bridge tests; correct config/assembly before connecting the load cell |
| I2C NACK at 0x2A | Check 3.3 V pull-ups, SDA/SCL continuity/swap, U2 supply and address | Power-cycle after correcting wiring; do not add stronger pull-ups blindly |
| Raw code saturated/stale | Check J2 mapping, open/short bridge, excitation, U2 state | Withhold count; repair harness/sensor or ADC path and recalibrate |
| Load produces negative sign | Reconfirm physical load direction and J2 pins 3/4 | Correct S+/S- harness documentation; do not silently mask an unknown reversal |
| Reading changes with cable motion | Check strain relief, connector seating, cable routing/contamination | Fix mechanics and rerun CABLE-01/NOISE-01 |
| Count shown while faulted | Capture protocol/UI evidence | Treat as release blocker; firmware/app must withhold authoritative count |
| App cannot reconnect | Check local URL, credentials/session expiry, event gap handling | Use explicit refresh/re-auth; verify physical status remains useful offline |
| Firmware upload fails | Use U1 USB-C, known cable, manufacturer BOOT/RESET recovery | Use 3.3 V UART diagnostics only; preserve upload logs |
| Platform bottoms or rocks | Remove load; inspect feet, load path, stop adjustment | Rebuild/adjust fixture below safe load; do not continue calibration |

## 8. Completion boundary

This document is complete as an executable procedure, but every physical checkbox remains unexecuted. A future release may change bench/field status only by adding dated raw evidence, setup metadata, instrument identification, actual results, anomalies, and hashes. Renders, static validation, software tests, and simulated data never satisfy that requirement.
