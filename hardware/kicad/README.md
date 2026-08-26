# Parts Tally KiCad source

This directory contains the editable KiCad 9 schematic and routed two-layer carrier PCB for revision A0. The design is static-analysis/DRC reviewed but has not been fabricated, assembled, electrically measured, calibrated, or field tested.

## Files

- `parts-tally.kicad_pro` — KiCad project metadata and board rules.
- `parts-tally.kicad_sch` — editable schematic and BOM source of truth.
- `parts-tally.kicad_pcb` — editable 100 × 60 mm routed board source.
- `lib/parts-tally.kicad_sym` — project-local XIAO ESP32-C3 and NAU7802 symbols.
- `lib/parts-tally.pretty/XIAO_ESP32C3.kicad_mod` — project-local module footprint.
- `generate_schematic.py` — reproducible schematic generator.
- `generate_pcb.py` — reproducible board outline, placement, rules, labels, mounting holes, and antenna keepouts from the KiCad XML netlist.
- `pre_route_critical.py` — fixed VBUS/I2C/+5 V escapes around the USB locator holes and XIAO antenna keepout.
- `route_pcb.py` — netclass-aware Specctra DSN/SES exchange and idempotent GND-pour fill.
- `finish_route.py` — deterministic local TP2 branch left by the autorouter.
- `validate_hardware.py` — schematic pin map, net-label, NC, BOM-property, and extraction checks.
- `validate_pcb.py` — PCB/netlist parity, geometry, mounting, keepout, zone, route-width, and analog-pair checks.
- `export_bom.py` — deterministic export from schematic properties to `../../bom/bom.csv`.

The XIAO library source and adaptation are documented in `lib/README.md`.

## Board design summary

- 100 × 60 mm, two copper layers, four 3.2 mm M3 mounting holes.
- U1 sits at the top-right edge with four layer-specific rule areas. Copper, tracks, vias, and components are prohibited in the transformed XIAO/ESP32-C3 antenna regions.
- J1 is a **power-only** USB-C UFP. Its locator-hole geometry requires two bottom-tented 0.60/0.30 mm via-in-pad transitions to tie the duplicated VBUS pad locations on B.Cu. D+/D-/SBU remain intentionally NC.
- VBUS and protected +5 V use 0.50 mm trunks with short 0.20 mm branches/neck-downs; low-current 3.3 V distribution uses 0.20 mm routing. Thirteen 0.15 mm FreeRouting neck-down segments occur only at constrained fine-pitch pads and remain above the selected prototype process minimum.
- `/LC_S+` and `/LC_S-` measure 10.01/11.04 mm (1.04 mm delta). `/AIN+` and `/AIN-`, including filter branches, measure 37.71/30.91 mm (6.80 mm delta). These are low-bandwidth bridge signals, not timing-matched digital pairs.
- Solid-connected GND pours cover F.Cu and B.Cu; five GND vias join the planes. The bottom plane is the preferred return path.
- TP1–TP10 expose VBUS, protected +5 V, 3V3, GND, AVDD, I2C, bridge inputs, and VBG.
- J2 pin order is 1 E+, 2 E-, 3 S+, 4 S-. Verify the real harness continuity and wire colors before power.

## Validate the committed design

Use KiCad 9 and Python 3.11+:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r hardware/kicad/requirements.txt
python hardware/kicad/validate_hardware.py
python hardware/kicad/export_bom.py --check

kicad-cli sch erc --exit-code-violations \
  -o /tmp/parts-tally-erc.rpt hardware/kicad/parts-tally.kicad_sch
kicad-cli sch export netlist --format kicadxml \
  -o /tmp/parts-tally.xml hardware/kicad/parts-tally.kicad_sch
python hardware/kicad/validate_pcb.py \
  hardware/kicad/parts-tally.kicad_pcb --netlist /tmp/parts-tally.xml
kicad-cli pcb drc --severity-all --all-track-errors --exit-code-violations \
  -o /tmp/parts-tally-drc.rpt hardware/kicad/parts-tally.kicad_pcb
```

The GitHub workflow runs the native KiCad commands in `kicad/kicad:9.0`, avoiding host-version ambiguity. Review evidence is in `../reports/layout-validation.md` and `../reports/generated/`.

## Regenerate placement and reroute

The committed `.kicad_pcb` is the reviewed editable layout source. The placement and critical escapes are reproducible; FreeRouting is nondeterministic, so a new autoroute is a new design revision and must pass all checks and visual review.

```bash
kicad-cli sch export netlist --format kicadxml \
  -o /tmp/parts-tally.xml hardware/kicad/parts-tally.kicad_sch
python hardware/kicad/generate_pcb.py \
  --netlist /tmp/parts-tally.xml --output hardware/kicad/parts-tally.kicad_pcb
python hardware/kicad/pre_route_critical.py hardware/kicad/parts-tally.kicad_pcb
python hardware/kicad/route_pcb.py export-dsn \
  hardware/kicad/parts-tally.kicad_pcb /tmp/parts-tally.dsn
java -jar freerouting-2.3.0.jar --gui.enabled=false \
  -de /tmp/parts-tally.dsn -do /tmp/parts-tally.ses \
  -mp 30 -mt 4 -us Hybrid -hr 1:1 -is prioritized
python hardware/kicad/route_pcb.py import-ses \
  hardware/kicad/parts-tally.kicad_pcb /tmp/parts-tally.ses
python hardware/kicad/finish_route.py hardware/kicad/parts-tally.kicad_pcb
python hardware/kicad/route_pcb.py add-ground-zones \
  hardware/kicad/parts-tally.kicad_pcb
```

The recorded local route used FreeRouting 2.3.0 on Java 25 and KiCad 9.0.9. Do not accept an autorouter success code as evidence: run KiCad DRC and inspect the report.

## Sourcing and mechanics

Every populated symbol carries `Manufacturer`, `MPN`, supplier/source, supplier PN, datasheet, dated cost/stock observations, and BOM notes. `bom/bom.csv` is generated from those properties. `bom/non-schematic-items.csv` separately tracks the load cell, mating parts, printed pieces, cable restraint, feet, overload stops, and fasteners. Re-check all stock and prices before ordering.

Editable enclosure/platform source is under `../mechanical/`; force flows from top plate → load cell → base and does not pass through the PCB. Preserve the antenna no-metal/no-fastener volume when adapting the enclosure.

## Important limitations

This is a PCB-layout/static-analysis deliverable. Native ERC/DRC and structural checks pass, but the installed KiCad MCP analyzer lacked `pcbnew` and no local EMC/SPICE analyzer scripts were available. No Gerber/drill/CPL release archive is included; that belongs to issue #7 after layout review. There is no assembled prototype, continuity record, USB current measurement, RF/EMC measurement, load test, calibration, thermal test, or field test. The device remains USB/SELV-only and is not legal-for-trade or safety certified.
