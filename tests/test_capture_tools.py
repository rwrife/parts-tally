from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


capture = load_module("capture_samples", "scripts/capture_samples.py")
analyzer = load_module("analyze_capture", "scripts/analyze_capture.py")
FIXTURE = ROOT / "tests" / "fixtures" / "synthetic_capture.csv"


class CaptureToolTests(unittest.TestCase):
    def test_parse_supported_input_forms(self) -> None:
        self.assertEqual(capture.parse_sample_line("42", 1.25), (1.25, 42, "ok"))
        self.assertEqual(capture.parse_sample_line("0.5,-7", 1.25), (0.5, -7, "ok"))
        self.assertEqual(
            capture.parse_sample_line('{"elapsed_s": 2, "raw_code": 9, "status": "saturated"}', 0),
            (2.0, 9, "saturated"),
        )

    def test_capture_cli_writes_integrity_bound_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "raw.csv"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "capture_samples.py"),
                    str(output),
                    "--condition",
                    "synthetic",
                    "--trial",
                    "trial-1",
                    "--metadata",
                    "fixture=unit-test",
                ],
                input="0.0,100\n0.1,101\n",
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertIn("Captured 2 samples", completed.stdout)
            metadata = json.loads(output.with_suffix(".csv.meta.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["sample_count"], 2)
            self.assertEqual(metadata["user_metadata"]["fixture"], "unit-test")
            self.assertEqual(metadata["capture_sha256"], hashlib.sha256(output.read_bytes()).hexdigest())

    def test_capture_rejects_out_of_range_code(self) -> None:
        with self.assertRaisesRegex(capture.CaptureError, "signed 24-bit"):
            capture.collect_samples(
                iter(["8388608\n"]),
                condition="test",
                trial="t1",
                reference_value="",
                ignore_unparseable=False,
                allow_out_of_range=False,
                limit=None,
            )

    def test_capture_rejects_non_finite_elapsed_time(self) -> None:
        with self.assertRaisesRegex(capture.CaptureError, "finite"):
            capture.parse_sample_line("nan,42", 0)


class AnalyzeToolTests(unittest.TestCase):
    def test_quantile_interpolation(self) -> None:
        self.assertEqual(analyzer.quantile([0, 10], 0.5), 5.0)
        self.assertEqual(analyzer.quantile([0, 10, 20], 0.95), 19.0)

    def test_fixture_metrics_and_repeatability(self) -> None:
        samples = analyzer.load_samples(FIXTURE)
        result = analyzer.analyze(
            samples,
            source=str(FIXTURE),
            evidence_stage="synthetic-software",
            window_samples=10,
            max_band=4.0,
            max_abs_slope=5.0,
        )
        self.assertEqual(result["overall"]["sample_count"], 40)
        self.assertNotIn("linear_drift_code_per_s", result["overall"])
        self.assertEqual(len(result["trials"]), 4)
        self.assertEqual(len(result["repeatability"]), 2)
        self.assertTrue(all(item["stable_window_count"] == 1 for item in result["stability"]))

    def test_missing_thresholds_never_claim_stable(self) -> None:
        samples = analyzer.load_samples(FIXTURE)
        result = analyzer.analyze(
            samples,
            source=str(FIXTURE),
            evidence_stage="synthetic-software",
            window_samples=10,
            max_band=None,
            max_abs_slope=None,
        )
        for trial in result["stability"]:
            self.assertEqual(trial["evaluation"], "not_evaluated_thresholds_missing")
            self.assertTrue(all(window["stable"] is None for window in trial["windows"]))

    def test_non_ok_samples_are_excluded_from_trial_and_repeatability_metrics(self) -> None:
        samples = [
            analyzer.Sample(0.0, 100, "zero", "t1", "0g", "ok"),
            analyzer.Sample(0.1, 999999, "zero", "t1", "0g", "saturated"),
            analyzer.Sample(0.2, 101, "zero", "t1", "0g", "ok"),
            analyzer.Sample(0.0, 102, "zero", "t2", "0g", "ok"),
            analyzer.Sample(0.1, 103, "zero", "t2", "0g", "ok"),
        ]
        result = analyzer.analyze(
            samples,
            source="memory",
            evidence_stage="synthetic-software",
            window_samples=2,
            max_band=None,
            max_abs_slope=None,
        )
        first = next(trial for trial in result["trials"] if trial["trial"] == "t1")
        self.assertEqual(first["excluded_unhealthy_count"], 1)
        self.assertEqual(first["metrics"]["mean_code"], 100.5)
        unhealthy_window = result["stability"][0]["windows"][0]
        self.assertFalse(unhealthy_window["healthy"])
        self.assertFalse(unhealthy_window["stable"])
        self.assertIsNone(unhealthy_window["p95_p5_band_code"])
        self.assertIsNone(unhealthy_window["linear_drift_code_per_s"])
        first_repeatability = next(item for item in result["repeatability"] if item["condition"] == "zero")
        self.assertLess(first_repeatability["trial_mean_range_code"], 10)

    def test_load_rejects_non_finite_and_duplicate_trial_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            header = "elapsed_s,raw_code,condition,trial,reference_value,status\n"
            path.write_text(header + "nan,1,c,t,,ok\n0.1,2,c,t,,ok\n", encoding="utf-8")
            with self.assertRaisesRegex(analyzer.AnalysisError, "finite"):
                analyzer.load_samples(path)
            path.write_text(header + "0.1,1,c,t,,ok\n0.1,2,c,t,,ok\n", encoding="utf-8")
            with self.assertRaisesRegex(analyzer.AnalysisError, "strictly increasing"):
                analyzer.load_samples(path)
            path.write_text(header + "0.2,1,c,t,,ok\n0.1,2,c,t,,ok\n", encoding="utf-8")
            with self.assertRaisesRegex(analyzer.AnalysisError, "capture order"):
                analyzer.load_samples(path)
            path.write_text(header + "0.1,8388608,c,t,,ok\n0.2,2,c,t,,ok\n", encoding="utf-8")
            with self.assertRaisesRegex(analyzer.AnalysisError, "signed 24-bit"):
                analyzer.load_samples(path)

    def test_bench_analysis_requires_integrity_bound_complete_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "raw.csv"
            command = [
                sys.executable,
                str(ROOT / "scripts" / "capture_samples.py"),
                str(output),
                "--condition",
                "wifi-off",
                "--trial",
                "zero-01",
            ]
            metadata = {
                "hardware_revision": "MP-1.0",
                "controller_sku": "113991054",
                "adc_sku": "SEN-15242",
                "load_cell_sku": "SEN-14729",
                "firmware_revision": "abc1234",
                "fixture_revision": "fixture-1",
                "adc_rate_sps": "10",
                "pga": "128",
                "ambient_c": "23.4",
                "instrument": "DMM asset-7",
                "operator": "test-operator",
                "usb_supply": "bench-supply asset-8",
            }
            for key, value in metadata.items():
                command.extend(["--metadata", f"{key}={value}"])
            subprocess.run(
                command,
                input="0.0,100\n0.1,101\n0.2,100\n",
                text=True,
                capture_output=True,
                check=True,
            )
            samples = analyzer.load_samples(output)
            sidecar = output.with_suffix(".csv.meta.json")
            provenance = analyzer.validate_bench_provenance(output, sidecar, len(samples))
            self.assertEqual(provenance["user_metadata"]["controller_sku"], "113991054")

            sidecar_data = json.loads(sidecar.read_text(encoding="utf-8"))
            sidecar_data["user_metadata"]["operator"] = "n/a"
            sidecar.write_text(json.dumps(sidecar_data), encoding="utf-8")
            with self.assertRaisesRegex(analyzer.AnalysisError, "placeholder_or_empty"):
                analyzer.validate_bench_provenance(output, sidecar, len(samples))
            sidecar_data["user_metadata"]["operator"] = "test-operator"
            sidecar_data["ignored_line_count"] = 1
            sidecar.write_text(json.dumps(sidecar_data), encoding="utf-8")
            with self.assertRaisesRegex(analyzer.AnalysisError, "zero ignored"):
                analyzer.validate_bench_provenance(output, sidecar, len(samples))
            sidecar_data["ignored_line_count"] = 0
            sidecar.write_text(json.dumps(sidecar_data), encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "analyze_capture.py"),
                    str(output),
                    "--evidence-stage",
                    "bench",
                    "--window-samples",
                    "2",
                    "--output",
                    str(Path(directory) / "report.json"),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)

            output.write_text(
                output.read_text(encoding="utf-8") + "0.3,102,wifi-off,zero-01,,ok\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(analyzer.AnalysisError, "sample_count|sha256"):
                analyzer.validate_bench_provenance(output, sidecar, 4)

    def test_bench_provenance_rejects_unchecked_raw_format(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            capture_path = Path(directory) / "raw.csv"
            capture_path.write_text(
                "elapsed_s,raw_code,condition,trial,reference_value,status\n"
                "0.0,1,c,t,,ok\n0.1,2,c,t,,ok\n",
                encoding="utf-8",
            )
            sidecar = capture_path.with_suffix(".csv.meta.json")
            sidecar.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "capture_file": capture_path.name,
                        "capture_sha256": hashlib.sha256(capture_path.read_bytes()).hexdigest(),
                        "sample_count": 2,
                        "raw_code_format": "unchecked-integer",
                        "user_metadata": {},
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(analyzer.AnalysisError, "raw_code_format"):
                analyzer.validate_bench_provenance(capture_path, sidecar, 2)

    def test_bench_analysis_without_sidecar_fails_closed(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "analyze_capture.py"),
                str(FIXTURE),
                "--evidence-stage",
                "bench",
                "--window-samples",
                "10",
            ],
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("requires sidecar", completed.stderr)

    def test_cli_rejects_partial_thresholds_and_short_trials(self) -> None:
        partial = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "analyze_capture.py"),
                str(FIXTURE),
                "--max-band",
                "4",
            ],
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(partial.returncode, 0)
        self.assertIn("provide both", partial.stderr)
        short = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "analyze_capture.py"),
                str(FIXTURE),
                "--window-samples",
                "11",
            ],
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(short.returncode, 0)
        self.assertIn("exceeds trial lengths", short.stderr)

    def test_analyzer_cli_writes_machine_readable_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "analyze_capture.py"),
                    str(FIXTURE),
                    "--evidence-stage",
                    "synthetic-software",
                    "--window-samples",
                    "10",
                    "--max-band",
                    "4",
                    "--max-abs-slope",
                    "5",
                    "--output",
                    str(output),
                ],
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertIn("Analyzed 40 samples", completed.stdout)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["evidence_stage"], "synthetic-software")
            self.assertIn("Synthetic data is not bench evidence", report["evidence_scope"])


if __name__ == "__main__":
    unittest.main()
