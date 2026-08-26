# Hardware

## System description

Parts Tally measures a removable bin through a 4-wire strain-gauge load cell. A 24-bit bridge ADC digitizes the differential signal. An ESP32-C3 filters readings, applies tare and known-count calibration, estimates quantity, stores local profiles, drives a status LED, and serves the local app.

The first hardware increment selected proven modules; revision A0 now includes an editable carrier layout and parametric mechanical platform so measurement and mechanical risks can be characterized before fabrication. This is still static design evidence, not prototype evidence.

## Controller choice

The selected prototype controller is **Seeed Studio XIAO ESP32-C3, SKU 113991054**. The selected ADC module is **SparkFun SEN-15242** using **Nuvoton NAU7802**; the selected carrier IC is **NAU7802SGI**. The selected load cell orderable SKU is **SparkFun SEN-14729**, containing the HT Sensor TAL220B 5 kg cell. See [`selection.md`](selection.md) and [`datasheets/manifest.json`](datasheets/manifest.json).

## Interfaces

The exact planned logical wiring map and carrier-board ownership boundary are versioned in [`interfaces.md`](interfaces.md), with pre-power and capture steps in [`module-prototype.md`](module-prototype.md). Physical connector orientation and continuity remain pending until real units exist.

- 4-wire load cell bridge to ADC: excitation +/-, signal +/-
- NAU7802 3.3 V I2C: XIAO D4/GPIO6 SDA and D5/GPIO7 SCL
- One debounced physical tare/calibrate button
- One addressable or discrete RGB status indicator with brightness limit
- USB-C 5 V input through the controller module for prototype power/programming
- 2.4 GHz Wi-Fi for local HTTP/WebSocket app; BLE reserved for evaluated provisioning only
- UART/USB recovery and accessible test points on the carrier revision

## Power plan

- SELV 5 V USB input only for MVP
- Use the controller module's regulated rail for logic, subject to measured noise/current validation
- The carrier schematic uses 3.3 V DVDD and a 3.0 V nominal internal-LDO AVDD/excitation setting; measure this boundary condition before PCB release
- Input protection, decoupling, bridge filtering, keyed load-cell connection, and reverse-current blocking are captured in the editable schematic
- No battery or charger in revision A

## Mechanical and enclosure concept

A rigid base holds one end of the TAL220B straight-bar load cell; a top plate/bin cradle attaches to the sensing end. Parametric OpenSCAD source in [`mechanical/`](mechanical/) includes M5 load-cell mounts, PCB standoffs outside the force path, cable strain relief, four non-slip feet, and four adjustable overload stops. The carrier places the XIAO antenna at a board edge with enforced two-layer copper/component keepouts; enclosure adaptations must also keep metal and fasteners out of that volume. Fit, print tolerance, stop gap, and load transfer remain physically unverified.

## Safety limits

- USB/SELV only; never connect to mains wiring
- Do not exceed the selected load cell's rated capacity
- Not structural, legal-for-trade, medical, food-safety, or life-safety equipment
- Do not use counts as the sole control for hazardous or critical stock
- Mechanical stops and a stable, non-slip base are mandatory before load testing

## Editable KiCad deliverables

The carrier-board milestone preserves:

- `kicad/parts-tally.kicad_pro`
- `kicad/parts-tally.kicad_sch`
- `kicad/parts-tally.kicad_pcb`
- project symbol/footprint tables or vendored custom libraries when needed
- ERC and DRC reports with explained exclusions
- schematic PDF and PCB renders as supplements, never substitutes
- fabrication Gerbers, drill files, CPL when applicable, and release archive

The project/schematic, routed `.kicad_pcb`, project-local symbols/footprints, generators, acceptance validators, datasheet extraction, schematic-backed BOM, mechanical source, DRC report, and review renders are present. Gerber/drill/CPL release files remain correctly deferred to the fabrication-packaging milestone.

Final Manufacturer, MPN, supplier, price-observation, stock-observation, datasheet, and BOM-note data lives in KiCad symbol properties. `../bom/preliminary-bom.csv` is not authoritative. From the repository root, regenerate the tracked BOM with `python3 hardware/kicad/export_bom.py`, or follow [`kicad/README.md`](kicad/README.md).

## Key layout constraints for the carrier revision

- Keep bridge inputs short, paired, and away from USB/Wi-Fi/high-edge-rate nets
- Follow selected ADC reference layout and decoupling guidance
- Preserve the XIAO/ESP32-C3 antenna keepout on all copper and enclosure metal
- Separate mechanical mounting loads from the PCB
- Add named test points for rails, ADC clock/data, bridge excitation, and ground
- Provide clear connector pin-1/polarity labels and accessible programming recovery

## Current evidence

The editable KiCad project, schematic, routed carrier PCB, project-local symbols/footprints, manufacturer-document/source manifest, schematic-exported BOM, targeted validators, OpenSCAD mechanical source, and static review evidence now exist. See [`kicad/README.md`](kicad/README.md), [`mechanical/README.md`](mechanical/README.md), [`reports/schematic-validation.md`](reports/schematic-validation.md), and [`reports/layout-validation.md`](reports/layout-validation.md).

Native KiCad 9 reports zero ERC/DRC violations and zero unconnected PCB items; repository validators pass. These are static checks only. No electrical/EMC simulation, physical fixture/assembly, continuity result, measurement, fabrication, calibration, load test, or field evidence exists yet. The design remains explicitly untested in hardware.
