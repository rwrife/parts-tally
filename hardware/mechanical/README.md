# Mechanical platform source

`parts-tally-platform.scad` is the editable, parametric revision-A0 mechanical source for the carrier, TAL220B load cell, top plate/bin cradle, strain relief, non-slip feet, PCB mounts, and adjustable overload stops. Attached bosses, rails, brackets, and contact pads overlap their parent plate by 0.1 mm so each export is one printable manifold volume rather than a collection of merely coplanar shells.

## Evidence and dimensions

- The manufacturer TAL220B drawing at `https://cdn.sparkfun.com/assets/e/5/f/5/6/TAL220B.pdf` (tracked SHA-256 `641b4150169e53e4e1fd33bc859d30ca371204243dc30b9987d6048ffd021181`) specifies a 55 × 12.7 × 12.7 mm body, 40 mm mounting-hole centre spacing, and M5 passages.
- PCB size and hole coordinates come from `../kicad/parts-tally.kicad_pcb`: 100 × 60 mm; board coordinates (4,4), (64,4), (4,56), and (96,56) mm.
- The XIAO antenna reference volume is derived from the KiCad rule areas. It is a mechanical keep-clear volume: no metal, fastener, cable loop, or shield may enter it.

## Force path

The top plate connects only to the load cell's free end. The load cell's fixed end connects to the base. Both printed M5 passages are centered on the drawing's ±20 mm load-cell hole centers; export-time OpenSCAD assertions fail if either mount origin drifts out of alignment. Four solid 12 mm underside pads provide collision surfaces; there are no through-access holes at the contact points. Each lower boss models a 6.2 × 6 mm M4 heat-set-insert pocket plus a 13.2 mm engaged/protruding nylon-tip M4 set screw and jam-nut reference. The modeled screw-tip plane—not the bare boss top—is `stop_nominal_gap` below the pad. Adjust and lock the screws before installing the top platform. Verify all dimensions against the purchased inserts/screws. The PCB is mounted on separate M3 standoffs below the platform and is not a structural member.

`stop_nominal_gap = 0.8` mm is only a printable setup target. Set the real stop gap using a current-limited, controlled load procedure so contact occurs below the TAL220B 120% full-scale safe-overload boundary. Print tolerance is not calibration evidence.

## Export

Open in OpenSCAD and set `part` to `base`, `platform`, `stop_gauge`, or `assembly`. Command-line examples:

```bash
openscad -D 'part="base"' -o generated/parts-tally-base.stl parts-tally-platform.scad
openscad -D 'part="platform"' -o generated/parts-tally-platform.stl parts-tally-platform.scad
openscad -D 'part="assembly"' --imgsize=1600,1000 -o generated/parts-tally-assembly.png parts-tally-platform.scad
python validate_stl.py generated/parts-tally-base.stl generated/parts-tally-platform.stl
```

The validator checks each ASCII STL for finite/non-collinear triangles, one edge-connected shell, exactly two oppositely directed facets per edge, and a single-cycle link around every vertex. It rejects empty, degenerate, open, disconnected, inconsistently wound, and topologically non-manifold output. It does not replace slicer review or detect every possible triangle self-intersection.

## Fabrication gaps

This CAD is static/manufacturer-drawing evidence only. Before fabrication, measure the purchased cell, selected bin, connector/cable bend radii, enclosure wall process, printer/material shrinkage, and fastener stack. No fixture has been printed, assembled, loaded, or measured. Keep the device USB/SELV-only and do not use it as a structural or certified scale.
