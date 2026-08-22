# Schematic validation record

**Revision under review:** issue #3 branch, 2026-08-22 UTC
**Scope:** editable schematic and schematic-backed BOM only
**Physical evidence:** none — no PCB, assembly, measurement, calibration, or field test exists

## Automated results

| Check | Result |
|---|---|
| `kicad-sch-api` generation | 46 symbols; zero API validation errors; five informational warnings caused by KiCad-standard hidden `#FLGxx` references |
| KiCad MCP load | Loaded successfully; 46 components |
| KiCad MCP validate | 0 errors; five warnings, all the same `#FLGxx` parser limitation |
| `validate_hardware.py` | Pass: 46 symbols, 31 populated BOM components, 107 labeled connection points, 15 intentional NC points, 16 datasheet-checked NAU7802 pins, 6 datasheet-checked RGB LED pins, 16 checked XIAO footprint pads, 13 resolved populated footprints, and exact pad-set checks on J1/J2/J3/U1/U2/D3 |
| BOM export/check | Pass: 22 grouped lines / 31 populated components; estimated schematic-only extended total USD 13.1124 |
| NAU7802 v1.4 extraction consistency | Pass: zero issues |
| KiCad schematic analyzer | 41 physical components; 40 nets; 100% MPN and datasheet-link coverage; 3 errors, 1 warning after connectivity correction — all triaged below |
| Native KiCad 9 ERC/PDF | Enforced by `.github/workflows/hardware-schematic.yml`; the committed report is updated from the exact revision after CI |

## Datasheet verification basis

- **NAU7802SGI:** Nuvoton Rev. 2.6, especially pin table p.6, electrical limits p.7, I2C interface p.13, single-channel application circuit p.24, package drawing p.37. The checked 16-pin extraction is `hardware/datasheets/extracted/NAU7802SGI.json` with source SHA-256 recorded in the datasheet manifest.
- **XIAO ESP32-C3 113991054:** Seeed hardware documentation p.5 and Seeed schematic; D4/GPIO6 is SDA, D5/GPIO7 is SCL, D6/GPIO21 is UART TX, D7/GPIO20 is UART RX, pin 12 is 3V3, pin 13 GND, and pin 14 VUSB.
- **USB4105-GF-A / JST GH / PTS810 / ASMT-YTC7 / protection parts:** manufacturer drawings and datasheet URLs are stored on each symbol and in the manifest. ASMT-YTC7 AV02-3819EN pp.2–3 confirms the 3.0 × 2.8 mm PLCC-6 package, lead map (1 KB, 2 KG, 3 KR, 4 AR, 5 AG, 6 AB), forward voltages, and current limits. The KiCad symbol/footprint is a consistency aid; manufacturer sources remain ground truth.

## Analyzer finding triage

The static analyzer reported no unresolved connectivity/source/USB protection warnings after pin-coordinate correction. Four rule findings remain and are narrowly justified:

1. **LR-001, RGB LED current limiting — analyzer false positive.** D3 cathodes KR/KG/KB connect through R8/R9/R10 respectively; each resistor is 220 Ω before the XIAO GPIO. The detector does not traverse the separate RGB channels. This topology and the YTC7 lead map are asserted by `validate_hardware.py`. Final brightness/current remains a bench item.
2. **PU-001, DRDY pull-up — analyzer false positive.** Nuvoton Rev. 2.6 p.6 defines DRDY as a CMOS output, not an open-drain output. It is intentionally NC because firmware can poll the I2C conversion-ready state. Adding the recommended pull-up would not improve this unused push-pull output.
3. **VM-001, I2C_SCL 5 V crossing — analyzer false positive.** U1 has both VUSB (5 V input) and a regulated 3V3 output, causing an IC-level domain heuristic to classify its GPIO incorrectly. SCL is XIAO D5/GPIO7, U2 DVDD is 3.3 V, and R6 pulls SCL to 3.3 V. No I2C conductor is tied to VBUS.
4. **VM-001, I2C_SDA 5 V crossing — same false positive.** SDA is XIAO D4/GPIO6, U2 DVDD is 3.3 V, and R5 pulls SDA to 3.3 V.

These are detector limitations, not blanket waivers. Native ERC still gates the schematic.

## Review gaps / not applicable

- **PCB analyzer, cross-domain PCB checks, DRC, EMC layout analysis, thermal layout analysis, Gerber analysis:** not applicable yet because issue #3 intentionally does not create the PCB; these are mandatory in the later PCB/fabrication issue.
- **SPICE:** not run because `ngspice`, `xyce`, and `ltspice` were unavailable. The bridge frontend values were compared directly with the manufacturer application circuit; this is static evidence only.
- **Lifecycle audit:** attempted for all 19 unique MPNs; distributor APIs returned unknown status for all lines because credentials were unavailable. A live lookup found the initially selected ASMT-YTC2 obsolete, so it was replaced with pin-compatible ASMT-YTC7-0AA02; current JLCPCB price/availability is recorded. Other non-live stock remains marked unverified rather than invented.
- **Full per-MPN extraction:** structured extraction is complete for the critical NAU7802; remaining manufacturer links were reviewed manually and are not represented as machine-extracted facts.
- **Bench validation:** no assembled hardware exists. In particular, 3.0 V AVDD/excitation margin, RGB current/brightness, noise, USB inrush, cable polarity, calibration, drift, and RF interaction remain open.

## Verdict

**Schematic-ready for native ERC and peer review; not PCB-ready or fabrication-ready.** PCB/layout work must not start until issue dependencies and the native ERC gate are green, and no physical-performance claim is valid until a real prototype is built and measured.
