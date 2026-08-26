#!/usr/bin/env python3
"""Specctra DSN/SES exchange and copper-pour finalization for Parts Tally."""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew

POWER_NETS = {"/VBUS", "/VBUS_FUSED", "/+5V_XIAO"}
ANALOG_NETS = {"/AVDD_3V0", "/LC_S+", "/LC_S-", "/AIN+", "/AIN-", "/VBG", "/PGA_CFILTER"}


def mm(value: float) -> int:
    return pcbnew.FromMM(value)


def make_class(name: str, width: float) -> pcbnew.NETCLASS:
    netclass = pcbnew.NETCLASS(name)
    netclass.SetClearance(mm(0.20))
    netclass.SetTrackWidth(mm(width))
    netclass.SetViaDiameter(mm(0.60))
    netclass.SetViaDrill(mm(0.30))
    return netclass


def apply_netclasses(board: pcbnew.BOARD) -> dict[str, pcbnew.NETCLASS]:
    classes = {
        "Default": make_class("Default", 0.25),
        "POWER": make_class("POWER", 0.50),
        "SENSITIVE_ANALOG": make_class("SENSITIVE_ANALOG", 0.25),
    }
    class_map = board.GetNetClasses()
    for name, netclass in classes.items():
        class_map[name] = netclass
    for name, net in board.GetNetsByName().items():
        if name in POWER_NETS:
            net.SetNetClass(classes["POWER"])
        elif name in ANALOG_NETS:
            net.SetNetClass(classes["SENSITIVE_ANALOG"])
        else:
            net.SetNetClass(classes["Default"])
    board.SynchronizeNetsAndNetClasses(True)
    return classes


def export_dsn(board_path: Path, output: Path) -> None:
    board = pcbnew.LoadBoard(str(board_path))
    apply_netclasses(board)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not pcbnew.ExportSpecctraDSN(board, str(output)):
        raise SystemExit("KiCad failed to export Specctra DSN")
    print(f"exported {output} with POWER=0.50mm, SENSITIVE_ANALOG=0.25mm, Default=0.25mm")


def import_ses(board_path: Path, session: Path) -> None:
    board = pcbnew.LoadBoard(str(board_path))
    apply_netclasses(board)
    if not pcbnew.ImportSpecctraSES(board, str(session)):
        raise SystemExit("KiCad failed to import Specctra session")
    # FreeRouting may use short 0.15 mm neck-downs at fine-pitch pads while the
    # DSN and named classes retain 0.20 mm or wider general routing.
    board.GetDesignSettings().m_TrackMinWidth = mm(0.15)
    pcbnew.SaveBoard(str(board_path), board)
    print(
        f"imported {session}: tracks={len(list(board.GetTracks()))}, "
        f"vias={sum(1 for item in board.GetTracks() if isinstance(item, pcbnew.PCB_VIA))}"
    )


def add_ground_zones(board_path: Path) -> None:
    board = pcbnew.LoadBoard(str(board_path))
    nets = board.GetNetsByName()
    ground = nets["/GND"] if nets.has_key("/GND") else None
    if ground is None:
        raise SystemExit("/GND net not found")
    copper_zones = [zone for zone in board.Zones() if not zone.GetIsRuleArea()]
    if copper_zones:
        for zone in copper_zones:
            zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    else:
        for layer, priority in ((pcbnew.B_Cu, 0), (pcbnew.F_Cu, 1)):
            zone = pcbnew.ZONE(board)
            zone.SetLayer(layer)
            zone.SetNet(ground)
            zone.SetZoneName("GND RETURN PLANE" if layer == pcbnew.B_Cu else "GND TOP POUR")
            zone.SetLocalClearance(mm(0.30))
            zone.SetMinThickness(mm(0.20))
            zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
            zone.SetAssignedPriority(priority)
            outline = zone.Outline()
            outline.NewOutline()
            for x, y in ((0.5, 0.5), (99.5, 0.5), (99.5, 59.5), (0.5, 59.5)):
                outline.Append(mm(x), mm(y))
            board.Add(zone)
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(str(board_path), board)
    print(f"filled F.Cu/B.Cu GND pours; total zones/rule areas={board.GetAreaCount()}")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export-dsn")
    export.add_argument("board", type=Path)
    export.add_argument("output", type=Path)
    imp = sub.add_parser("import-ses")
    imp.add_argument("board", type=Path)
    imp.add_argument("session", type=Path)
    zones = sub.add_parser("add-ground-zones")
    zones.add_argument("board", type=Path)
    args = parser.parse_args()
    if args.command == "export-dsn":
        export_dsn(args.board, args.output)
    elif args.command == "import-ses":
        import_ses(args.board, args.session)
    else:
        add_ground_zones(args.board)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
