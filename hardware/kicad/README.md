# Parts Tally KiCad source

This directory contains the editable KiCad schematic for the first Parts Tally carrier revision. The PCB is intentionally deferred to the layout issue; this directory does not claim a fabricated or bench-tested design.

## Files

- `parts-tally.kicad_pro` — KiCad project metadata.
- `parts-tally.kicad_sch` — editable source-of-truth schematic.
- `lib/parts-tally.kicad_sym` — project-local XIAO ESP32-C3 and NAU7802 symbols.
- `lib/parts-tally.pretty/XIAO_ESP32C3.kicad_mod` — project-local module footprint.
- `generate_schematic.py` — reproducible schematic generator.
- `validate_hardware.py` — pin map, net-label, NC, BOM-property, and extraction acceptance checks.
- `export_bom.py` — deterministic export from schematic properties to `../../bom/bom.csv`.

The XIAO library source and adaptation are documented in `lib/README.md`.

## Design summary

- J1 is a **power-only** USB-C UFP with independent 5.1 kΩ CC pull-downs, VBUS TVS, PPTC, reverse-current Schottky block, and input bypassing. Its USB data/SBU pins are intentionally NC.
- U1 is Seeed XIAO ESP32-C3 113991054. The module's own USB-C remains the programming/recovery interface; the carrier does not reuse BOOT/RESET as the product button.
- U2 is NAU7802SGI. DVDD is 3.3 V; firmware must configure the internal LDO to 3.0 V AVDD, channel 1, PGA 128, internal RC clock, and initially 10 SPS. The bridge path follows the Rev. 2.6 application circuit with 47 Ω series resistors, 100 nF differential filtering, VBG bypass, 1 µF DVDD/AVDD capacitors, and the 330 pF PGA-output filter.
- J2 is JST GH with explicit pin order: 1 E+, 2 E-, 3 S+, 4 S-. Verify actual harness continuity and wire colors before power.
- SW1 is a dedicated active-low product button. D3 is the current Broadcom ASMT-YTC7-0AA02 three-channel RGB indicator with one 220 Ω resistor per active-low cathode. Its six-pin map and PLCC-6 footprint are checked against manufacturer datasheet AV02-3819EN.
- J3 exposes 3.3 V UART only. TP1–TP10 cover VBUS, protected 5 V, 3V3, GND, AVDD, I2C, bridge inputs, and VBG.

## Regenerate and validate

Use Python 3.11+ and KiCad 9 symbol libraries:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r hardware/kicad/requirements.txt
python hardware/kicad/generate_schematic.py --symbol-dir /usr/share/kicad/symbols
python hardware/kicad/validate_hardware.py
python hardware/kicad/export_bom.py
python hardware/kicad/export_bom.py --check
kicad-cli sch erc --exit-code-violations \
  -o /tmp/parts-tally-erc.rpt hardware/kicad/parts-tally.kicad_sch
kicad-cli sch export pdf -o /tmp/parts-tally-schematic.pdf \
  hardware/kicad/parts-tally.kicad_sch
```

The GitHub workflow runs the native KiCad commands in `kicad/kicad:9.0`, avoiding host-version ambiguity.

## Source of truth and sourcing

Every populated symbol carries `Manufacturer`, `MPN`, `Supplier`, `Supplier PN`, `Datasheet`, `Estimated Unit Cost USD`, observation date, stock observation, cost basis, and `BOM Comments`. `bom/bom.csv` is generated from those fields. `bom/non-schematic-items.csv` separately tracks the load cell, mating contacts/housing, cable/supply, enclosure, and fasteners.

Costs are observations or clearly marked estimates, not quotations. See `../../bom/sourcing-snapshot.md`; re-check stock and price before ordering.

## Important limitations

This is a schematic/static-analysis deliverable. There is no PCB, DRC, signal-integrity/EMC layout review, Gerber/CPL archive, assembled prototype, continuity record, calibration, bench measurement, or field test. The device remains USB/SELV-only and is not legal-for-trade or safety certified.
