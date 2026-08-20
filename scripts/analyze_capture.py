#!/usr/bin/env python3
"""Compute transparent noise, drift, stability, and repeatability metrics.

The input is the CSV emitted by ``capture_samples.py``. Stability is never
claimed unless both a maximum P95-P5 band and an absolute slope threshold are
provided from characterized requirements.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


class AnalysisError(ValueError):
    """Raised when capture data cannot support valid calculations."""


BENCH_METADATA_KEYS = {
    "hardware_revision",
    "controller_sku",
    "adc_sku",
    "load_cell_sku",
    "firmware_revision",
    "fixture_revision",
    "adc_rate_sps",
    "pga",
    "ambient_c",
    "instrument",
    "operator",
    "usb_supply",
}
RAW_MIN = -(1 << 23)
RAW_MAX = (1 << 23) - 1
PLACEHOLDER_VALUES = {
    "", "-", "--", "n/a", "na", "none", "not available", "not measured",
    "pending", "todo", "tbd", "unknown", "unset",
}


@dataclass(frozen=True)
class Sample:
    elapsed_s: float
    raw_code: int
    condition: str
    trial: str
    reference_value: str
    status: str


def quantile(values: Iterable[float], probability: float) -> float:
    """Return a linearly interpolated quantile using index (n-1)*p."""
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise AnalysisError("quantile needs at least one value")
    if not 0 <= probability <= 1:
        raise AnalysisError("quantile probability must be in [0, 1]")
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def linear_slope(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        raise AnalysisError("slope needs at least two paired values")
    x_mean = statistics.fmean(xs)
    y_mean = statistics.fmean(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator == 0:
        raise AnalysisError("slope needs distinct timestamps")
    return sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denominator


def load_samples(path: Path) -> list[Sample]:
    last_elapsed_by_trial: dict[tuple[str, str, str], float] = {}
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            required = {"elapsed_s", "raw_code", "condition", "trial"}
            if reader.fieldnames is None or not required <= set(reader.fieldnames):
                raise AnalysisError(f"CSV requires columns {sorted(required)}")
            samples = []
            for row_number, row in enumerate(reader, start=2):
                try:
                    sample = Sample(
                        elapsed_s=float(row["elapsed_s"]),
                        raw_code=int(row["raw_code"]),
                        condition=(row.get("condition") or "").strip(),
                        trial=(row.get("trial") or "").strip(),
                        reference_value=(row.get("reference_value") or "").strip(),
                        status=(row.get("status") or "ok").strip(),
                    )
                except (TypeError, ValueError) as exc:
                    raise AnalysisError(f"row {row_number}: invalid numeric value") from exc
                if sample.elapsed_s < 0 or not sample.condition or not sample.trial:
                    raise AnalysisError(f"row {row_number}: elapsed_s must be nonnegative and labels nonempty")
                if not math.isfinite(sample.elapsed_s):
                    raise AnalysisError(f"row {row_number}: elapsed_s must be finite")
                if not RAW_MIN <= sample.raw_code <= RAW_MAX:
                    raise AnalysisError(
                        f"row {row_number}: raw_code {sample.raw_code} is outside signed 24-bit range"
                    )
                key = (sample.condition, sample.trial, sample.reference_value)
                previous = last_elapsed_by_trial.get(key)
                if previous is not None and sample.elapsed_s <= previous:
                    raise AnalysisError(
                        f"row {row_number}: trial {key!r} timestamps must be strictly increasing in capture order"
                    )
                last_elapsed_by_trial[key] = sample.elapsed_s
                samples.append(sample)
    except OSError as exc:
        raise AnalysisError(f"cannot read {path}: {exc}") from exc
    if len(samples) < 2:
        raise AnalysisError("capture needs at least two samples")
    return samples


def validate_bench_provenance(capture: Path, sidecar: Path, sample_count: int) -> dict[str, object]:
    try:
        metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    except OSError as exc:
        raise AnalysisError(f"bench evidence requires sidecar {sidecar}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise AnalysisError(f"invalid bench sidecar JSON: {exc}") from exc
    if not isinstance(metadata, dict) or metadata.get("schema_version") != 1:
        raise AnalysisError("bench sidecar must be a schema_version 1 object")
    if metadata.get("capture_file") != capture.name:
        raise AnalysisError("bench sidecar capture_file does not match input filename")
    if metadata.get("sample_count") != sample_count:
        raise AnalysisError("bench sidecar sample_count does not match capture")
    if metadata.get("raw_code_format") != "signed-24-bit":
        raise AnalysisError("bench sidecar raw_code_format must be signed-24-bit")
    if metadata.get("ignored_line_count") != 0:
        raise AnalysisError("bench sidecar must report zero ignored input lines")
    digest = hashlib.sha256(capture.read_bytes()).hexdigest()
    if metadata.get("capture_sha256") != digest:
        raise AnalysisError("bench sidecar capture_sha256 does not match capture")
    user_metadata = metadata.get("user_metadata")
    if not isinstance(user_metadata, dict):
        raise AnalysisError("bench sidecar user_metadata must be an object")
    missing = sorted(BENCH_METADATA_KEYS - set(user_metadata))
    placeholders = []
    for key in sorted(BENCH_METADATA_KEYS & set(user_metadata)):
        value = str(user_metadata[key]).strip().lower()
        if (
            value in PLACEHOLDER_VALUES
            or value.startswith("<") and value.endswith(">")
            or "to be determined" in value
        ):
            placeholders.append(key)
    if missing or placeholders:
        raise AnalysisError(
            f"bench provenance incomplete: missing={missing}, placeholder_or_empty={placeholders}"
        )
    return metadata


def metric_summary(samples: list[Sample]) -> dict[str, float | int | None]:
    if len(samples) < 2:
        raise AnalysisError("metrics need at least two samples")
    ordered = sorted(samples, key=lambda sample: sample.elapsed_s)
    xs = [sample.elapsed_s for sample in ordered]
    ys = [float(sample.raw_code) for sample in ordered]
    p5 = quantile(ys, 0.05)
    p95 = quantile(ys, 0.95)
    q1 = quantile(ys, 0.25)
    q3 = quantile(ys, 0.75)
    iqr = q3 - q1
    low_fence = q1 - 1.5 * iqr
    high_fence = q3 + 1.5 * iqr
    duration = xs[-1] - xs[0]
    return {
        "sample_count": len(ordered),
        "duration_s": duration,
        "sample_rate_hz": (len(ordered) - 1) / duration if duration > 0 else None,
        "mean_code": statistics.fmean(ys),
        "median_code": statistics.median(ys),
        "sample_stddev_code": statistics.stdev(ys) if len(ys) > 1 else 0.0,
        "p5_code": p5,
        "p95_code": p95,
        "p95_p5_band_code": p95 - p5,
        "peak_to_peak_code": max(ys) - min(ys),
        "start_code": ys[0],
        "end_code": ys[-1],
        "delta_code": ys[-1] - ys[0],
        "linear_drift_code_per_s": linear_slope(xs, ys),
        "outlier_count_iqr": sum(value < low_fence or value > high_fence for value in ys),
        "outlier_rate_iqr": sum(value < low_fence or value > high_fence for value in ys) / len(ys),
    }


def group_samples(samples: list[Sample]) -> dict[tuple[str, str, str], list[Sample]]:
    grouped: dict[tuple[str, str, str], list[Sample]] = defaultdict(list)
    for sample in samples:
        grouped[(sample.condition, sample.trial, sample.reference_value)].append(sample)
    return dict(grouped)


def repeatability_summary(samples: list[Sample]) -> list[dict[str, object]]:
    trials = group_samples(samples)
    by_reference: dict[tuple[str, str], list[tuple[str, float]]] = defaultdict(list)
    for (condition, trial, reference), trial_samples in trials.items():
        healthy = [sample for sample in trial_samples if sample.status == "ok"]
        if not healthy:
            continue
        by_reference[(condition, reference)].append(
            (trial, statistics.fmean(sample.raw_code for sample in healthy))
        )

    results: list[dict[str, object]] = []
    for (condition, reference), trial_means in sorted(by_reference.items()):
        if len(trial_means) < 2:
            continue
        means = [mean for _, mean in trial_means]
        results.append(
            {
                "condition": condition,
                "reference_value": reference,
                "trial_count": len(means),
                "trial_means_code": [
                    {"trial": trial, "mean_code": mean} for trial, mean in sorted(trial_means)
                ],
                "mean_of_trial_means_code": statistics.fmean(means),
                "trial_mean_range_code": max(means) - min(means),
                "trial_mean_sample_stddev_code": statistics.stdev(means),
            }
        )
    return results


def stability_summary(
    grouped: dict[tuple[str, str, str], list[Sample]],
    *,
    window_samples: int,
    max_band: float | None,
    max_abs_slope: float | None,
) -> list[dict[str, object]]:
    evaluated = max_band is not None and max_abs_slope is not None
    results: list[dict[str, object]] = []
    for key, samples in sorted(grouped.items()):
        ordered = sorted(samples, key=lambda sample: sample.elapsed_s)
        windows = []
        for start in range(0, len(ordered) - window_samples + 1):
            window = ordered[start : start + window_samples]
            healthy = all(sample.status == "ok" for sample in window)
            metrics = metric_summary(window) if healthy else None
            stable = None if healthy else False
            if evaluated and healthy:
                assert max_band is not None and max_abs_slope is not None
                assert metrics is not None
                band_value = metrics["p95_p5_band_code"]
                slope_value = metrics["linear_drift_code_per_s"]
                assert isinstance(band_value, (int, float))
                assert isinstance(slope_value, (int, float))
                band = float(band_value)
                slope = float(slope_value)
                stable = band <= max_band and abs(slope) <= max_abs_slope
            windows.append(
                {
                    "start_index": start,
                    "end_index": start + window_samples - 1,
                    "p95_p5_band_code": metrics["p95_p5_band_code"] if metrics else None,
                    "linear_drift_code_per_s": metrics["linear_drift_code_per_s"] if metrics else None,
                    "healthy": healthy,
                    "stable": stable,
                }
            )
        results.append(
            {
                "condition": key[0],
                "trial": key[1],
                "reference_value": key[2],
                "evaluation": "evaluated" if evaluated else "not_evaluated_thresholds_missing",
                "window_samples": window_samples,
                "window_count": len(windows),
                "stable_window_count": sum(item["stable"] is True for item in windows),
                "windows": windows,
            }
        )
    return results


def analyze(
    samples: list[Sample],
    *,
    source: str,
    evidence_stage: str,
    window_samples: int,
    max_band: float | None,
    max_abs_slope: float | None,
) -> dict[str, object]:
    grouped = group_samples(samples)
    statuses: dict[str, int] = defaultdict(int)
    for sample in samples:
        statuses[sample.status] += 1
    return {
        "schema_version": 1,
        "source": source,
        "evidence_stage": evidence_stage,
        "evidence_scope": (
            "Computed metrics only. Synthetic data is not bench evidence; bench-labeled data still "
            "requires setup, instruments, environment, revisions, and raw-file provenance."
        ),
        "methods": {
            "quantiles": "linear interpolation at index (n-1)*p",
            "noise_band": "P95-P5 of raw code",
            "drift": "ordinary least-squares slope versus elapsed seconds",
            "outliers": "outside Tukey 1.5*IQR fences",
            "repeatability": "range/stddev of per-trial raw-code means grouped by condition/reference",
        },
        "thresholds": {
            "max_p95_p5_band_code": max_band,
            "max_abs_slope_code_per_s": max_abs_slope,
            "window_samples": window_samples,
            "note": "null thresholds intentionally prevent an unsupported stability pass claim",
        },
        "status_counts": dict(sorted(statuses.items())),
        "overall": {
            "sample_count": len(samples),
            "healthy_sample_count": sum(sample.status == "ok" for sample in samples),
            "trial_count": len(grouped),
            "condition_count": len({sample.condition for sample in samples}),
            "note": "Temporal metrics are per trial because elapsed_s restarts independently.",
        },
        "trials": [
            {
                "condition": condition,
                "trial": trial,
                "reference_value": reference,
                "status_counts": {
                    status: sum(sample.status == status for sample in trial_samples)
                    for status in sorted({sample.status for sample in trial_samples})
                },
                "excluded_unhealthy_count": sum(sample.status != "ok" for sample in trial_samples),
                "metrics": metric_summary(
                    [sample for sample in trial_samples if sample.status == "ok"]
                )
                if sum(sample.status == "ok" for sample in trial_samples) >= 2
                else None,
            }
            for (condition, trial, reference), trial_samples in sorted(grouped.items())
        ],
        "repeatability": repeatability_summary(samples),
        "stability": stability_summary(
            grouped,
            window_samples=window_samples,
            max_band=max_band,
            max_abs_slope=max_abs_slope,
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--output", type=Path, help="write JSON here; stdout is always summarized")
    parser.add_argument("--metadata", type=Path, help="capture sidecar; required/auto-derived for bench")
    parser.add_argument(
        "--evidence-stage",
        choices=("unspecified", "synthetic-software", "bench"),
        default="unspecified",
    )
    parser.add_argument("--window-samples", type=int, default=20)
    parser.add_argument("--max-band", type=float, help="characterized max P95-P5 raw-code band")
    parser.add_argument("--max-abs-slope", type=float, help="characterized max absolute code/s slope")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.window_samples < 2:
        raise SystemExit("--window-samples must be at least 2")
    if (args.max_band is None) != (args.max_abs_slope is None):
        raise SystemExit("provide both --max-band and --max-abs-slope, or neither")
    if args.max_band is not None and (args.max_band < 0 or args.max_abs_slope < 0):
        raise SystemExit("stability thresholds cannot be negative")
    if args.max_band is not None and not all(math.isfinite(value) for value in (args.max_band, args.max_abs_slope)):
        raise SystemExit("stability thresholds must be finite")
    try:
        samples = load_samples(args.capture)
        grouped = group_samples(samples)
        short_trials = [key for key, group in grouped.items() if len(group) < args.window_samples]
        if short_trials:
            raise AnalysisError(f"--window-samples exceeds trial lengths: {short_trials}")
        provenance = None
        if args.evidence_stage == "bench":
            sidecar = args.metadata or args.capture.with_suffix(args.capture.suffix + ".meta.json")
            provenance = validate_bench_provenance(args.capture, sidecar, len(samples))
        result = analyze(
            samples,
            source=str(args.capture),
            evidence_stage=args.evidence_stage,
            window_samples=args.window_samples,
            max_band=args.max_band,
            max_abs_slope=args.max_abs_slope,
        )
        if provenance is not None:
            result["bench_provenance"] = provenance
    except AnalysisError as exc:
        raise SystemExit(f"analysis failed: {exc}") from exc

    rendered = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        overall = result["overall"]
        assert isinstance(overall, dict)
        print(f"Analyzed {overall['sample_count']} samples -> {args.output}")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
