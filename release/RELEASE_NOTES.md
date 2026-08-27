# Parts Tally v0.1.0-rc.1

This is the first integrated hardware/firmware/app **release candidate** for quote, peer review, fabrication review, and eventual physical bring-up.

## Compatibility

- carrier board A0
- firmware 0.2.0
- protocol `parts-tally/v1`
- companion app 0.1.0
- persistent-state schema 3 / calibration schema 2

## Included

- editable KiCad 9 schematic/PCB/project and project-local libraries;
- editable OpenSCAD fixture source and generated reference STLs;
- KiCad-generated Gerber X2, separate PTH/NPTH drill files, drill map, placement/CPL, schematic PDF, assembly drawings, and renders;
- schematic-backed BOM plus a JLCPCB-format parity-checked BOM;
- firmware/app source, protocol schemas, assembly/bring-up procedure, release manifest, license notices, reports, and SHA-256 checksums.

## Verification state

Static hardware validators, native KiCad ERC/DRC/parity, firmware native tests/static analysis/target compile, app lint/type/unit/accessibility/e2e/build, protocol contract tests, mechanical compilation/manifold checks, and archive integrity are required release gates. See `docs/release-verification.md` and the GitHub Actions run attached to the tag.

No physical prototype exists. Continuity, USB current, rails, bridge excitation, ADC raw behavior, noise, repeatability, hysteresis, warm-up drift, creep, off-center response, disconnect/saturation/overload handling, RF/EMC, thermal, calibration, known-count, and field tests remain pending. No render or software/static result is presented as physical evidence.

## Fabrication warnings

- J1 uses two bottom-tented but unfilled through-vias in VBUS pads. Obtain explicit assembler approval for solder-wicking risk or use documented hand rework/inspection.
- The JLCPCB BOM has blank LCSC IDs for user-sourced parts and is not a turnkey order.
- Public C189895 stock results remain contradictory. Re-check the exact JST connector and all sourcing facts at checkout.
- Preserve USB/SELV-only, non-certified, non-legal-for-trade scope and explicit uncertainty/fault states.

Closes #7.
