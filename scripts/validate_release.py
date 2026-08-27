#!/usr/bin/env python3
"""Validate the Parts Tally release contract and generated archive."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import stat
import tempfile
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "release/manifest.json"
REQUIRED_SOURCE_FILES = (
    "hardware/kicad/parts-tally.kicad_pro",
    "hardware/kicad/parts-tally.kicad_sch",
    "hardware/kicad/parts-tally.kicad_pcb",
    "hardware/mechanical/parts-tally-platform.scad",
    "firmware/include/parts_tally/version.hpp",
    "app/package.json",
    "docs/assembly-and-bring-up.md",
    "docs/verification-plan.md",
    "release/README.md",
    "release/RELEASE_NOTES.md",
    "LICENSES.md",
)
EXPECTED_GERBER_MARKERS = (
    "F_Cu",
    "B_Cu",
    "F_Paste",
    "B_Paste",
    "F_Silkscreen",
    "B_Silkscreen",
    "F_Mask",
    "B_Mask",
    "Edge_Cuts",
)
REF_RE = re.compile(r"^[A-Z]+[0-9]+$")
MAX_ARCHIVE_MEMBERS = 1000
MAX_ARCHIVE_EXPANDED_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_MEMBER_BYTES = 25 * 1024 * 1024
MAX_COMPRESSION_RATIO = 1000


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def split_refs(value: str) -> list[str]:
    return [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]


def fail(message: str) -> NoReturn:
    raise SystemExit(f"release validation failed: {message}")


def archive_relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "." in path.parts:
        fail(f"unsafe archive-relative path: {value!r}")
    return path


def validate_manifest() -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        fail("manifest schema_version must be 1")
    if manifest.get("status") != "release-candidate":
        fail("manifest must remain an honest release-candidate")
    compatibility = manifest.get("compatibility", {})
    expected = {
        "carrier_board": "A0",
        "firmware": "0.2.0",
        "protocol": "parts-tally/v1",
        "app": "0.1.0",
    }
    for key, value in expected.items():
        if compatibility.get(key) != value:
            fail(f"compatibility {key} must be {value}")
    if manifest.get("source", {}).get("expected_tag") != manifest.get("release"):
        fail("expected tag must equal release")
    evidence = manifest.get("evidence", {})
    for key in (
        "static_analysis",
        "simulation",
        "software_tests",
        "target_compile",
        "bench",
        "field",
    ):
        if not evidence.get(key):
            fail(f"evidence field {key} is missing")
    if (
        evidence["bench"] != "not-performed-no-physical-prototype"
        or evidence["field"] != "not-performed-no-physical-prototype"
    ):
        fail("bench and field evidence must remain explicitly unperformed")
    safety = manifest.get("safety_scope", {})
    if (
        safety.get("power") != "USB 5 V SELV only"
        or safety.get("legal_for_trade") is not False
        or safety.get("safety_certified") is not False
    ):
        fail("USB/SELV, non-legal-for-trade, non-certified limits must remain explicit")

    profile = manifest.get("fabrication_profile", {})
    limits = {
        "minimum_track_mm": 0.127,
        "minimum_clearance_mm": 0.127,
        "minimum_via_diameter_mm": 0.45,
        "minimum_via_drill_mm": 0.2,
        "minimum_copper_edge_mm": 0.3,
    }
    for field, manufacturer_minimum in limits.items():
        if float(profile.get(field, 0)) < manufacturer_minimum:
            fail(f"{field} is below selected JLCPCB standard capability")
    for path in REQUIRED_SOURCE_FILES:
        if not (ROOT / path).is_file():
            fail(f"required source/document missing: {path}")
    return manifest


def read_designators(
    path: Path,
    column: str,
    *,
    quantity_column: str | None = None,
    single_per_row: bool = False,
) -> Counter[str]:
    refs: Counter[str] = Counter()
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or column not in reader.fieldnames:
            fail(f"{path.name} lacks {column}")
        for row in reader:
            row_refs = split_refs(row[column])
            if not row_refs or (single_per_row and len(row_refs) != 1):
                fail(f"invalid designator row in {path.name}: {row.get(column)!r}")
            if len(row_refs) != len(set(row_refs)):
                fail(f"duplicate designators within row in {path.name}: {row_refs}")
            if quantity_column is not None:
                if quantity_column not in row:
                    fail(f"{path.name} lacks {quantity_column}")
                try:
                    quantity = int(row[quantity_column])
                except (TypeError, ValueError):
                    fail(f"invalid quantity in {path.name}: {row.get(quantity_column)!r}")
                if quantity != len(row_refs):
                    fail(
                        f"quantity/designator mismatch in {path.name}: "
                        f"{quantity} != {len(row_refs)} for {row.get(column)!r}"
                    )
            duplicates = sorted(ref for ref in row_refs if refs[ref])
            if duplicates:
                fail(f"duplicate designators in {path.name}: {duplicates}")
            refs.update(row_refs)
    malformed = sorted(ref for ref in refs if not REF_RE.fullmatch(ref))
    if malformed:
        fail(f"malformed designators in {path.name}: {malformed}")
    return refs


def validate_cpl(path: Path) -> Counter[str]:
    refs = read_designators(path, "Designator", single_per_row=True)
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        required = {"Designator", "Mid X", "Mid Y", "Layer", "Rotation"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            fail(f"{path.name} lacks required CPL columns")
        for row in reader:
            if row["Layer"] not in {"Top", "Bottom"}:
                fail(f"invalid CPL layer for {row['Designator']}: {row['Layer']!r}")
            try:
                x = float(row["Mid X"].removesuffix("mm"))
                y = float(row["Mid Y"].removesuffix("mm"))
                rotation = float(row["Rotation"])
            except ValueError:
                fail(f"non-numeric CPL placement for {row['Designator']}")
            if not all(math.isfinite(value) for value in (x, y, rotation)):
                fail(f"non-finite CPL placement for {row['Designator']}")
    return refs


def validate_checksums(stage: Path) -> int:
    checksum_file = stage / "SHA256SUMS"
    if not checksum_file.is_file():
        fail("SHA256SUMS is missing")
    listed: set[str] = set()
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        expected, separator, relative = line.partition("  ")
        if not separator or len(expected) != 64:
            fail(f"malformed checksum line: {line}")
        safe_relative = archive_relative_path(relative)
        path = stage.joinpath(*safe_relative.parts)
        if not path.is_file():
            fail(f"checksum target missing: {relative}")
        if sha256(path) != expected:
            fail(f"checksum mismatch: {relative}")
        if relative in listed:
            fail(f"duplicate checksum path: {relative}")
        listed.add(relative)
    actual = {
        path.relative_to(stage).as_posix()
        for path in stage.rglob("*")
        if path.is_file() and path != checksum_file
    }
    if listed != actual:
        fail(
            f"checksum coverage mismatch: missing={sorted(actual-listed)} "
            f"extra={sorted(listed-actual)}"
        )
    return len(listed)


def validate_stage(stage: Path, expected_release: str) -> None:
    required = (
        "release-manifest.json",
        "SHA256SUMS",
        "reports/parts-tally-erc.rpt",
        "reports/parts-tally-drc.rpt",
        "reports/command-log.txt",
        "fabrication/parts-tally-jlcpcb-cpl.csv",
        "bom/parts-tally-bom.csv",
        "bom/parts-tally-jlcpcb-bom.csv",
        "documentation/parts-tally-schematic.pdf",
        "documentation/parts-tally-front-assembly.svg",
        "documentation/parts-tally-back-assembly.svg",
        "renders/parts-tally-top.png",
        "renders/parts-tally-bottom.png",
        "sources/hardware/kicad/parts-tally.kicad_pro",
        "sources/hardware/kicad/parts-tally.kicad_sch",
        "sources/hardware/kicad/parts-tally.kicad_pcb",
        "sources/hardware/mechanical/parts-tally-platform.scad",
        "sources/hardware/mechanical/generated/parts-tally-base.stl",
        "sources/hardware/mechanical/generated/parts-tally-platform.stl",
        "sources/firmware/include/parts_tally/version.hpp",
        "sources/app/package.json",
        "sources/app/scripts/generate-contract.mjs",
        "sources/app/vite.config.ts",
        "sources/app/playwright.config.ts",
        "sources/app/e2e/app.spec.ts",
        "sources/firmware/test/test_domain/test_main.cpp",
        "sources/docs/schemas/api-v1/status.schema.json",
        "sources/tests/fixtures/protocol/v1/status-stable.json",
        "sources/scripts/validate_release.py",
        "sources/release/requirements.lock",
        "sources/bom/bom.csv",
        "sources/docs/architecture-contract.json",
        "sources/PLAN.md",
    )
    for relative in required:
        path = stage / relative
        if not path.is_file() or path.stat().st_size == 0:
            fail(f"archive member missing or empty: {relative}")

    release_manifest = json.loads(
        (stage / "release-manifest.json").read_text(encoding="utf-8")
    )
    if release_manifest.get("release") != expected_release:
        fail("archive release does not match source manifest")
    build = release_manifest.get("build", {})
    if (
        not build.get("source_ref")
        or not build.get("source_revision")
        or not build.get("generated_utc")
    ):
        fail("archive build provenance is incomplete")
    if (
        expected_release.startswith("v")
        and build["source_ref"].startswith("v")
        and build["source_ref"] != expected_release
    ):
        fail("tagged build source_ref does not equal release")

    gerbers = sorted((stage / "fabrication/gerbers").glob("*.gbr"))
    names = {path.name for path in gerbers}
    for marker in EXPECTED_GERBER_MARKERS:
        if not any(marker in name for name in names):
            fail(f"Gerber layer missing: {marker}")
    if any(path.stat().st_size < 100 for path in gerbers):
        fail("one or more Gerber layers are unexpectedly small")
    drills = list((stage / "fabrication/drill").glob("*.drl"))
    if (
        len(drills) < 2
        or not any("PTH" in path.name for path in drills)
        or not any("NPTH" in path.name for path in drills)
    ):
        fail("separate PTH/NPTH drill files are required")
    if not list((stage / "fabrication/drill").glob("*.svg")):
        fail("drill map SVG is missing")

    bom_refs = read_designators(
        stage / "bom/parts-tally-jlcpcb-bom.csv",
        "Designator",
        quantity_column="Quantity",
    )
    cpl_refs = validate_cpl(stage / "fabrication/parts-tally-jlcpcb-cpl.csv")
    if bom_refs != cpl_refs:
        fail(
            f"BOM/CPL parity mismatch: missing CPL={sorted(bom_refs-cpl_refs)} "
            f"orphan CPL={sorted(cpl_refs-bom_refs)}"
        )
    forbidden = sorted(
        ref for ref in cpl_refs if ref.startswith("TP") or ref.startswith("H")
    )
    if forbidden:
        fail(f"non-assembly designators leaked into CPL: {forbidden}")
    if len(bom_refs) != 31:
        fail(f"expected 31 populated BOM designators, found {len(bom_refs)}")

    checksum_count = validate_checksums(stage)
    print(
        "release archive passed: "
        f"{len(gerbers)} Gerbers, {len(drills)} drill files, "
        f"{len(bom_refs)} BOM/CPL designators, {checksum_count} checksummed files"
    )


def validate_zip_members(archive: zipfile.ZipFile, expected_root: str) -> None:
    members = archive.infolist()
    if not members or len(members) > MAX_ARCHIVE_MEMBERS:
        fail(f"archive member count is invalid: {len(members)}")
    expanded = 0
    seen: set[PurePosixPath] = set()
    for member in members:
        path = archive_relative_path(member.filename)
        if not path.parts or path.parts[0] != expected_root:
            fail(f"archive member is outside {expected_root}: {member.filename!r}")
        if path in seen:
            fail(f"archive contains a duplicate normalized path: {member.filename!r}")
        seen.add(path)
        file_type = (member.external_attr >> 16) & 0o170000
        if file_type == stat.S_IFLNK:
            fail(f"archive links are not allowed: {member.filename}")
        if member.is_dir() or file_type not in {0, stat.S_IFREG}:
            fail(f"archive must contain regular files only: {member.filename}")
        if member.file_size > MAX_ARCHIVE_MEMBER_BYTES:
            fail(f"archive member is too large: {member.filename}")
        expanded += member.file_size
        if expanded > MAX_ARCHIVE_EXPANDED_BYTES:
            fail("archive expanded size exceeds limit")
        ratio = member.file_size / max(member.compress_size, 1)
        if member.file_size > 1024 and ratio > MAX_COMPRESSION_RATIO:
            fail(f"archive compression ratio exceeds limit: {member.filename}")
    for path in seen:
        if any(parent in seen for parent in path.parents):
            fail(f"archive file/directory path collision: {path}")


def extract_validated_members(archive: zipfile.ZipFile, root: Path) -> None:
    expanded = 0
    for member in archive.infolist():
        relative = archive_relative_path(member.filename)
        target = root.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(member) as source, target.open("xb") as destination:
            member_bytes = 0
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                member_bytes += len(chunk)
                expanded += len(chunk)
                if member_bytes > member.file_size or member_bytes > MAX_ARCHIVE_MEMBER_BYTES:
                    fail(f"archive member expanded beyond declared/allowed size: {member.filename}")
                if expanded > MAX_ARCHIVE_EXPANDED_BYTES:
                    fail("archive expanded size exceeds limit during extraction")
                destination.write(chunk)
            if member_bytes != member.file_size:
                fail(f"archive member size does not match metadata: {member.filename}")


def validate_bundle(bundle: Path, manifest: dict) -> None:
    if not bundle.is_file() or not zipfile.is_zipfile(bundle):
        fail(f"bundle is not a readable zip: {bundle}")
    expected_stage_name = f"parts-tally-{manifest['release']}"
    with tempfile.TemporaryDirectory(prefix="parts-tally-release-") as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(bundle) as archive:
            validate_zip_members(archive, expected_stage_name)
            try:
                extract_validated_members(archive, root)
            except zipfile.BadZipFile as exc:
                fail(f"zip CRC/structure failure: {exc}")
        stage = root / expected_stage_name
        if not stage.is_dir():
            fail(f"archive top-level directory must be {expected_stage_name}")
        validate_stage(stage, manifest["release"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path)
    args = parser.parse_args()
    manifest = validate_manifest()
    if args.bundle:
        validate_bundle(args.bundle.resolve(), manifest)
    else:
        print(
            "release manifest passed: "
            f"{manifest['release']} / board {manifest['compatibility']['carrier_board']} / "
            f"firmware {manifest['compatibility']['firmware']} / "
            f"protocol {manifest['compatibility']['protocol']} / "
            f"app {manifest['compatibility']['app']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
