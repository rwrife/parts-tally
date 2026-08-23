#!/usr/bin/env python3
"""Deterministic, dependency-free reviewability checks for firmware C++."""

from __future__ import annotations

import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE_SUFFIXES = {".cpp", ".hpp", ".h"}
DENSE_PATTERNS = (
    re.compile(r"\}\s*(?:else|catch)\s*\{.*\}"),
    re.compile(r";\s*(?:if|for|while|switch)\s*\("),
    re.compile(r"\{[^{}\n]{120,}\}"),
)


def validate(path: pathlib.Path) -> list[str]:
    errors: list[str] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        location = f"{path.relative_to(ROOT)}:{number}"
        if "\t" in line:
            errors.append(f"{location}: tab character")
        if line.rstrip() != line:
            errors.append(f"{location}: trailing whitespace")
        if len(line) > 100 and not line.lstrip().startswith("//"):
            errors.append(f"{location}: line is {len(line)} columns (maximum 100)")
        if any(pattern.search(line) for pattern in DENSE_PATTERNS):
            errors.append(f"{location}: dense multi-statement line")
    return errors


def main() -> int:
    firmware = ROOT / "firmware"
    paths = sorted(
        path
        for path in firmware.rglob("*")
        if path.suffix in SOURCE_SUFFIXES and ".pio" not in path.parts
    )
    errors = [error for path in paths for error in validate(path)]
    if errors:
        print("\n".join(errors))
        return 1
    print(f"firmware format validation passed ({len(paths)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
