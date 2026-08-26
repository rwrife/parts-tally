# Carrier PCB and mechanical layout validation

**Project:** Parts Tally revision A0 (KiCad 9, single-sheet schematic, two-layer PCB)

**Review date:** 2026-08-26 UTC

**Scope:** issue #6 carrier PCB, static PCB/schematic cross-check, and editable mechanical source

**Physical evidence:** none

## Verdict and blockers

**No critical or warning-level electrical/layout blocker was found by the checks that ran.** The editable PCB is ready for peer review and issue #7 fabrication-package work, but it is **not fabrication-approved or prototype-tested**.

| Severity | Item | Required action |
|---|---|---|
| WARNING before fabrication | J1’s locator holes force two 0.60/0.30 mm through-vias into VBUS pads. The B.Cu ends are tented, but unfilled via-in-pad can wick solder. | In issue #7, confirm the assembler’s tenting/plugging process or select hand-solder/rework guidance before ordering. |
| WARNING before ordering | Current public results for JST C189895 conflict between in-stock and out-of-stock snippets. | Recheck the exact JST MPN and source at checkout; do not silently substitute the footprint. |
| TEST GAP | No board, fixture, or enclosure has been built. | Execute continuity, power, noise, RF, mechanical fit, overload-stop, calibration, and stability tests on hardware. |

## Overview

The 100 × 60 mm board carries a power-only USB-C input, protected 5 V path, Seeed XIAO ESP32-C3 module, NAU7802 bridge ADC, keyed JST GH load-cell connector, RGB status LED, button, UART header, and ten named test points. U1 is at a board edge with explicit copper/track/via and component rule areas on both layers. Parametric OpenSCAD source provides a 170 × 120 mm printed base, load-cell mounts, 130 × 90 mm bin platform, PCB standoffs outside the force path, cable clamp, feet, and adjustable overload stops.

## Previous review delta

The 2026-08-22 schematic review explicitly lacked a PCB, DRC, mechanical CAD, EMC-layout basis, and manufacturing layout evidence.

- **Fixed/new evidence:** editable routed `.kicad_pcb`; 0-violation native DRC; exact schematic↔PCB pad-net validator; antenna rule areas; GND pours; M3 board mounts; review renders; editable mechanical source.
- **Still open:** physical module/connector fit, AVDD/excitation measurement, bridge noise, USB inrush, RF interaction, thermal behavior, calibration/drift, harness continuity, overload-stop setup, and complete fabrication DFM.
- **No prior PCB analyzer JSON:** a structured run-to-run PCB diff was not possible.

During the 2026-08-26 inherited-work review, the base's fixed-end M5 passage was found offset from the TAL220B drawing center because a non-centered boss origin was interpreted as its center. The same review found that the first stop formula produced a 4.8 mm gap, access holes removed the intended contact surfaces, and a later draft measured the gap from the bare boss rather than the adjustment hardware. The source now places fixed/free passages at the drawing's ±20 mm centers and models each stop as an M4 heat-set insert, nylon-tip set screw, jam nut, and solid 12 mm underside pad. The asserted 0.8 mm nominal gap is from the modeled screw-tip plane to the pad. Both OpenSCAD solids were recompiled successfully. These defects were resolved before publication; purchased-hardware fit and real stop adjustment remain unverified.

## Verification basis

### Tools actually run

| Check | Evidence basis | Result |
|---|---|---|
| `validate_hardware.py` | raw schematic + manufacturer-backed assertions from issue #3 | PASS: 45 symbols, 31 populated BOM components, 106 labeled connections, 15 intentional NCs, 16 NAU7802 pins, 6 RGB pins, 16 XIAO footprint pads, exact critical pad sets |
| KiCad 9 ERC | native KiCad | 0 violations |
| `validate_pcb.py` | raw PCB + exported KiCad XML netlist | PASS: 128 physical pads / 124 unique IDs checked against 123 schematic nodes plus J2's explicitly unnetted `MP` hold-down ID; 41 schematic footprints + 4 board-only holes |
| KiCad 9 DRC | native KiCad, all severities and all track errors | **0 violations, 0 unconnected items, 0 footprint errors** |
| KiCad 9 schematic parity | native KiCad | **0 parity issues** after H1–H4 were marked board-only |
| OpenSCAD CLI + `validate_stl.py` | source compile + independent mesh topology | base: 4,672 facets/2,322 vertices; platform: 1,212 facets/608 vertices; each is one edge-connected, consistently wound 2-manifold shell with 0 boundary/overused/orientation/vertex-link errors |
| KiCad render/SVG export | generated review artifacts | top, bottom, isometric PNGs and top/bottom copper SVGs generated successfully |

### Datasheet basis inherited and rechecked

The critical pin/application review remains grounded in the manufacturer sources recorded in `hardware/datasheets/manifest.json` and `hardware/reports/schematic-validation.md`:

- **NAU7802SGI, Nuvoton Rev. 2.6:** pin table p.6, limits p.7, I2C p.13, channel-1 application p.24, package p.37. Structured extraction exists at `hardware/datasheets/extracted/NAU7802SGI.json`.
- **XIAO ESP32-C3 113991054:** Seeed pin documentation/schematic for D4 SDA, D5 SCL, D6 TX, D7 RX, 3V3/GND/VUSB.
- **USB4105-GF-A, JST GH, ASMT-YTC7, and protection parts:** manufacturer URLs are stored on schematic symbols. Physical pad-net parity was checked for every PCB pad; the manufacturer documents, not KiCad libraries, remain physical pinout ground truth.
- **TAL220B-5KG:** manufacturer drawing dimensions used by the OpenSCAD source are 55 × 12.7 × 12.7 mm, 40 mm hole-center spacing, and 5.2 mm passages for M5 hardware. Printed fit remains unverified.

## Component and connectivity summary

- 41 schematic footprints + four intentional board-only M3 mounting holes.
- 128 physical PCB pads / 124 unique pad IDs checked against 123 schematic netlist nodes plus J2's explicitly allowlisted, unnetted `MP` hold-down ID; duplicate USB shell/VBUS, switch, and `MP` pads account for the higher physical-pad count.
- 40 named/generated nets.
- 332 track segments and 46 vias, including five GND vias.
- Track width distribution: 13 × 0.15 mm neck-down segments, 296 × 0.20 mm, 14 × 0.25 mm, 9 × 0.50 mm.
- Two filled solid-connected GND pours and four antenna rule areas.
- Zero native unrouted items.

## Power tree and current paths

```text
USB-C J1 VBUS
  -> D1 TVS + C11
  -> F1 500 mA hold PPTC
  -> D2 reverse-current Schottky
  -> +5V_XIAO (C1/C2, TP2)
  -> XIAO module regulator
  -> +3V3 (C3/C4/C5, TP3, J3)
     -> U2 DVDD
     -> U2 internal LDO -> AVDD_3V0/excitation (C6, TP5, J2 E+)
```

Raw-file layout checks show 0.50 mm trunks on VBUS and protected +5 V, short 0.20 mm branches/neck-downs, and 0.20 mm low-current 3.3 V distribution. This is a USB/SELV-only board; no mains creepage or isolation requirement applies. Actual current, diode dissipation, and inrush were not measured.

## Precision analog and return strategy

- `/LC_S+` = 10.01 mm and `/LC_S-` = 11.04 mm; **1.04 mm delta**.
- `/AIN+` = 37.71 mm and `/AIN-` = 30.91 mm, including filter branches; **6.80 mm delta**.
- Bridge routes are low-bandwidth measurement nets rather than timing-constrained digital pairs. They are kept in the U2/J2 region and away from the XIAO antenna area.
- B.Cu is the preferred GND return plane; F.Cu adds local ground copper. Solid pad connections avoid a starved thermal at edge-mounted J3 GND and provide low-impedance return paths.
- No split analog/digital ground domain was introduced; the NAU7802 application circuit and board use one GND domain.

## RF/antenna constraints

Four layer-specific KiCad rule areas enforce:

1. no copper pour, tracks, vias, or pads beneath the transformed XIAO antenna region; and
2. no components/copper in the module clearance region.

Native DRC passes with both pours filled. The OpenSCAD assembly marks a no-metal/no-fastener antenna volume. RF performance, enclosure detuning, and radiated/conducted EMC remain unmeasured.

## Mechanical and overload design

The top platform attaches only to the load-cell sensing end; the PCB attaches to independent base standoffs. Intended force flow is:

```text
bin -> top plate/cradle -> free load-cell end -> fixed load-cell end -> base -> feet
```

The PCB is not a structural link. Four M4 adjustable stops are modeled with a nominal 0.8 mm CAD gap, but the README requires bench adjustment under a conservative proof load rather than trusting printer tolerance. Cable clamp holes are separate from the strain element. No print, fit check, finite-element analysis, or real load test has occurred.

The fixed and free M5 passages are centered on the TAL220B drawing's −20 mm and +20 mm hole centers. Each nylon-tip M4 set screw faces a solid 12 mm-diameter, 2 mm-thick underside pad; no adjustment hole passes through the collision surface. The reference model uses a 6.2 × 6 mm insert pocket and 13.2 mm screw engagement/projection. OpenSCAD assertions bind each printed mount origin to the cell centers and verify the screw-tip-to-pad gap equals 0.8 mm. Purchased insert/screw dimensions and proof-load adjustment are still mandatory.

## Thermal and manufacturing assessment

- No high-power regulator, MOSFET, exposed thermal pad, or mains component is present. U2 is SOIC-16 and U1 is a module. A junction-temperature script was not run; actual USB-path losses remain load-dependent.
- Minimum route is 0.15 mm; general routing is 0.20 mm; vias are 0.60/0.30 mm. Fabricator capability has not yet been checked against a selected process.
- J1 VBUS uses two bottom-tented through via-in-pad transitions. This is the main assembly-process concern.
- Ten test points cover input/protected rails, GND, AVDD, I2C, bridge inputs, and VBG; J3 provides 3.3 V UART.
- Connector functions and pin 1 are labeled on F.SilkS. Review PNG/SVG artifacts are generated from the committed board.

## Sourcing and BOM

Schematic symbol properties remain the source of truth; `bom/bom.csv` is generated from them. `bom/non-schematic-items.csv` now separately includes printed base/platform, load-cell hardware, PCB standoffs, cable-clamp hardware, feet, and overload-stop hardware with TBD cost where no part was actually selected.

A 2026-08-26 public-search refresh confirmed current product mappings for J1, J2, U2, and U1 but did not provide API-grade quotes. Conflicting indexed prices and the dated J2 stock observation remain explicit. No stock, price, or lifecycle status is represented as guaranteed.

## False positives / reviewer overrides

- Early parity runs reported H1–H4 as extra footprints. They are intentional mechanical holes and are now marked board-only; final parity reports zero issues.
- KiCad library-sync checks report board-local overrides on footprints loaded by the deterministic generator, plus the project-local XIAO nickname in the headless container. `lib_footprint_mismatch` and `lib_footprint_issues` are explicitly ignored at project level; this does not suppress copper, clearance, connectivity, keepout, or footprint-placement DRC. `validate_hardware.py` protects the two-waiver set, resolves every populated footprint, checks critical pad sets, and `validate_pcb.py` compares every electrical pad to the exported schematic netlist.
- The two GND pours initially produced one starved thermal at J3. This was not waived: both planes now use solid pad connections and final DRC is clean.
- Early post-route GND stitch vias were reported dangling before fills. The generator no longer preplaces them; the final route has five connected GND vias and filled planes.
- FreeRouting’s internal “violations” count was not accepted as authoritative. The imported result was iterated until native KiCad DRC reported zero violations and zero opens.
- Issue #3’s I2C voltage-domain, DRDY pull-up, and RGB-limiting analyzer findings remain documented detector false positives; native ERC and the raw pin/net assertions pass.

## Not performed / review limits

- **KiCad MCP PCB audit:** attempted twice; failed because the MCP environment lacked the `pcbnew` module.
- **`analyze_schematic.py`, `analyze_pcb.py --full`, cross-analysis, thermal analyzer:** not present in the installed skill directory; no JSON claims were fabricated.
- **EMC analyzer:** not available locally. Plane continuity/antenna keepouts were checked through raw board structure and native DRC only.
- **SPICE:** not run; `ngspice`, `ltspice`, and `xyce` were unavailable.
- **Gerber/drill/CPL analysis:** intentionally not run because issue #6 does not create fabrication release files; issue #7 owns that gate.
- **Lifecycle audit:** not rerun; distributor APIs/bulk catalog were unavailable without credentials or accepting terms on the user’s behalf.
- **Full per-MPN extraction:** only the critical NAU7802 has a structured extraction; other manufacturer checks are inherited manual review.
- **Physical validation:** no continuity, power, USB, RF/EMC, thermal, noise, calibration, fit, overload, environmental, or field test.

## Final readiness statement

**Ready to merge as an editable PCB/mechanical layout and static review deliverable. Not ready to order or call tested.** Issue #7 must resolve the via-in-pad assembly method, run selected-fabricator DFM, export/inspect Gerber/drill/CPL files, and keep all physical-performance claims pending until a real assembled prototype is measured.
