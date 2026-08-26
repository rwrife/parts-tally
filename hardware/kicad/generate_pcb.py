#!/usr/bin/env python3
"""Generate the routed-board starting point for the Parts Tally carrier.

Run this script with KiCad 9's Python interpreter after exporting a KiCad XML
netlist from parts-tally.kicad_sch.  The generated .kicad_pcb remains editable
in KiCad; this script makes reviewed placement, rule areas, and pin-net import
repeatable.
"""

from __future__ import annotations

import argparse
import math
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pcbnew

BOARD_WIDTH_MM = 100.0
BOARD_HEIGHT_MM = 60.0

# Rotation is chosen so the XIAO's own USB-C faces the right board edge.  The
# ESP32-C3 antenna is at the opposite end (positive local Y in the project
# footprint), over the named copper rule area and facing an additional
# no-component/no-copper clearance region.
PLACEMENTS: dict[str, tuple[float, float, float]] = {
    "J1": (14.0, 4.8, 0.0),
    "R1": (10.0, 11.0, 0.0),
    "R2": (16.0, 11.0, 0.0),
    "D1": (23.0, 10.0, 90.0),
    "C11": (24.0, 5.0, 0.0),
    "F1": (32.0, 5.0, 0.0),
    "D2": (40.0, 5.0, 0.0),
    "C1": (47.0, 5.0, 0.0),
    "C2": (52.0, 5.0, 0.0),
    "TP1": (27.0, 13.0, 0.0),
    "TP2": (44.0, 13.0, 0.0),
    "U1": (86.0, 18.0, 270.0),
    "C3": (70.0, 12.0, 0.0),
    "C4": (70.0, 16.0, 0.0),
    "TP3": (68.0, 21.0, 0.0),
    "J2": (6.0, 42.0, 90.0),
    "R3": (14.0, 39.0, 0.0),
    "R4": (14.0, 45.0, 0.0),
    "C8": (20.0, 42.0, 90.0),
    "U2": (29.0, 42.0, 0.0),
    "C5": (36.0, 37.0, 0.0),
    "C6": (36.0, 41.0, 0.0),
    "C7": (23.0, 49.0, 0.0),
    "C9": (29.0, 50.0, 0.0),
    "R5": (43.0, 35.0, 0.0),
    "R6": (43.0, 39.0, 0.0),
    "TP5": (12.0, 52.0, 0.0),
    "TP8": (18.0, 52.0, 0.0),
    "TP9": (24.0, 56.0, 0.0),
    "TP10": (30.0, 56.0, 0.0),
    "R7": (49.0, 50.0, 0.0),
    "C10": (55.0, 49.0, 0.0),
    "SW1": (56.0, 56.0, 0.0),
    "R8": (64.0, 48.0, 0.0),
    "R9": (68.0, 48.0, 0.0),
    "R10": (72.0, 48.0, 0.0),
    "D3": (72.0, 55.0, 0.0),
    "TP4": (42.0, 56.0, 0.0),
    "TP6": (48.0, 31.0, 0.0),
    "TP7": (53.0, 31.0, 0.0),
    "J3": (90.0, 43.0, 90.0),
}

MOUNTING_HOLES = {
    "H1": (4.0, 4.0),
    "H2": (64.0, 4.0),
    "H3": (4.0, 56.0),
    "H4": (96.0, 56.0),
}

def mm(value: float) -> int:
    return pcbnew.FromMM(value)


def point(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I_MM(x, y)


def standard_footprint_root() -> Path:
    return Path(os.environ.get("KICAD_FOOTPRINT_DIR", "/usr/share/kicad/footprints"))


def load_footprint(fp_id: str, project_dir: Path) -> pcbnew.FOOTPRINT:
    library, name = fp_id.split(":", 1)
    if library == "parts-tally":
        library_path = project_dir / "lib" / "parts-tally.pretty"
    else:
        library_path = standard_footprint_root() / f"{library}.pretty"
    footprint = pcbnew.FootprintLoad(str(library_path), name)
    if footprint is None:
        raise SystemExit(f"unable to load footprint {fp_id} from {library_path}")
    return footprint


def add_outline(board: pcbnew.BOARD) -> None:
    corners = [
        (0.0, 0.0),
        (BOARD_WIDTH_MM, 0.0),
        (BOARD_WIDTH_MM, BOARD_HEIGHT_MM),
        (0.0, BOARD_HEIGHT_MM),
    ]
    for start, end in zip(corners, corners[1:] + corners[:1]):
        segment = pcbnew.PCB_SHAPE(board)
        segment.SetShape(pcbnew.SHAPE_T_SEGMENT)
        segment.SetLayer(pcbnew.Edge_Cuts)
        segment.SetStart(point(*start))
        segment.SetEnd(point(*end))
        segment.SetWidth(mm(0.05))
        board.Add(segment)


def rotate_local(cx: float, cy: float, degrees: float, x: float, y: float) -> tuple[float, float]:
    # KiCad board coordinates have Y increasing downward, so positive footprint
    # orientation is clockwise in this Cartesian helper.
    theta = math.radians(-degrees)
    return (
        cx + x * math.cos(theta) - y * math.sin(theta),
        cy + x * math.sin(theta) + y * math.cos(theta),
    )


def rotated_rectangle(
    center: tuple[float, float], degrees: float, x1: float, y1: float, x2: float, y2: float
) -> list[tuple[float, float]]:
    cx, cy = center
    return [
        rotate_local(cx, cy, degrees, x1, y1),
        rotate_local(cx, cy, degrees, x2, y1),
        rotate_local(cx, cy, degrees, x2, y2),
        rotate_local(cx, cy, degrees, x1, y2),
    ]


def add_rule_area(
    board: pcbnew.BOARD,
    name: str,
    polygon: list[tuple[float, float]],
    *,
    block_footprints: bool,
    block_pads: bool,
) -> None:
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer)
        zone.SetZoneName(name)
        zone.SetIsRuleArea(True)
        zone.SetDoNotAllowCopperPour(True)
        zone.SetDoNotAllowTracks(True)
        zone.SetDoNotAllowVias(True)
        zone.SetDoNotAllowPads(block_pads)
        zone.SetDoNotAllowFootprints(block_footprints)
        outline = zone.Outline()
        outline.NewOutline()
        for x, y in polygon:
            outline.Append(mm(x), mm(y))
        board.Add(zone)


def add_antenna_rule_areas(board: pcbnew.BOARD) -> None:
    ux, uy, rotation = PLACEMENTS["U1"]
    copper_keepout = rotated_rectangle((ux, uy), rotation, -7.0, 1.5, 6.8, 7.4)
    component_clearance = rotated_rectangle((ux, uy), rotation, -12.0, 7.7, 10.0, 13.0)
    add_rule_area(
        board,
        "XIAO ANTENNA - NO COPPER/TRACKS/VIAS",
        copper_keepout,
        block_footprints=False,
        block_pads=False,
    )
    add_rule_area(
        board,
        "XIAO ANTENNA CLEARANCE - NO COMPONENTS/COPPER",
        component_clearance,
        block_footprints=True,
        block_pads=True,
    )


def add_text(
    board: pcbnew.BOARD,
    text: str,
    x: float,
    y: float,
    *,
    layer: int = pcbnew.F_SilkS,
    size: float = 0.9,
    rotation: float = 0.0,
) -> None:
    item = pcbnew.PCB_TEXT(board)
    item.SetText(text)
    item.SetPosition(point(x, y))
    item.SetLayer(layer)
    size = max(size, 0.8)
    item.SetTextSize(pcbnew.VECTOR2I_MM(size, size))
    item.SetTextThickness(mm(max(0.12, size * 0.15)))
    item.SetTextAngle(pcbnew.EDA_ANGLE(rotation, pcbnew.DEGREES_T))
    board.Add(item)


def add_documentation(board: pcbnew.BOARD) -> None:
    add_text(board, "PARTS TALLY REV A0 - USB/SELV ONLY", 50.0, 58.5, size=0.8)
    add_text(board, "POWER ONLY", 14.0, 14.0, size=0.8)
    add_text(board, "J2: 1 E+  2 E-  3 S+  4 S-", 13.0, 34.0, size=0.8)
    add_text(board, "3V3 UART", 87.0, 48.0, size=0.8, rotation=90.0)
    add_text(board, "TARE / CAL", 58.0, 52.5, size=0.8)
    add_text(board, "STATUS", 74.0, 52.0, size=0.8)
    add_text(board, "XIAO USB / RECOVERY", 98.5, 18.0, size=0.8, rotation=90.0)
    add_text(board, "ANTENNA KEEP CLEAR", 75.8, 18.0, layer=pcbnew.F_Fab, size=0.8, rotation=90.0)
    for ref, label in {
        "TP1": "VBUS",
        "TP2": "5V",
        "TP3": "3V3",
        "TP4": "GND",
        "TP5": "AVDD",
        "TP6": "SDA",
        "TP7": "SCL",
        "TP8": "AIN+",
        "TP9": "AIN-",
        "TP10": "VBG",
    }.items():
        x, y, _ = PLACEMENTS[ref]
        add_text(board, label, x, y - 2.4, size=0.8)


def configure_rules(board: pcbnew.BOARD) -> None:
    settings = board.GetDesignSettings()
    settings.m_TrackMinWidth = mm(0.20)
    settings.m_MinClearance = mm(0.20)
    settings.m_ViasMinSize = mm(0.60)
    settings.m_MinThroughDrill = mm(0.30)
    settings.m_HoleClearance = mm(0.25)
    settings.m_CopperEdgeClearance = mm(0.50)
    settings.m_SilkClearance = mm(0.20)
    settings.m_BoardThickness = mm(1.60)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--netlist", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("parts-tally.kicad_pcb"))
    args = parser.parse_args()

    project_dir = Path(__file__).resolve().parent
    root = ET.parse(args.netlist).getroot()
    components = root.findall("./components/comp")
    refs = {component.get("ref", "") for component in components}
    if refs != set(PLACEMENTS):
        missing = sorted(refs - set(PLACEMENTS))
        extra = sorted(set(PLACEMENTS) - refs)
        raise SystemExit(f"placement map mismatch: missing={missing} extra={extra}")

    board = pcbnew.BOARD()
    board.SetFileName(str(args.output))
    configure_rules(board)
    add_outline(board)

    footprints: dict[str, pcbnew.FOOTPRINT] = {}
    for component in components:
        ref = component.get("ref", "")
        fp_id = component.findtext("footprint", "")
        if not fp_id:
            raise SystemExit(f"{ref} has no footprint in the XML netlist")
        footprint = load_footprint(fp_id, project_dir)
        footprint.SetFPIDAsString(fp_id)
        x, y, rotation = PLACEMENTS[ref]
        footprint.SetReference(ref)
        footprint.SetValue(component.findtext("value", ""))
        footprint.SetPosition(point(x, y))
        footprint.SetOrientationDegrees(rotation)
        footprint.Reference().SetTextSize(pcbnew.VECTOR2I_MM(0.8, 0.8))
        footprint.Reference().SetTextThickness(mm(0.12))
        if ref.startswith("TP") or ref in {"D3", "SW1"}:
            footprint.Reference().SetVisible(False)
        if ref == "J1":
            footprint.Reference().SetPosition(point(14.0, 8.5))
        footprint.Value().SetVisible(False)
        board.Add(footprint)
        footprints[ref] = footprint

    for ref, (x, y) in MOUNTING_HOLES.items():
        footprint = load_footprint("MountingHole:MountingHole_3.2mm_M3", project_dir)
        footprint.SetReference(ref)
        footprint.SetValue("M3 PCB MOUNT - NOT IN SCALE FORCE PATH")
        footprint.SetBoardOnly(True)
        footprint.SetPosition(point(x, y))
        footprint.Reference().SetTextSize(pcbnew.VECTOR2I_MM(0.8, 0.8))
        footprint.Reference().SetVisible(False)
        footprint.Value().SetVisible(False)
        board.Add(footprint)

    net_items: dict[str, pcbnew.NETINFO_ITEM] = {}
    assigned_nodes = 0
    for net in root.findall("./nets/net"):
        name = net.get("name", "")
        net_item = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net_item)
        net_items[name] = net_item
        for node in net.findall("node"):
            ref = node.get("ref", "")
            pin = node.get("pin", "")
            matching_pads = [pad for pad in footprints[ref].Pads() if pad.GetNumber() == pin]
            if not matching_pads:
                raise SystemExit(f"netlist node {ref}.{pin} has no matching footprint pad")
            for pad in matching_pads:
                pad.SetNet(net_item)
                assigned_nodes += 1

    add_antenna_rule_areas(board)
    add_documentation(board)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(args.output), board)
    print(
        f"generated {args.output}: {len(footprints)} schematic footprints + "
        f"{len(MOUNTING_HOLES)} mounting holes, {len(net_items)} nets, "
        f"{assigned_nodes} assigned pads, {board.GetAreaCount()} enforceable antenna rule areas"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
