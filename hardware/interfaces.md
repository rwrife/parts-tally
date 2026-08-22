# Module prototype wiring and carrier boundary

**Interface map version:** 1.2<br>
**Status:** module prototype map retained; carrier schematic pin assignments added and statically reviewed; assembly/continuity/bench evidence absent

This file defines logical nets and ownership. Exact selection evidence is in [`selection.md`](selection.md), document hashes/links in [`datasheets/manifest.json`](datasheets/manifest.json), and the pre-power/capture record in [`module-prototype.md`](module-prototype.md). Wire color alone is never pinout evidence.

## Selected module-prototype map

```text
USB 5 V SELV
  -> Seeed XIAO ESP32-C3 SKU 113991054 USB-C

XIAO 3V3 + GND
  -> SparkFun SEN-15242 3V3/VCC + GND

XIAO D4 / GPIO6 / SDA
  -> SEN-15242 SDA / NAU7802 SDIO
XIAO D5 / GPIO7 / SCL
  -> SEN-15242 SCL / NAU7802 SCLK

SEN-15242 E+ / E-
  -> TAL220B red / black excitation leads
TAL220B green / white signal leads
  -> SEN-15242 A+ / A-
```

Selected electrical defaults are 3.3 V DVDD/Qwiic logic, 3.0 V nominal AVDD/bridge excitation, channel 1, PGA 128, and 10 SPS. These are datasheet-reviewed starting settings, not measured values or final thresholds. The carrier uses a dedicated button and discrete RGB indicator; BOOT/RESET remains reserved for recovery.

## Wiring record

| Logical connection | Source terminal/pin | Destination terminal/pin | Voltage/domain | Verification source | Current evidence |
|---|---|---|---|---|---|
| USB input | Compliant USB-C supply | XIAO USB-C | 5 V SELV | Seeed 113991054 datasheet pp. 4–5 | Datasheet/static only |
| ADC supply | XIAO `3V3` | SEN-15242 `3.3V/VCC` | 3.3 V | Seeed p. 5; SparkFun board schematic p. 1 | Datasheet/static only |
| Common ground | XIAO `GND` | SEN-15242 `GND` | 0 V | Board schematics/labels | Static only; continuity pending |
| I2C data | XIAO D4/GPIO6/SDA | SEN-15242 SDA/NAU7802 SDIO | 3.3 V open drain | Seeed pinout workbook; Nuvoton Rev. 2.6 p. 6 | Datasheet/static only |
| I2C clock | XIAO D5/GPIO7/SCL | SEN-15242 SCL/NAU7802 SCLK | 3.3 V open drain | Same | Datasheet/static only |
| Excitation positive | SEN-15242 `E+` | TAL220B red | ~3.0 V nominal | TAL220B p. 1; SparkFun hookup guide | Datasheet/static only |
| Excitation negative | SEN-15242 `E-` | TAL220B black | excitation return | Same | Datasheet/static only |
| Signal positive | TAL220B green | SEN-15242 `A+` | differential analog | Same | Datasheet/static only; polarity trial pending |
| Signal negative | TAL220B white | SEN-15242 `A-` | differential analog | Same | Datasheet/static only; polarity trial pending |
| Physical user input | PTS810 active-low button, 10 kΩ pull-up, 100 nF debounce | XIAO D1/GPIO3 | 3.3 V logic | KiCad schematic; Seeed pin map | Static only; firmware and bench timing pending |
| User status red | ASMT-YTC7 red cathode through 220 Ω | XIAO D2/GPIO4 | 3.3 V active-low sink | KiCad schematic; Broadcom AV02-3819EN | Static only; current/brightness measurement pending |
| User status green | ASMT-YTC7 green cathode through 220 Ω | XIAO D3/GPIO5 | 3.3 V active-low sink | Same | Static only; current/brightness measurement pending |
| User status blue | ASMT-YTC7 blue cathode through 220 Ω | XIAO D10/GPIO10 | 3.3 V active-low sink | Same | Static only; current/brightness measurement pending |
| UART debug | J3 pin 3 TX / pin 4 RX | XIAO D6/GPIO21 and D7/GPIO20 | 3.3 V logic | KiCad schematic; Seeed pin map | Static only; target communication pending |

## Harness and physical controls

- Use CAB-17261 or individually continuity-verified jumpers; record connector orientation and pin labels on the real assembly.
- Keep excitation and signal conductors paired/short and away from USB, antenna, and digital edges.
- Add strain relief so cable movement cannot pull ADC/load-cell terminals.
- Preserve manufacturer antenna clearance from load-cell metal, fasteners, wiring loops, and enclosure features.
- Mount electronics outside the force path and away from overload-stop contact.
- Carrier TP1–TP10 provide access for USB VBUS, protected 5 V, 3V3, GND, AVDD/bridge excitation, I2C data/clock, differential inputs, and VBG; layout/access review remains pending.
- The SEN-15242 spring terminal is a prototype convenience, not the carrier's keyed connector decision.

## Carrier-board boundary

The carrier schematic accepts:

- XIAO ESP32-C3 SKU 113991054 or a separately reviewed exact replacement;
- Nuvoton NAU7802SGI in SOP-16 and the Rev. 2.6 application/reference components;
- one keyed four-position load-cell connector with mating-half documentation;
- one dedicated physical button and one dedicated accessible status indicator;
- USB/recovery access and named test points;
- mechanical mounting that carries no scale force.

The carrier schematic owns protection, decoupling, 3.3 V/AVDD generation, I2C pull-up ownership, filter values, test points, net names, connector mapping, and symbol/footprint properties. The PCB owns return paths, analog spacing, antenna keepout rule areas, connector access, and silkscreen orientation.

## Interface invariants

1. Swapping `S+`/`S-` may change sign but is corrected in the documented wiring, not hidden as an unexplained software quirk.
2. Swapping excitation and signal pairs is prohibited.
3. No GPIO is assigned without checking controller revision and boot/recovery constraints; D4/D5 are selected only for I2C.
4. Never put 5 V Qwiic pull-ups onto XIAO SDA/SCL.
5. A disconnected, stale, saturated, calibration-error, or overload-indicated sensor produces no count.
6. Networking is not required for the physical status/recovery path.
7. The exact built wiring and part markings are recorded with characterization data.
8. 3.0 V AVDD/excitation is a boundary condition that must be measured before PCB release.

## Evidence boundary

This map is implemented in `kicad/parts-tally.kicad_sch` and supported by manufacturer documents. It is not a continuity result, assembly record, bench test, or field test. No physical prototype or photos are available.
