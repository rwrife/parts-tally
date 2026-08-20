#!/usr/bin/env python3
"""Record line-oriented ADC samples as an evidence-preserving CSV capture.

Input may be one signed integer per line, ``elapsed_s,raw_code``, or JSON lines
containing ``raw_code`` and optionally ``elapsed_s`` and ``status``. The tool
uses only the Python standard library so it can sit behind a serial monitor,
for example:

    pio device monitor --raw | python3 scripts/capture_samples.py out.csv \
      --condition wifi-idle --trial zero-01 --metadata ambient_c=23.4

A capture is raw evidence, not by itself proof of a calibrated or tested scale.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

RAW_MIN = -(1 << 23)
RAW_MAX = (1 << 23) - 1


class CaptureError(ValueError):
    """Raised for malformed or unsafe capture input."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_metadata(items: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise CaptureError(f"metadata must be key=value, got {item!r}")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key or key in parsed:
            raise CaptureError(f"metadata key is empty or duplicated: {key!r}")
        parsed[key] = value.strip()
    return parsed


def parse_sample_line(line: str, fallback_elapsed_s: float) -> tuple[float, int, str]:
    text = line.strip()
    if not text or text.startswith("#"):
        raise CaptureError("empty")

    status = "ok"
    if text.startswith("{"):
        try:
            item = json.loads(text)
        except json.JSONDecodeError as exc:
            raise CaptureError(f"invalid JSON: {exc.msg}") from exc
        if not isinstance(item, dict) or "raw_code" not in item:
            raise CaptureError("JSON sample must be an object containing raw_code")
        elapsed = float(item.get("elapsed_s", fallback_elapsed_s))
        raw = int(item["raw_code"])
        status = str(item.get("status", "ok"))
    elif "," in text:
        fields = [part.strip() for part in text.split(",")]
        if len(fields) != 2:
            raise CaptureError("CSV input line must be elapsed_s,raw_code")
        elapsed = float(fields[0])
        raw = int(fields[1])
    else:
        elapsed = fallback_elapsed_s
        raw = int(text)

    if elapsed < 0:
        raise CaptureError("elapsed_s cannot be negative")
    if not math.isfinite(elapsed):
        raise CaptureError("elapsed_s must be finite")
    if not status:
        raise CaptureError("status cannot be empty")
    return elapsed, raw, status


def collect_samples(
    stream: TextIO,
    *,
    condition: str,
    trial: str,
    reference_value: str,
    ignore_unparseable: bool,
    allow_out_of_range: bool,
    limit: int | None,
) -> tuple[list[dict[str, str]], int]:
    rows: list[dict[str, str]] = []
    ignored = 0
    start = time.monotonic()
    for line_number, line in enumerate(stream, start=1):
        fallback = time.monotonic() - start
        try:
            elapsed, raw, status = parse_sample_line(line, fallback)
        except (CaptureError, ValueError) as exc:
            if str(exc) == "empty":
                continue
            if ignore_unparseable:
                ignored += 1
                continue
            raise CaptureError(f"line {line_number}: {exc}") from exc
        if not allow_out_of_range and not RAW_MIN <= raw <= RAW_MAX:
            raise CaptureError(
                f"line {line_number}: raw_code {raw} is outside signed 24-bit range "
                f"[{RAW_MIN}, {RAW_MAX}]"
            )
        rows.append(
            {
                "utc": utc_now(),
                "elapsed_s": f"{elapsed:.9f}",
                "raw_code": str(raw),
                "condition": condition,
                "trial": trial,
                "reference_value": reference_value,
                "status": status,
            }
        )
        if limit is not None and len(rows) >= limit:
            break
    return rows, ignored


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="raw capture CSV path")
    parser.add_argument("--input", type=Path, help="read lines from a file instead of stdin")
    parser.add_argument("--condition", required=True, help="test condition, e.g. wifi-off")
    parser.add_argument("--trial", required=True, help="unique trial ID, e.g. zero-01")
    parser.add_argument("--reference-value", default="", help="known load/count label; no invented units")
    parser.add_argument("--metadata", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--ignore-unparseable", action="store_true", help="skip serial log lines")
    parser.add_argument("--allow-out-of-range", action="store_true", help="disable signed 24-bit guard")
    parser.add_argument("--limit", type=int, help="stop after this many valid samples")
    parser.add_argument("--force", action="store_true", help="replace existing capture and sidecar")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.limit is not None and args.limit <= 0:
        raise SystemExit("--limit must be positive")
    sidecar = args.output.with_suffix(args.output.suffix + ".meta.json")
    if not args.force and (args.output.exists() or sidecar.exists()):
        raise SystemExit("refusing to overwrite capture; pass --force")

    try:
        user_metadata = parse_metadata(args.metadata)
        if args.input:
            with args.input.open("r", encoding="utf-8") as stream:
                rows, ignored = collect_samples(
                    stream,
                    condition=args.condition,
                    trial=args.trial,
                    reference_value=args.reference_value,
                    ignore_unparseable=args.ignore_unparseable,
                    allow_out_of_range=args.allow_out_of_range,
                    limit=args.limit,
                )
        else:
            rows, ignored = collect_samples(
                sys.stdin,
                condition=args.condition,
                trial=args.trial,
                reference_value=args.reference_value,
                ignore_unparseable=args.ignore_unparseable,
                allow_out_of_range=args.allow_out_of_range,
                limit=args.limit,
            )
    except (OSError, CaptureError) as exc:
        raise SystemExit(f"capture failed: {exc}") from exc

    if not rows:
        raise SystemExit("capture failed: no valid samples")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["utc", "elapsed_s", "raw_code", "condition", "trial", "reference_value", "status"]
    capture_temp: Path | None = None
    sidecar_temp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="", dir=args.output.parent, prefix=f".{args.output.name}.", delete=False
        ) as stream:
            capture_temp = Path(stream.name)
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            stream.flush()
            os.fsync(stream.fileno())

        capture_sha256 = hashlib.sha256(capture_temp.read_bytes()).hexdigest()
        metadata = {
            "schema_version": 1,
            "created_utc": utc_now(),
            "capture_file": args.output.name,
            "capture_sha256": capture_sha256,
            "sample_count": len(rows),
            "ignored_line_count": ignored,
            "condition": args.condition,
            "trial": args.trial,
            "reference_value": args.reference_value,
            "raw_code_format": "signed-24-bit" if not args.allow_out_of_range else "unchecked-integer",
            "evidence_scope": "raw sample capture only; setup, calibration, and bench claims require separate records",
            "user_metadata": user_metadata,
        }
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=sidecar.parent, prefix=f".{sidecar.name}.", delete=False
        ) as stream:
            sidecar_temp = Path(stream.name)
            stream.write(json.dumps(metadata, indent=2, sort_keys=True, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

        # Remove old provenance before replacing a forced capture. If interrupted
        # between replacements, the result is missing metadata rather than a
        # dangerously stale sidecar paired with new samples.
        if sidecar.exists():
            sidecar.unlink()
        os.replace(capture_temp, args.output)
        capture_temp = None
        os.replace(sidecar_temp, sidecar)
        sidecar_temp = None
    finally:
        for temporary in (capture_temp, sidecar_temp):
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    print(f"Captured {len(rows)} samples to {args.output} ({ignored} lines ignored)")
    print(f"Metadata: {sidecar}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
