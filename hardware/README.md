# Hardware

## System description

Parts Tally measures a removable bin through a 4-wire strain-gauge load cell. A 24-bit bridge ADC digitizes the differential signal. An ESP32-C3 filters readings, applies tare and known-count calibration, estimates quantity, stores local profiles, drives a status LED, and serves the local app.

The first hardware increment uses proven modules so measurement and mechanical risks can be characterized before designing a carrier PCB.

## Controller choice

The prototype targets **Seeed Studio XIAO ESP32C3**, based on Espressif ESP32-C3. It provides Wi-Fi, BLE-capable hardware, native USB development support, a small footprint, and enough GPIO for the bridge ADC, button, status LED, and debug access. The exact orderable module/board SKU and revision must be captured from the manufacturer before purchase and in KiCad properties before schematic release.

## Interfaces

- 4-wire load cell bridge to ADC: excitation +/-, signal +/-
- HX711-class two-wire digital interface to MCU: clock and data
- One debounced physical tare/calibrate button
- One addressable or discrete RGB status indicator with brightness limit
- USB-C 5 V input through the controller module for prototype power/programming
- 2.4 GHz Wi-Fi for local HTTP/WebSocket app; BLE reserved for evaluated provisioning only
- UART/USB recovery and accessible test points on the carrier revision

## Power plan

- SELV 5 V USB input only for MVP
- Use the controller module's regulated rail for logic, subject to measured noise/current validation
- Bridge excitation/ADC supply must follow the selected ADC and load-cell datasheets
- Add input protection, decoupling, analog filtering, and connector protection in the schematic as justified by datasheets
- No battery or charger in revision A

## Mechanical and enclosure concept

A rigid base holds one end of a straight-bar load cell; a top plate/bin cradle attaches to the sensing end. Mechanical overload stops protect the cell. The enclosure isolates the PCB and cable from the force path, exposes USB and the button, preserves antenna clearance, and uses common metric fasteners. Printable CAD sources and dimensioned drawings are planned; photos remain placeholders until a real prototype exists.

## Safety limits

- USB/SELV only; never connect to mains wiring
- Do not exceed the selected load cell's rated capacity
- Not structural, legal-for-trade, medical, food-safety, or life-safety equipment
- Do not use counts as the sole control for hazardous or critical stock
- Mechanical stops and a stable, non-slip base are mandatory before load testing

## Editable KiCad deliverables

The carrier-board milestone must create and preserve:

- `kicad/parts-tally.kicad_pro`
- `kicad/parts-tally.kicad_sch`
- `kicad/parts-tally.kicad_pcb`
- project symbol/footprint tables or vendored custom libraries when needed
- ERC and DRC reports with explained exclusions
- schematic PDF and PCB renders as supplements, never substitutes
- fabrication Gerbers, drill files, CPL when applicable, and release archive

Final Manufacturer, MPN, supplier, and BOM-note data lives in KiCad symbol properties. `../bom/preliminary-bom.csv` is not authoritative.

## Key layout constraints for the carrier revision

- Keep bridge inputs short, paired, and away from USB/Wi-Fi/high-edge-rate nets
- Follow selected ADC reference layout and decoupling guidance
- Preserve the XIAO/ESP32-C3 antenna keepout on all copper and enclosure metal
- Separate mechanical mounting loads from the PCB
- Add named test points for rails, ADC clock/data, bridge excitation, and ground
- Provide clear connector pin-1/polarity labels and accessible programming recovery

## Current evidence

Documentation only. No editable KiCad project, ERC/DRC output, measurements, or fabricated hardware exists yet.
