#!/usr/bin/env python3
"""Add fixed keepout-safe routes before FreeRouting handles the remainder."""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew


def mm(value: float) -> int:
    return pcbnew.FromMM(value)


def pt(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I_MM(x, y)


def segment(board, net, layer, start, end, width):
    track = pcbnew.PCB_TRACK(board)
    track.SetNet(net)
    track.SetLayer(layer)
    track.SetStart(pt(*start))
    track.SetEnd(pt(*end))
    track.SetWidth(mm(width))
    board.Add(track)


def path(board, net, layer, points, width):
    for start, end in zip(points, points[1:]):
        segment(board, net, layer, start, end, width)


def via(board, net, at, diameter=0.60, drill=0.30, *, tent_back=False):
    item = pcbnew.PCB_VIA(board)
    item.SetNet(net)
    item.SetPosition(pt(*at))
    item.SetWidth(mm(diameter))
    item.SetDrill(mm(drill))
    item.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    if tent_back:
        item.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
    board.Add(item)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("board", type=Path)
    args = parser.parse_args()
    board = pcbnew.LoadBoard(str(args.board))
    nets = board.GetNetsByName()

    # Tie the duplicated USB-C VBUS pad locations and reach the protected input
    # chain before the general router sees the connector.
    vbus = nets["/VBUS"]
    via(board, vbus, (11.60,1.12), tent_back=True)
    via(board, vbus, (16.40,1.12), tent_back=True)
    path(board, vbus, pcbnew.B_Cu, [(11.60,1.12), (16.40,1.12)], 0.50)

    # Route the I2C pair through the clear top corridor on B.Cu, then terminate
    # at adjacent vias beside U2.  This avoids front-side test pads/components
    # and keeps the pair parallel outside the antenna rule areas.
    scl = nets["/I2C_SCL"]
    path(board, scl, pcbnew.F_Cu, [(82.72,9.40), (82.72,5.2)], 0.25)
    via(board, scl, (82.72,5.2))
    path(board, scl, pcbnew.B_Cu,
         [(82.72,5.2), (70.0,5.2), (70.0,30.0), (46.0,30.0),
          (38.0,34.0), (33.0,41.365)], 0.25)
    via(board, scl, (33.0,41.365))
    path(board, scl, pcbnew.F_Cu, [(33.0,41.365), (31.475,41.365)], 0.25)

    sda = nets["/I2C_SDA"]
    path(board, sda, pcbnew.F_Cu, [(85.26,9.40), (85.26,3.0)], 0.25)
    via(board, sda, (85.26,3.0))
    path(board, sda, pcbnew.B_Cu,
         [(85.26,3.0), (68.0,3.0), (68.0,28.0), (44.0,28.0),
          (36.0,33.0), (33.0,40.095)], 0.25)
    via(board, sda, (33.0,40.095))
    path(board, sda, pcbnew.F_Cu, [(33.0,40.095), (31.475,40.095)], 0.25)

    # Bring +5 V around the lower side of the antenna keepout on B.Cu.  Short
    # F.Cu stubs reach the XIAO and C2 power-chain pad.
    five = nets["/+5V_XIAO"]
    path(board, five, pcbnew.F_Cu, [(95.42,25.425), (97.0,29.0)], 0.50)
    via(board, five, (97.0,29.0))
    path(board, five, pcbnew.B_Cu, [(97.0,29.0), (94.0,34.0), (72.0,38.0)], 0.50)
    via(board, five, (72.0,38.0))
    path(board, five, pcbnew.F_Cu, [(72.0,38.0), (60.0,38.0), (56.0,10.0), (51.225,5.0)], 0.50)

    pcbnew.SaveBoard(str(args.board), board)
    print("pre-routed VBUS, I2C_SCL, I2C_SDA, and +5V_XIAO around antenna rule areas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
