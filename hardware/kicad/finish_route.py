#!/usr/bin/env python3
"""Complete the single TP2 branch left after the validated autoroute."""

from pathlib import Path
import argparse
import pcbnew


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("board", type=Path)
    args = parser.parse_args()
    board = pcbnew.LoadBoard(str(args.board))
    net = board.GetNetsByName()["/+5V_XIAO"]
    points = [(44.0, 13.0), (44.0, 10.0), (46.7304, 6.2054)]
    for start, end in zip(points, points[1:]):
        track = pcbnew.PCB_TRACK(board)
        track.SetNet(net)
        track.SetLayer(pcbnew.F_Cu)
        track.SetStart(pcbnew.VECTOR2I_MM(*start))
        track.SetEnd(pcbnew.VECTOR2I_MM(*end))
        track.SetWidth(pcbnew.FromMM(0.50))
        board.Add(track)
    pcbnew.SaveBoard(str(args.board), board)
    print("connected TP2 to the +5V_XIAO route with a 0.50 mm F.Cu branch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
