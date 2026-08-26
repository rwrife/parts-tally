#!/usr/bin/env python3
"""Deterministic structural checks for the Parts Tally carrier PCB."""

from __future__ import annotations

import argparse
import math
from collections import Counter, defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET

import pcbnew

MM = pcbnew.FromMM(1.0)
EXPECTED_BOARD = (100.0, 60.0)
EXPECTED_HOLES = {
    "H1": (4.0, 4.0),
    "H2": (64.0, 4.0),
    "H3": (4.0, 56.0),
    "H4": (96.0, 56.0),
}
TEST_POINTS = {f"TP{i}" for i in range(1, 11)}
ANALOG_NETS = ("/LC_S+", "/LC_S-", "/AIN+", "/AIN-")
EXPECTED_RULE_AREAS = {
    "XIAO ANTENNA - NO COPPER/TRACKS/VIAS": {
        "bbox": (78.6, 11.0, 5.9, 13.8),
        "restrictions": (True, True, True, False, False),
    },
    "XIAO ANTENNA CLEARANCE - NO COMPONENTS/COPPER": {
        "bbox": (73.0, 6.0, 5.3, 22.0),
        "restrictions": (True, True, True, True, True),
    },
}


def close(actual: float, expected: float, tolerance: float = 0.02) -> bool:
    return math.isclose(actual, expected, abs_tol=tolerance)


def exported_netlist(path: Path):
    root = ET.parse(path).getroot()
    refs = {comp.attrib["ref"] for comp in root.findall("./components/comp")}
    nodes: dict[tuple[str, str], str] = {}
    for net in root.findall("./nets/net"):
        name = net.attrib["name"]
        for node in net.findall("node"):
            nodes[(node.attrib["ref"], node.attrib["pin"])] = name
    return refs, nodes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("board", type=Path)
    parser.add_argument("--netlist", required=True, type=Path)
    args = parser.parse_args()

    board = pcbnew.LoadBoard(str(args.board))
    refs_expected, nodes_expected = exported_netlist(args.netlist)
    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}
    errors: list[str] = []

    schematic_refs = set(footprints) - set(EXPECTED_HOLES)
    if schematic_refs != refs_expected:
        errors.append(
            f"footprint parity mismatch: missing={sorted(refs_expected-schematic_refs)} "
            f"extra={sorted(schematic_refs-refs_expected)}"
        )

    pcb_node_keys = {
        (ref, pad.GetNumber())
        for ref in refs_expected
        if (fp := footprints.get(ref)) is not None
        for pad in fp.Pads()
        if pad.GetNumber()
    }
    expected_node_keys = set(nodes_expected)
    missing_pads = sorted(expected_node_keys - pcb_node_keys)
    extra_pads = sorted(pcb_node_keys - expected_node_keys)
    if missing_pads or extra_pads:
        errors.append(
            f"pin/pad parity mismatch: missing PCB pads={missing_pads} "
            f"extra PCB pads={extra_pads}"
        )

    checked_pads = 0
    for ref in refs_expected:
        fp = footprints.get(ref)
        if fp is None:
            continue
        for pad in fp.Pads():
            number = pad.GetNumber()
            if not number:
                continue
            key = (ref, number)
            expected = nodes_expected.get(key)
            if expected is None:
                if not pad.GetNetname():
                    continue
                errors.append(f"{ref}.{number} has no schematic node")
                continue
            actual = pad.GetNetname()
            if actual != expected:
                errors.append(f"{ref}.{number}: PCB {actual!r} != schematic {expected!r}")
            checked_pads += 1

    bbox = board.GetBoardEdgesBoundingBox()
    width = bbox.GetWidth() / MM
    height = bbox.GetHeight() / MM
    if not (close(width, EXPECTED_BOARD[0], 0.06) and close(height, EXPECTED_BOARD[1], 0.06)):
        errors.append(f"board is {width:.3f} x {height:.3f} mm, expected 100 x 60 mm")
    if board.GetCopperLayerCount() != 2:
        errors.append(f"expected 2 copper layers, found {board.GetCopperLayerCount()}")

    for ref, expected_xy in EXPECTED_HOLES.items():
        fp = footprints.get(ref)
        if fp is None:
            errors.append(f"missing mounting hole {ref}")
            continue
        pos = fp.GetPosition()
        actual_xy = (pos.x / MM, pos.y / MM)
        pad = next(iter(fp.Pads()), None)
        drill = pad.GetDrillSize().x / MM if pad is not None else 0.0
        if not all(close(a, e) for a, e in zip(actual_xy, expected_xy)):
            errors.append(f"{ref} at {actual_xy}, expected {expected_xy}")
        if not close(drill, 3.2):
            errors.append(f"{ref} drill is {drill:.3f} mm, expected 3.2 mm")

    if not TEST_POINTS.issubset(footprints):
        errors.append(f"missing test points: {sorted(TEST_POINTS-set(footprints))}")

    u1 = footprints.get("U1")
    if u1 is None:
        errors.append("missing U1")
    else:
        pos = u1.GetPosition()
        u1_xy = (pos.x / MM, pos.y / MM)
        rotation = u1.GetOrientation().AsDegrees() % 360
        if not (close(u1_xy[0], 86.0) and close(u1_xy[1], 18.0) and close(rotation, 270.0)):
            errors.append(f"U1 placement is {u1_xy} @ {rotation:.1f}°, expected (86,18) @ 270°")

    rule_areas = [z for z in board.Zones() if z.GetIsRuleArea()]
    copper_zones = [z for z in board.Zones() if not z.GetIsRuleArea()]
    expected_zone_names = set(EXPECTED_RULE_AREAS)
    actual_zone_names = {z.GetZoneName() for z in rule_areas}
    if len(rule_areas) != 4 or actual_zone_names != expected_zone_names:
        errors.append(f"antenna rule-area names mismatch: {sorted(actual_zone_names)}")
    for name, expected in EXPECTED_RULE_AREAS.items():
        named_areas = [z for z in rule_areas if z.GetZoneName() == name]
        if {z.GetLayer() for z in named_areas} != {pcbnew.F_Cu, pcbnew.B_Cu}:
            errors.append(f"{name} must exist on F.Cu and B.Cu")
        for zone in named_areas:
            bbox = zone.GetBoundingBox()
            actual_bbox = (
                bbox.GetX() / MM,
                bbox.GetY() / MM,
                bbox.GetWidth() / MM,
                bbox.GetHeight() / MM,
            )
            if not all(close(actual, wanted, 0.03) for actual, wanted in zip(actual_bbox, expected["bbox"])):
                errors.append(f"{name} bbox {actual_bbox} != expected {expected['bbox']}")
            restrictions = (
                zone.GetDoNotAllowCopperPour(),
                zone.GetDoNotAllowTracks(),
                zone.GetDoNotAllowVias(),
                zone.GetDoNotAllowPads(),
                zone.GetDoNotAllowFootprints(),
            )
            if restrictions != expected["restrictions"]:
                errors.append(
                    f"{name} restrictions {restrictions} != expected {expected['restrictions']}"
                )
    zone_layers = {layer for z in copper_zones for layer in z.GetLayerSet().Seq()}
    if len(copper_zones) != 2 or zone_layers != {pcbnew.F_Cu, pcbnew.B_Cu}:
        errors.append("expected one F.Cu and one B.Cu copper zone")
    if any(z.GetNetname() != "/GND" for z in copper_zones):
        errors.append("all copper zones must be on /GND")
    if any(z.GetPadConnection() != pcbnew.ZONE_CONNECTION_FULL for z in copper_zones):
        errors.append("GND zones must use solid pad connections")

    widths: Counter[float] = Counter()
    lengths: defaultdict[str, float] = defaultdict(float)
    vias = 0
    gnd_vias = 0
    for item in board.GetTracks():
        net = item.GetNetname()
        if isinstance(item, pcbnew.PCB_VIA):
            vias += 1
            if net == "/GND":
                gnd_vias += 1
            continue
        width_mm = round(item.GetWidth() / MM, 3)
        widths[width_mm] += 1
        lengths[net] += item.GetLength() / MM
        if width_mm < 0.15 - 1e-6:
            errors.append(f"track on {net} is narrower than 0.15 mm: {width_mm:.3f} mm")

    for net in ("/VBUS", "/+5V_XIAO"):
        used = [item.GetWidth() / MM for item in board.GetTracks()
                if not isinstance(item, pcbnew.PCB_VIA) and item.GetNetname() == net]
        if not used or max(used) < 0.49:
            errors.append(f"power net {net} lacks a 0.50 mm trunk")
    used_3v3 = [item.GetWidth() / MM for item in board.GetTracks()
                if not isinstance(item, pcbnew.PCB_VIA) and item.GetNetname() == "/+3V3"]
    if not used_3v3 or min(used_3v3) < 0.19:
        errors.append("/+3V3 routing is narrower than the 0.20 mm low-current policy")

    cell_delta = abs(lengths["/LC_S+"] - lengths["/LC_S-"])
    sense_delta = abs(lengths["/AIN+"] - lengths["/AIN-"])
    if cell_delta > 3.0:
        errors.append(f"load-cell pair length delta {cell_delta:.2f} mm exceeds 3 mm")
    if sense_delta > 10.0:
        errors.append(f"ADC-filter pair length delta {sense_delta:.2f} mm exceeds 10 mm")

    print(f"board: {width:.1f} x {height:.1f} mm, {len(footprints)} footprints ({len(refs_expected)} schematic + 4 holes)")
    print(
        f"netlist parity: {checked_pads} physical PCB pads / {len(pcb_node_keys)} unique pin IDs "
        f"checked against {len(nodes_expected)} schematic nodes"
    )
    print(f"routing: {sum(widths.values())} segments, {vias} vias ({gnd_vias} GND), widths={dict(sorted(widths.items()))}")
    print(f"zones: {len(copper_zones)} GND pours + {len(rule_areas)} antenna rule areas")
    print("analog lengths (mm): " + ", ".join(f"{n}={lengths[n]:.2f}" for n in ANALOG_NETS))
    print(f"pair deltas: load-cell={cell_delta:.2f} mm, ADC-filter={sense_delta:.2f} mm")
    if errors:
        print(f"FAIL: {len(errors)} structural PCB error(s)")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS: PCB structure, netlist parity, mechanical constraints, keepouts, zones, and route policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
