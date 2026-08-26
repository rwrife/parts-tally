#!/usr/bin/env python3
"""Static acceptance checks for the issue #3 editable KiCad schematic."""

from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMATIC = ROOT / "hardware" / "kicad" / "parts-tally.kicad_sch"
PROJECT = ROOT / "hardware" / "kicad" / "parts-tally.kicad_pro"
CUSTOM_LIBRARY = ROOT / "hardware" / "kicad" / "lib" / "parts-tally.kicad_sym"
XIAO_FOOTPRINT = ROOT / "hardware" / "kicad" / "lib" / "parts-tally.pretty" / "XIAO_ESP32C3.kicad_mod"
EXTRACTION = ROOT / "hardware" / "datasheets" / "extracted" / "NAU7802SGI.json"
BOM = ROOT / "bom" / "bom.csv"


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def prop(component, name: str) -> str:
    value = component.get_property(name)
    if isinstance(value, dict):
        value = value.get("value")
    return "" if value is None else str(value)


def rounded_point(x: float, y: float) -> tuple[float, float]:
    return (round(float(x), 2), round(float(y), 2))


def pin_point(component, symbol_definition, pin_number: str) -> tuple[float, float]:
    if component.rotation != 0:
        fail(f"{component.reference} is rotated; validator transform needs extension")
    pin = symbol_definition.get_pin(pin_number)
    if pin is None:
        fail(f"{component.reference} has no pin {pin_number}")
    return rounded_point(component.position.x + pin.position.x, component.position.y - pin.position.y)


def main() -> int:
    os.environ.setdefault("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols")
    from kicad_sch_api import get_symbol_cache, load_schematic

    if not SCHEMATIC.exists():
        fail(f"missing schematic: {SCHEMATIC}")
    project = json.loads(PROJECT.read_text(encoding="utf-8"))
    erc_severities = project.get("erc", {}).get("rule_severities", {})
    expected_waivers = {
        "footprint_link_issues": "ignore",
        "lib_symbol_mismatch": "ignore",
    }
    if erc_severities != expected_waivers:
        fail(
            "project must retain the two documented headless ERC waivers; "
            f"found {erc_severities!r}"
        )
    cache = get_symbol_cache()
    symbol_dir = Path(os.environ["KICAD_SYMBOL_DIR"])
    if symbol_dir.is_dir():
        cache.discover_libraries([str(symbol_dir)])
    cache.add_library_path(str(CUSTOM_LIBRARY))
    schematic = load_schematic(SCHEMATIC)
    components = {component.reference: component for component in schematic.components.all()}
    symbol_defs = {
        reference: cache.get_symbol(component.lib_id)
        for reference, component in components.items()
    }
    if missing_defs := [ref for ref, definition in symbol_defs.items() if definition is None]:
        fail(f"could not resolve symbol definitions for {missing_defs}")

    required_refs = {"J1", "J2", "J3", "U1", "U2", "F1", "D1", "D2", "D3", "SW1"}
    if missing := required_refs - components.keys():
        fail(f"missing required symbols: {sorted(missing)}")

    required_properties = [
        "Manufacturer", "MPN", "Supplier", "Datasheet",
        "Estimated Unit Cost USD", "Price Observed UTC", "BOM Comments",
    ]
    bom_components = [
        component for component in components.values()
        if component.in_bom and not component.reference.startswith("#")
    ]
    if len(bom_components) != 31:
        fail(f"expected 31 populated schematic components, found {len(bom_components)}")
    for component in bom_components:
        if not component.footprint:
            fail(f"{component.reference} has no footprint")
        for field in required_properties:
            if not prop(component, field).strip():
                fail(f"{component.reference} missing {field}")

    expected_u2_pins = {
        "1": "REFP", "2": "VIN1N", "3": "VIN1P", "4": "VIN2N",
        "5": "VIN2P", "6": "VBG", "7": "REFN", "8": "AVSS",
        "9": "DVSS", "10": "XIN", "11": "XOUT", "12": "DRDY",
        "13": "SCLK", "14": "SDIO", "15": "DVDD", "16": "AVDD/LDO",
    }
    for number, expected_name in expected_u2_pins.items():
        actual = symbol_defs["U2"].get_pin(number)
        if actual is None or actual.name != expected_name:
            fail(f"U2 pin {number}: expected {expected_name}, got {getattr(actual, 'name', None)}")

    expected_u1_pins = {
        "1": "D0", "2": "D1", "3": "D2", "4": "D3", "5": "D4",
        "6": "D5", "7": "D6", "8": "D7", "9": "D8", "10": "D9",
        "11": "D10", "12": "VCC_3V3", "13": "GND", "14": "VUSB",
        "B+": "Batt+", "B-": "Batt-",
    }
    for number, expected_name in expected_u1_pins.items():
        actual = symbol_defs["U1"].get_pin(number)
        if actual is None or actual.name != expected_name:
            fail(f"U1 pin {number}: expected {expected_name}, got {getattr(actual, 'name', None)}")

    expected_d3_pins = {
        "1": "KB", "2": "KG", "3": "KR", "4": "AR", "5": "AG", "6": "AB",
    }
    for number, expected_name in expected_d3_pins.items():
        actual = symbol_defs["D3"].get_pin(number)
        if actual is None or actual.name != expected_name:
            fail(f"D3 pin {number}: expected {expected_name}, got {getattr(actual, 'name', None)}")
    if prop(components["D3"], "MPN") != "ASMT-YTC7-0AA02":
        fail("D3 must use the current ASMT-YTC7-0AA02 replacement")

    footprint_text = XIAO_FOOTPRINT.read_text(encoding="utf-8")
    footprint_pads = set(re.findall(r'\(pad\s+"([^"]+)"', footprint_text))
    expected_xiao_pads = {str(number) for number in range(1, 15)} | {"B+", "B-"}
    if footprint_pads != expected_xiao_pads:
        fail(f"XIAO footprint pads differ from header/battery map: {sorted(footprint_pads)}")

    footprint_dir = Path(os.environ.get("KICAD_FOOTPRINT_DIR", "/usr/share/kicad/footprints"))

    def resolve_footprint(footprint: str) -> Path:
        library, name = footprint.split(":", 1)
        if library == "parts-tally":
            return ROOT / "hardware" / "kicad" / "lib" / "parts-tally.pretty" / f"{name}.kicad_mod"
        return footprint_dir / f"{library}.pretty" / f"{name}.kicad_mod"

    for component in bom_components:
        footprint_path = resolve_footprint(component.footprint)
        if not footprint_path.exists():
            fail(f"{component.reference} footprint does not resolve: {component.footprint}")

    expected_critical_pad_sets = {
        "J1": {"A1", "A4", "A5", "A6", "A7", "A8", "A9", "A12", "B1", "B4", "B5", "B6", "B7", "B8", "B9", "B12", "S1"},
        "J2": {"1", "2", "3", "4", "MP"},
        "J3": {"1", "2", "3", "4"},
        "U1": expected_xiao_pads,
        "U2": {str(number) for number in range(1, 17)},
        "D3": {str(number) for number in range(1, 7)},
    }
    for reference, expected_pads in expected_critical_pad_sets.items():
        footprint_path = resolve_footprint(components[reference].footprint)
        actual_pads = set(re.findall(r'\(pad\s+"([^"]+)"', footprint_path.read_text(encoding="utf-8")))
        if actual_pads != expected_pads:
            fail(f"{reference} footprint pad set mismatch: {sorted(actual_pads)}")

    text = SCHEMATIC.read_text(encoding="utf-8")
    label_pattern = re.compile(r'\(label\s+"([^"]+)"\s*\n\s*\(at\s+([-0-9.]+)\s+([-0-9.]+)')
    labels_at: dict[tuple[float, float], set[str]] = defaultdict(set)
    for net, x, y in label_pattern.findall(text):
        labels_at[rounded_point(float(x), float(y))].add(net)
    if len(labels_at) < 35:
        fail(f"expected at least 35 labeled connection points, found {len(labels_at)}")
    for point, names in labels_at.items():
        if len(names) > 1:
            fail(f"conflicting labels at {point}: {sorted(names)}")

    expected_connections = {
        ("J1", "A5"): "CC1", ("J1", "B5"): "CC2", ("J1", "A4"): "VBUS",
        ("U1", "14"): "+5V_XIAO", ("U1", "12"): "+3V3", ("U1", "13"): "GND",
        ("U1", "5"): "I2C_SDA", ("U1", "6"): "I2C_SCL",
        ("U1", "2"): "BUTTON_N", ("U1", "7"): "UART_TX", ("U1", "8"): "UART_RX",
        ("U2", "1"): "AVDD_3V0", ("U2", "2"): "AIN-", ("U2", "3"): "AIN+",
        ("U2", "5"): "PGA_CFILTER", ("U2", "6"): "VBG", ("U2", "7"): "GND",
        ("U2", "13"): "I2C_SCL", ("U2", "14"): "I2C_SDA",
        ("U2", "15"): "+3V3", ("U2", "16"): "AVDD_3V0",
        ("J2", "1"): "AVDD_3V0", ("J2", "2"): "GND",
        ("J2", "3"): "LC_S+", ("J2", "4"): "LC_S-",
        ("J3", "1"): "+3V3", ("J3", "2"): "GND",
        ("J3", "3"): "UART_TX", ("J3", "4"): "UART_RX",
        ("D3", "1"): "LED_B_K", ("D3", "2"): "LED_G_K", ("D3", "3"): "LED_R_K",
        ("D3", "4"): "+3V3", ("D3", "5"): "+3V3", ("D3", "6"): "+3V3",
        ("R8", "1"): "LED_R_GPIO", ("R8", "2"): "LED_R_K",
        ("R9", "1"): "LED_G_GPIO", ("R9", "2"): "LED_G_K",
        ("R10", "1"): "LED_B_GPIO", ("R10", "2"): "LED_B_K",
    }
    for (reference, pin), expected_net in expected_connections.items():
        point = pin_point(components[reference], symbol_defs[reference], pin)
        if expected_net not in labels_at.get(point, set()):
            fail(f"{reference}.{pin} at {point}: expected label {expected_net}, got {labels_at.get(point)}")

    nc_pattern = re.compile(r'\(no_connect\s*\n\s*\(at\s+([-0-9.]+)\s+([-0-9.]+)')
    nc_points = {rounded_point(float(x), float(y)) for x, y in nc_pattern.findall(text)}
    expected_nc = {
        ("J1", "A6"), ("J1", "A7"), ("J1", "A8"),
        ("J1", "B6"), ("J1", "B7"), ("J1", "B8"),
        ("U1", "1"), ("U1", "9"), ("U1", "10"), ("U1", "B+"), ("U1", "B-"),
        ("U2", "4"), ("U2", "10"), ("U2", "11"), ("U2", "12"),
    }
    for reference, pin in expected_nc:
        point = pin_point(components[reference], symbol_defs[reference], pin)
        if point not in nc_points:
            fail(f"{reference}.{pin} at {point} lacks an intentional no-connect marker")

    extraction = json.loads(EXTRACTION.read_text(encoding="utf-8"))
    if extraction["source"]["mpn"] != "NAU7802SGI":
        fail("NAU7802 extraction MPN mismatch")
    extracted_pins = {
        number: pin["name"]
        for pin in extraction["base"]["pinout"]
        for number in pin["numbers"]
    }
    if extracted_pins != expected_u2_pins:
        fail("NAU7802 cached datasheet pinout differs from the checked symbol map")
    if extraction["extraction"]["quality_score"] < 90:
        fail("NAU7802 extraction quality score is below 90")

    if not BOM.exists() or BOM.stat().st_size < 1000:
        fail("bom/bom.csv is missing or unexpectedly small")
    if "Estimated Unit Cost USD" not in BOM.read_text(encoding="utf-8").splitlines()[0]:
        fail("BOM lacks cost provenance columns")

    print(
        "hardware validation passed: "
        f"{len(components)} symbols, {len(bom_components)} BOM components, "
        f"{len(labels_at)} labeled points, {len(nc_points)} intentional NC points, "
        f"{len(extracted_pins)} datasheet-checked NAU7802 pins, "
        f"{len(expected_d3_pins)} datasheet-checked RGB LED pins, "
        f"{len(footprint_pads)} checked XIAO footprint pads, "
        f"{len({component.footprint for component in bom_components})} resolved populated footprints"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
