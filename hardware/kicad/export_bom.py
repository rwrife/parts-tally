#!/usr/bin/env python3
"""Export the production BOM directly from KiCad symbol properties."""

from __future__ import annotations

import argparse
import csv
import io
import os
import re
from collections import defaultdict
from decimal import Decimal
from pathlib import Path


def natural_ref(ref: str) -> tuple[str, int, str]:
    match = re.match(r"([A-Za-z]+)(\d+)(.*)", ref)
    return (match.group(1), int(match.group(2)), match.group(3)) if match else (ref, 0, "")


def prop(component, name: str) -> str:
    value = component.get_property(name)
    if isinstance(value, dict):
        value = value.get("value")
    return "" if value is None else str(value)


def render(schematic_path: Path) -> str:
    os.environ.setdefault("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols")
    from kicad_sch_api import get_symbol_cache, load_schematic

    custom_lib = schematic_path.parent / "lib" / "parts-tally.kicad_sym"
    if custom_lib.exists():
        get_symbol_cache().add_library_path(str(custom_lib))
    schematic = load_schematic(schematic_path)

    fields = [
        "Reference", "Qty", "Value", "Footprint", "Manufacturer", "MPN",
        "Supplier", "Supplier PN", "Estimated Unit Cost USD",
        "Extended Cost USD", "Price Observed UTC", "Stock Observed",
        "Cost Basis", "Datasheet", "BOM Comments",
    ]
    groups: dict[tuple[str, ...], list[object]] = defaultdict(list)
    group_fields = [
        "Value", "Footprint", "Manufacturer", "MPN", "Supplier",
        "Supplier PN", "Estimated Unit Cost USD", "Price Observed UTC",
        "Stock Observed", "Cost Basis", "Datasheet",
    ]

    for component in schematic.components.all():
        if not component.in_bom or component.reference.startswith("#"):
            continue
        key = tuple(prop(component, name) for name in group_fields)
        groups[key].append(component)

    rows: list[dict[str, str]] = []
    for key, components in groups.items():
        components.sort(key=lambda item: natural_ref(item.reference))
        values = dict(zip(group_fields, key))
        qty = len(components)
        unit = Decimal(values["Estimated Unit Cost USD"])
        notes = []
        for component in components:
            note = prop(component, "BOM Comments")
            if note and note not in notes:
                notes.append(note)
        rows.append({
            "Reference": ",".join(item.reference for item in components),
            "Qty": str(qty),
            **values,
            "Extended Cost USD": f"{unit * qty:.4f}",
            "BOM Comments": " | ".join(notes),
        })

    rows.sort(key=lambda row: natural_ref(row["Reference"].split(",", 1)[0]))
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schematic", default="hardware/kicad/parts-tally.kicad_sch")
    parser.add_argument("--output", default="bom/bom.csv")
    parser.add_argument("--check", action="store_true", help="fail if committed CSV is stale")
    args = parser.parse_args()

    schematic = Path(args.schematic)
    output = Path(args.output)
    generated = render(schematic)
    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8") != generated:
            raise SystemExit(f"stale BOM: run {Path(__file__).name} --output {output}")
        print(f"BOM is current: {output}")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(generated, encoding="utf-8", newline="")
    print(f"exported {generated.count(chr(10)) - 1} BOM lines to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
