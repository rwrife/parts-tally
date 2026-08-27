# Integrated release verification record

**Release candidate:** v0.1.0-rc.1
**Compatibility:** carrier A0 / firmware 0.2.0 / protocol `parts-tally/v1` / app 0.1.0
**Evidence cutoff:** populated by the issue #7 PR and tagged release workflow

## Verdict

The release process is reproducible and fail-closed: a package is produced only after native KiCad ERC/DRC/schematic parity, repository hardware/BOM validators, BOM/CPL parity, manifest/document contracts, and archive integrity pass. Firmware/app checks run in their pinned workflows. This supports an **RC for fabrication quote/DFM and first-article build**, not a declaration that hardware works.

## Static analysis

Required commands:

```bash
python3 scripts/validate_contract.py
python3 -m unittest discover -s tests -v
python3 hardware/kicad/validate_hardware.py
python3 hardware/kicad/export_bom.py --check
python3 scripts/validate_release.py
pio check -d firmware -e native --fail-on-defect high
pio test -d firmware -e native
pio run -d firmware -e seeed_xiao_esp32c3
cd app && npm ci && npm run lint && npm run typecheck && npm test && npm run build && npm run test:e2e
```

The release workflow additionally runs KiCad 9 ERC, exports the XML netlist, executes `validate_pcb.py`, runs DRC with all severities/all track errors/schematic parity, plots fabrication files, normalizes CPL, checks exact BOM/CPL parity, compiles the OpenSCAD solids, validates manifold topology, and verifies every archive checksum/ZIP member.

Exact run URLs and tool output are recorded in the PR and tag Actions pages. The archive includes KiCad ERC/DRC reports and the exact fabrication command log. Results must not be copied into this source file before the corresponding run exists.

## Datasheet/BOM verification

- The schematic remains the BOM source of truth and `bom/bom.csv` is checked for drift.
- Every populated symbol carries Manufacturer, MPN, supplier/source, supplier PN, Datasheet, dated cost/stock observation, and BOM comments.
- NAU7802SGI has a 96/100 structured extraction with all 16 pins checked against Nuvoton Rev. 2.6.
- Critical XIAO, USB-C, JST GH, RGB LED, protection, and load-cell mappings are backed by manufacturer documents cited in `hardware/datasheets/manifest.json` and `hardware/reports/schematic-validation.md`.
- The bulk LCSC catalog was not accessed because accepting third-party catalog terms was not authorized. Public searches on 2026-08-27 confirmed the exact C189895/JST mapping but returned contradictory stock snippets; no current stock or price claim is made.
- Full structured extraction is not available for every passive/module. Those checks remain manufacturer-link/manual consistency checks, not machine-extracted verification.

## Fabrication/DFM basis

Selected comparison profile: documented JLCPCB standard two-layer capability. Design values are 0.15 mm minimum track, 0.20 mm minimum clearance, 0.60/0.30 mm vias, 0.50 mm copper-edge clearance, 100 × 60 mm, two layers, and 1.6 mm nominal board thickness. Native DRC is authoritative; the release validator also checks the frozen profile is not below published process minima.

The principal assembly exception is J1's two bottom-tented, unfilled through-vias in VBUS pads. Tenting does not equal filling/plugging. PCBA requires explicit assembler process acceptance or documented hand rework and inspection. CPL rotations remain an operator review item during first-order assembly review.

## Simulation

**Not performed.** No SPICE simulator was installed on the execution host, no validated component models/parasitics were available for a meaningful whole-chain result, and no simulated result is substituted for physical characterization. Static application-circuit calculations are identified as such in the hardware review.

## Bench testing

**Not performed — no physical prototype exists.** There is no assembly record, continuity result, instrument record, rail/current measurement, ADC capture, load fixture, calibration, repeatability, hysteresis, warm-up, creep, off-center, disconnect, overload, reconnect, or known-count evidence. `docs/assembly-and-bring-up.md` and `docs/verification-plan.md` preserve the unexecuted procedures.

## Field testing

**Not performed — no physical prototype exists.** There is no field deployment, environmental observation, long-term drift record, user trial, radio-range result, or operational safety evidence.

## Known limitations / release gaps

1. First-article fabrication, assembly, mechanical fit, stop adjustment, and continuity are pending.
2. USB current/inrush, diode losses, 3.3 V rail, 3.0 V AVDD/excitation boundary, RGB brightness/current, and thermal behavior are unmeasured.
3. Load-cell noise, RF coupling, calibration quality, drift, creep, hysteresis, off-center response, and useful unit-mass limits are uncharacterized.
4. Conducted/radiated EMC and antenna detuning are unmeasured; only static keepout/return-path evidence exists.
5. J2 availability and all prices/stock must be rechecked before ordering; no substitution inherits this review.
6. The PCBA BOM includes user-sourced blanks; an operator must review part matching and rotations.
7. The device is USB/SELV-only, not certified, not legal-for-trade, and unsuitable for safety-critical stock control.
