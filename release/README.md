# Parts Tally release candidate packaging

`release/manifest.json` freezes the board/firmware/protocol/app compatibility set. The release archive is generated from a tagged checkout by `scripts/build_release.py`; generated files are not preferred editable source.

## Build

Use KiCad 9.0.x with Python and `pcbnew` available. The GitHub workflow uses the pinned `kicad/kicad:9.0` image on an amd64 runner.

```bash
python3 scripts/build_release.py \
  --version v0.1.0-rc.1 \
  --source-ref v0.1.0-rc.1 \
  --source-revision "$(git rev-parse HEAD)" \
  --output dist
python3 scripts/validate_release.py \
  --bundle dist/parts-tally-v0.1.0-rc.1.zip
```

The archive contains:

- Gerber X2 copper, mask, paste, silkscreen, and Edge.Cuts layers;
- separate plated/non-plated Excellon drills plus an SVG drill map;
- KiCad and JLCPCB-format BOMs plus a normalized placement file;
- schematic PDF, assembly SVGs, and PCB renders;
- ERC/DRC/parity reports and a command log;
- editable KiCad/OpenSCAD sources, assembly/bring-up instructions, release report, and license notices;
- a per-file `SHA256SUMS` plus an archive checksum.

## Fabrication/assembly assumptions

The selected validation profile is JLCPCB's documented standard two-layer capability. The source rules are more conservative than its published minimums: 0.15 mm minimum track, 0.20 mm clearance, 0.60/0.30 mm via, and 0.50 mm copper-edge clearance.

This RC is suitable for **quote/DFM review**, not an unattended order:

1. Keep 100 × 60 mm, two layers, 1.6 mm nominal FR-4 unless a reviewed change is made.
2. Review the rendered files and confirm the outline, polarity, pin 1, antenna keepout, and drill split.
3. J1 has two bottom-tented, unfilled 0.60/0.30 mm through-vias inside VBUS pads. For PCBA, obtain explicit assembly-process approval for solder-wicking risk or use documented hand solder/rework. Do not represent tenting as plugging/filling.
4. The JLCPCB BOM intentionally leaves `LCSC Part #` blank for user-sourced items. It is a parity-checked assembly aid, not a guarantee that every part is available for turnkey PCBA.
5. Re-check C189895/SM04B-GHS-TB(LF)(SN), all blank supplier IDs, prices, stock, substitutions, rotations, and feeder class at checkout.
6. No substitute connector/module/ADC inherits this review. Re-run ERC, DRC, BOM/CPL parity, and datasheet pin/package review after any substitution.
7. Order a stencil only if the chosen assembly path needs one. For hand assembly, inspect USB-C and SOIC solder joints before power.

## Evidence boundary

A release archive, render, successful build, static analyzer, or simulated fixture is not physical evidence. Bench and field verification remain pending until an identified physical assembly is tested with dated raw measurements under `docs/verification-plan.md` and `docs/assembly-and-bring-up.md`.
