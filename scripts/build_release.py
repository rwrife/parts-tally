#!/usr/bin/env python3
"""Build the Parts Tally fabrication/release archive with KiCad 9."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMATIC = ROOT / "hardware/kicad/parts-tally.kicad_sch"
PCB = ROOT / "hardware/kicad/parts-tally.kicad_pcb"
PROJECT = ROOT / "hardware/kicad/parts-tally.kicad_pro"
BOM = ROOT / "bom/bom.csv"
MANIFEST_TEMPLATE = ROOT / "release/manifest.json"
GERBER_LAYERS = (
    "F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,"
    "F.Mask,B.Mask,Edge.Cuts"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def split_refs(value: str) -> list[str]:
    return [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]


def observed_time() -> dt.datetime:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        return dt.datetime.fromtimestamp(int(epoch), tz=dt.timezone.utc)
    return dt.datetime.now(tz=dt.timezone.utc)


def run(command: list[str], log: list[str]) -> None:
    rendered = " ".join(command)
    print(f"+ {rendered}")
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    log.append(f"$ {rendered}\n{completed.stdout}{completed.stderr}")
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    if completed.returncode:
        raise SystemExit(f"command failed ({completed.returncode}): {rendered}")


def write_jlc_bom(output: Path, source_path: Path = BOM) -> Counter[str]:
    references: Counter[str] = Counter()
    with source_path.open(newline="", encoding="utf-8") as source, output.open(
        "w", newline="", encoding="utf-8"
    ) as destination:
        reader = csv.DictReader(source)
        fieldnames = [
            "Comment",
            "Designator",
            "Footprint",
            "LCSC Part #",
            "MPN",
            "Manufacturer",
            "Quantity",
            "Notes",
        ]
        writer = csv.DictWriter(destination, fieldnames=fieldnames)
        writer.writeheader()
        for row in reader:
            refs = split_refs(row["Reference"])
            if not refs or len(refs) != int(row["Qty"]):
                raise SystemExit(
                    f"BOM quantity/reference mismatch for {row.get('Reference', '')!r}: "
                    f"Qty={row.get('Qty')!r}, references={refs}"
                )
            if len(refs) != len(set(refs)):
                raise SystemExit(f"duplicate BOM designators within row: {refs}")
            duplicates = sorted(ref for ref in refs if references[ref])
            if duplicates:
                raise SystemExit(f"duplicate BOM designators: {duplicates}")
            references.update(refs)
            supplier_pn = row.get("Supplier PN", "").strip()
            lcsc = supplier_pn if supplier_pn.startswith("C") and supplier_pn[1:].isdigit() else ""
            writer.writerow(
                {
                    "Comment": row["Value"],
                    "Designator": ",".join(refs),
                    "Footprint": row["Footprint"],
                    "LCSC Part #": lcsc,
                    "MPN": row["MPN"],
                    "Manufacturer": row["Manufacturer"],
                    "Quantity": row["Qty"],
                    "Notes": row.get("BOM Comments", ""),
                }
            )
    return references


def normalize_placement(source: Path, destination: Path) -> Counter[str]:
    aliases = {
        "ref": ("Ref", "Reference", "Designator"),
        "x": ("PosX", "Mid X", "X"),
        "y": ("PosY", "Mid Y", "Y"),
        "side": ("Side", "Layer"),
        "rotation": ("Rot", "Rotation"),
    }

    with source.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise SystemExit("KiCad placement CSV has no header")
        fields = set(reader.fieldnames)

        def select(name: str) -> str:
            for candidate in aliases[name]:
                if candidate in fields:
                    return candidate
            raise SystemExit(f"KiCad placement CSV lacks {name}: {reader.fieldnames}")

        selected = {name: select(name) for name in aliases}
        rows = list(reader)

    references: Counter[str] = Counter()
    with destination.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=["Designator", "Mid X", "Mid Y", "Layer", "Rotation"]
        )
        writer.writeheader()
        for row in rows:
            reference = row[selected["ref"]].strip()
            if not reference:
                raise SystemExit("placement row has an empty reference")
            references[reference] += 1
            if references[reference] != 1:
                raise SystemExit(f"duplicate placement designator: {reference}")
            raw_side = row[selected["side"]].strip().lower()
            if raw_side in {"front", "top", "f.cu"}:
                layer = "Top"
            elif raw_side in {"back", "bottom", "b.cu"}:
                layer = "Bottom"
            else:
                raise SystemExit(f"unknown placement side for {reference}: {raw_side!r}")
            try:
                x = float(row[selected["x"]].strip())
                y = float(row[selected["y"]].strip())
                rotation = float(row[selected["rotation"]].strip())
            except ValueError as exc:
                raise SystemExit(f"non-numeric placement for {reference}") from exc
            if not all(math.isfinite(value) for value in (x, y, rotation)):
                raise SystemExit(f"non-finite placement for {reference}")
            writer.writerow(
                {
                    "Designator": reference,
                    "Mid X": f"{x:g}mm",
                    "Mid Y": f"{y:g}mm",
                    "Layer": layer,
                    "Rotation": f"{rotation:g}",
                }
            )
    return references


def copy_sources(stage: Path, base_stl: Path, platform_stl: Path) -> None:
    source_root = stage / "sources"
    documentation = stage / "documentation"
    licenses = stage / "licenses"
    documentation.mkdir(parents=True)
    licenses.mkdir(parents=True)

    source_ignores = shutil.ignore_patterns(
        "__pycache__", "*.pyc", ".pio", "node_modules", "dist",
        "test-results", "playwright-report", "compile_commands.json",
        "pdfs", "*.lck", "~*",
    )
    for directory in (
        "hardware", "firmware", "app", "docs", "tests", "scripts",
        "release", "bom", "LICENSES", ".github",
    ):
        shutil.copytree(ROOT / directory, source_root / directory, ignore=source_ignores)
    for name in ("README.md", "PLAN.md", "LICENSES.md", ".gitignore"):
        shutil.copy2(ROOT / name, source_root / name)

    generated = source_root / "hardware/mechanical/generated"
    generated.mkdir(parents=True, exist_ok=True)
    shutil.copy2(base_stl, generated / "parts-tally-base.stl")
    shutil.copy2(platform_stl, generated / "parts-tally-platform.stl")

    for path in (
        ROOT / "docs/assembly-and-bring-up.md",
        ROOT / "docs/verification-plan.md",
        ROOT / "docs/release-verification.md",
        ROOT / "release/README.md",
        ROOT / "release/RELEASE_NOTES.md",
    ):
        shutil.copy2(path, documentation / path.name)
    shutil.copy2(ROOT / "LICENSES.md", licenses)
    for path in sorted((ROOT / "LICENSES").glob("*.txt")):
        shutil.copy2(path, licenses / path.name)


def write_checksums(stage: Path) -> None:
    checksum_file = stage / "SHA256SUMS"
    files = [path for path in stage.rglob("*") if path.is_file() and path != checksum_file]
    lines = [f"{sha256(path)}  {path.relative_to(stage).as_posix()}" for path in sorted(files)]
    checksum_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_deterministic_zip(stage: Path, archive: Path, timestamp: dt.datetime) -> None:
    stamp = timestamp.astimezone(dt.timezone.utc)
    year = max(1980, stamp.year)
    zip_time = (year, stamp.month, stamp.day, stamp.hour, stamp.minute, stamp.second)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(item for item in stage.rglob("*") if item.is_file()):
            relative = Path(stage.name) / path.relative_to(stage)
            info = zipfile.ZipInfo(relative.as_posix(), zip_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, path.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument(
        "--base-stl",
        type=Path,
        default=ROOT / "hardware/mechanical/generated/parts-tally-base.stl",
    )
    parser.add_argument(
        "--platform-stl",
        type=Path,
        default=ROOT / "hardware/mechanical/generated/parts-tally-platform.stl",
    )
    args = parser.parse_args()

    version = args.version if args.version.startswith("v") else f"v{args.version}"
    template = json.loads(MANIFEST_TEMPLATE.read_text(encoding="utf-8"))
    if template["release"] != version:
        raise SystemExit(f"manifest release {template['release']} does not match {version}")

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    stage = output / f"parts-tally-{version}"
    archive = output / f"parts-tally-{version}.zip"
    if stage.exists() or archive.exists():
        raise SystemExit(f"refusing to overwrite existing release output under {output}")

    fabrication = stage / "fabrication"
    gerbers = fabrication / "gerbers"
    drills = fabrication / "drill"
    reports = stage / "reports"
    renders = stage / "renders"
    documentation = stage / "documentation"
    bom_dir = stage / "bom"
    for directory in (gerbers, drills, reports, renders, documentation, bom_dir):
        directory.mkdir(parents=True, exist_ok=True)

    command_log: list[str] = []
    netlist = reports / "parts-tally.xml"
    run(["kicad-cli", "sch", "erc", "--exit-code-violations", "-o", str(reports / "parts-tally-erc.rpt"), str(SCHEMATIC)], command_log)
    run(["kicad-cli", "sch", "export", "pdf", "-o", str(documentation / "parts-tally-schematic.pdf"), str(SCHEMATIC)], command_log)
    run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadxml", "-o", str(netlist), str(SCHEMATIC)], command_log)
    run(["python3", "hardware/kicad/validate_pcb.py", str(PCB), "--netlist", str(netlist)], command_log)
    run(["kicad-cli", "pcb", "drc", "--severity-all", "--all-track-errors", "--schematic-parity", "--exit-code-violations", "-o", str(reports / "parts-tally-drc.rpt"), str(PCB)], command_log)
    run(["kicad-cli", "pcb", "export", "gerbers", "-o", str(gerbers), "--layers", GERBER_LAYERS, "--subtract-soldermask", "--precision", "6", "--no-protel-ext", str(PCB)], command_log)
    run(["kicad-cli", "pcb", "export", "drill", "-o", str(drills), "--format", "excellon", "--excellon-units", "mm", "--excellon-zeros-format", "decimal", "--excellon-separate-th", "--generate-map", "--map-format", "svg", str(PCB)], command_log)

    raw_placement = fabrication / "parts-tally-kicad-position.csv"
    run(["kicad-cli", "pcb", "export", "pos", "-o", str(raw_placement), "--side", "both", "--format", "csv", "--units", "mm", "--exclude-dnp", str(PCB)], command_log)
    bom_refs = write_jlc_bom(bom_dir / "parts-tally-jlcpcb-bom.csv")
    placement_refs = normalize_placement(raw_placement, fabrication / "parts-tally-jlcpcb-cpl.csv")
    raw_placement.unlink()
    if placement_refs != bom_refs:
        raise SystemExit(
            "placement/BOM mismatch: "
            f"missing placement={sorted(bom_refs-placement_refs)}, "
            f"orphan placement={sorted(placement_refs-bom_refs)}"
        )

    run(["kicad-cli", "pcb", "export", "svg", "--mode-single", "--fit-page-to-board", "--exclude-drawing-sheet", "--black-and-white", "--sketch-pads-on-fab-layers", "--layers", "F.Fab,F.Silkscreen,Edge.Cuts", "-o", str(documentation / "parts-tally-front-assembly.svg"), str(PCB)], command_log)
    run(["kicad-cli", "pcb", "export", "svg", "--mode-single", "--fit-page-to-board", "--exclude-drawing-sheet", "--black-and-white", "--sketch-pads-on-fab-layers", "--mirror", "--layers", "B.Fab,B.Silkscreen,Edge.Cuts", "-o", str(documentation / "parts-tally-back-assembly.svg"), str(PCB)], command_log)
    for side in ("top", "bottom"):
        run(["kicad-cli", "pcb", "render", "--side", side, "--quality", "high", "--width", "1600", "--height", "1000", "--background", "opaque", "-o", str(renders / f"parts-tally-{side}.png"), str(PCB)], command_log)

    shutil.copy2(BOM, bom_dir / "parts-tally-bom.csv")
    shutil.copy2(ROOT / "bom/non-schematic-items.csv", bom_dir)
    copy_sources(stage, args.base_stl.resolve(), args.platform_stl.resolve())

    timestamp = observed_time()
    template["build"] = {
        "source_ref": args.source_ref,
        "source_revision": args.source_revision,
        "generated_utc": timestamp.isoformat().replace("+00:00", "Z"),
        "generator": "scripts/build_release.py",
        "kicad": "9.0 container series",
    }
    (stage / "release-manifest.json").write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
    (reports / "command-log.txt").write_text("\n".join(command_log) + "\n", encoding="utf-8")
    write_checksums(stage)
    write_deterministic_zip(stage, archive, timestamp)
    archive_hash = sha256(archive)
    (output / f"{archive.name}.sha256").write_text(f"{archive_hash}  {archive.name}\n", encoding="utf-8")
    print(f"release archive: {archive}")
    print(f"sha256: {archive_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
