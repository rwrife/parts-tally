import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validate_release", ROOT / "scripts/validate_release.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load scripts/validate_release.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
BUILD_SPEC = importlib.util.spec_from_file_location("build_release", ROOT / "scripts/build_release.py")
if BUILD_SPEC is None or BUILD_SPEC.loader is None:
    raise RuntimeError("could not load scripts/build_release.py")
BUILD = importlib.util.module_from_spec(BUILD_SPEC)
BUILD_SPEC.loader.exec_module(BUILD)


class ReleaseContractTests(unittest.TestCase):
    def test_manifest_and_source_contract(self):
        manifest = MODULE.validate_manifest()
        self.assertEqual(manifest["release"], "v0.1.0-rc.1")
        self.assertEqual(manifest["compatibility"]["firmware"], "0.2.0")
        self.assertEqual(manifest["compatibility"]["protocol"], "parts-tally/v1")
        self.assertEqual(manifest["compatibility"]["app"], "0.1.0")
        self.assertEqual(manifest["evidence"]["bench"], "not-performed-no-physical-prototype")
        self.assertFalse(manifest["safety_scope"]["legal_for_trade"])

    def test_firmware_version_source_matches_manifest(self):
        manifest = json.loads((ROOT / "release/manifest.json").read_text())
        version_header = (ROOT / "firmware/include/parts_tally/version.hpp").read_text()
        self.assertIn(f'kFirmwareVersion = "{manifest["compatibility"]["firmware"]}"', version_header)
        self.assertIn(f'kProtocolVersion = "{manifest["compatibility"]["protocol"]}"', version_header)
        self.assertIn(f'kCarrierBoardRevision = "{manifest["compatibility"]["carrier_board"]}"', version_header)

    def test_app_version_matches_manifest(self):
        manifest = json.loads((ROOT / "release/manifest.json").read_text())
        package = json.loads((ROOT / "app/package.json").read_text())
        self.assertEqual(package["version"], manifest["compatibility"]["app"])

    def test_schematic_bom_has_expected_designators(self):
        import csv

        with (ROOT / "bom/bom.csv").open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        refs = set().union(*(MODULE.split_refs(row["Reference"]) for row in rows))
        self.assertEqual(len(refs), 31)
        self.assertTrue({"J1", "J2", "J3", "U1", "U2", "D3"}.issubset(refs))

    def test_bom_reader_rejects_duplicate_and_quantity_mismatched_designators(self):
        cases = (
            'Designator,Quantity\n"R1,R1",2\n',
            'Designator,Quantity\n"R1,R2",1\n',
            "Designator,Quantity\nR1,1\nR1,1\n",
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bom.csv"
            for content in cases:
                with self.subTest(content=content):
                    path.write_text(content, encoding="utf-8")
                    with self.assertRaises(SystemExit):
                        MODULE.read_designators(
                            path, "Designator", quantity_column="Quantity"
                        )

    def test_placement_normalizer_rejects_unknown_nonfinite_and_duplicate_rows(self):
        cases = (
            "Ref,PosX,PosY,Side,Rot\n,1,2,front,0\n",
            "Ref,PosX,PosY,Side,Rot\nR1,1,2,sideways,0\n",
            "Ref,PosX,PosY,Side,Rot\nR1,nan,2,front,0\n",
            "Ref,PosX,PosY,Side,Rot\nR1,1,2,front,0\nR1,2,3,front,0\n",
        )
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "position.csv"
            output = Path(temporary) / "cpl.csv"
            for content in cases:
                with self.subTest(content=content):
                    source.write_text(content, encoding="utf-8")
                    with self.assertRaises(SystemExit):
                        BUILD.normalize_placement(source, output)

    def test_zip_validation_rejects_traversal_and_extra_roots(self):
        root = "parts-tally-v0.1.0-rc.1"
        cases = ("../escape", f"{root}/../escape", "unexpected/file.txt")
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary) / "bad.zip"
            for member in cases:
                with self.subTest(member=member):
                    with zipfile.ZipFile(bundle, "w") as archive:
                        archive.writestr(member, "bad")
                    with zipfile.ZipFile(bundle) as archive:
                        with self.assertRaises(SystemExit):
                            MODULE.validate_zip_members(archive, root)

    def test_zip_validation_rejects_normalized_path_collisions(self):
        root = "parts-tally-v0.1.0-rc.1"
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary) / "collision.zip"
            with zipfile.ZipFile(bundle, "w") as archive:
                archive.writestr(f"{root}/sources//file.txt", "first")
                archive.writestr(f"{root}/sources/file.txt", "second")
            with zipfile.ZipFile(bundle) as archive:
                with self.assertRaises(SystemExit):
                    MODULE.validate_zip_members(archive, root)

    def test_copy_sources_is_buildable_and_uses_supplied_stls(self):
        base = ROOT / "hardware/mechanical/generated/parts-tally-base.stl"
        platform = ROOT / "hardware/mechanical/generated/parts-tally-platform.stl"
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary) / "stage"
            BUILD.copy_sources(stage, base, platform)
            required = (
                "sources/app/scripts/generate-contract.mjs",
                "sources/app/e2e/app.spec.ts",
                "sources/app/eslint.config.js",
                "sources/app/playwright.config.ts",
                "sources/firmware/test/test_domain/test_main.cpp",
                "sources/docs/schemas/api-v1/status.schema.json",
                "sources/tests/fixtures/protocol/v1/status-stable.json",
                "sources/scripts/validate_release.py",
                "sources/release/requirements.lock",
                "sources/hardware/kicad/parts-tally.kicad_pro",
                "sources/bom/bom.csv",
                "sources/docs/architecture-contract.json",
            )
            for relative in required:
                self.assertTrue((stage / relative).is_file(), relative)
            self.assertEqual(
                (stage / "sources/hardware/mechanical/generated/parts-tally-base.stl").read_bytes(),
                base.read_bytes(),
            )
            self.assertEqual(
                (stage / "sources/hardware/mechanical/generated/parts-tally-platform.stl").read_bytes(),
                platform.read_bytes(),
            )
            for script in ("scripts/validate_contract.py", "scripts/validate_release.py"):
                completed = subprocess.run(
                    [sys.executable, script],
                    cwd=stage / "sources",
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(
                    completed.returncode,
                    0,
                    f"{script}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
                )

    def test_protocol_schemas_promised_by_release_exist(self):
        self.assertTrue((ROOT / "docs/schemas/api-v1/status.schema.json").is_file())


if __name__ == "__main__":
    unittest.main()
