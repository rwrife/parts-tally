#!/usr/bin/env python3
"""Validate the Parts Tally architecture/requirements contract using stdlib only."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs" / "architecture-contract.json"
ID_RE = re.compile(r"\|\s*([A-Z]+-\d{2})\s*\|")
TEST_ID_RE = re.compile(r"\|\s*([A-Z]+(?:-[A-Z]+)*-\d{2})\s*\|")
RISK_ID_RE = re.compile(r"\|\s*(RISK-[A-Z]+-\d{2})\s*\|")

REQUIRED_VERIFICATION_TESTS = {
    "DOC-01", "NOISE-01", "REP-01", "HYS-01", "WARM-01", "CREEP-01",
    "OFFCENTER-01", "CABLE-01", "DISC-01", "SAT-01", "OVR-01", "WIFI-01",
    "COUNT-01",
}
REQUIRED_NO_COUNT_STATES = {
    "uncalibrated", "unstable", "stale", "disconnected", "saturated",
    "overload_indicated", "below_tare", "calibration_invalid",
    "uncertainty_excessive",
}
EXPECTED_EVIDENCE_STATUS = {
    "documentation_static": "implemented",
    "datasheet_selection": "pending",
    "simulation": "not-performed",
    "software": "not-implemented",
    "schematic_layout": "not-implemented",
    "bench": "not-performed",
    "field": "not-performed",
}


class ContractError(RuntimeError):
    pass


def load_contract() -> dict:
    try:
        data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot load {CONTRACT_PATH.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(data, dict):
        raise ContractError("architecture contract must be a JSON object")
    return data


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def read_relative(relative: str) -> str:
    path = ROOT / relative
    require(path.is_file(), f"missing document: {relative}")
    return path.read_text(encoding="utf-8")


def table_ids(text: str, pattern: re.Pattern[str]) -> list[str]:
    return pattern.findall(text)


def validate_contract(data: dict) -> list[str]:
    checks: list[str] = []

    require(data.get("schema_version") == 1, "schema_version must equal 1")
    require(re.fullmatch(r"\d+\.\d+", str(data.get("architecture_version", ""))) is not None,
            "architecture_version must be MAJOR.MINOR")
    require(re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(data.get("baseline_date", ""))) is not None,
            "baseline_date must be YYYY-MM-DD")
    require(data.get("status") == "design-contract", "status must remain design-contract before implementation")
    checks.append("contract metadata")

    safety = data.get("safety_scope")
    require(isinstance(safety, dict), "safety_scope must be an object")
    require(safety.get("power") == "USB 5 V SELV only", "power scope must be USB 5 V SELV only")
    require(safety.get("legal_for_trade") is False, "legal_for_trade must be false")
    require(safety.get("safety_certified") is False, "safety_certified must be false")
    forbidden = set(safety.get("forbidden_uses", []))
    require({"mains", "medical", "life-safety", "hazardous-process", "weapon"} <= forbidden,
            "forbidden use set is incomplete")
    checks.append("safety scope")

    docs = data.get("documents")
    require(isinstance(docs, dict), "documents must be an object")
    required_doc_keys = {
        "requirements", "architecture", "interfaces", "protocol",
        "verification_plan", "risk_register"
    }
    require(required_doc_keys <= set(docs), "document map is incomplete")
    text_by_key = {key: read_relative(value) for key, value in docs.items()}
    checks.append(f"{len(text_by_key)} required documents")

    requirements = table_ids(text_by_key["requirements"], ID_RE)
    require(len(requirements) == len(set(requirements)), "duplicate requirement IDs found")
    prefixes = {item.split("-", 1)[0] for item in requirements}
    require(set(data.get("requirement_prefixes", [])) == prefixes,
            f"requirement prefixes differ: contract={data.get('requirement_prefixes')} docs={sorted(prefixes)}")
    require(len(requirements) >= 30, "requirements baseline is unexpectedly incomplete")
    checks.append(f"{len(requirements)} unique requirements")

    planned_tests = table_ids(text_by_key["verification_plan"], TEST_ID_RE)
    planned_test_set = set(planned_tests)
    required_tests = set(data.get("verification_tests", []))
    require(required_tests == REQUIRED_VERIFICATION_TESTS,
            "verification_tests must equal the canonical acceptance test set")
    require(required_tests <= planned_test_set,
            f"verification tests missing from plan: {sorted(required_tests - planned_test_set)}")
    require("UNEXECUTED" in text_by_key["verification_plan"],
            "verification plan must visibly declare physical work unexecuted")
    checks.append(f"{len(required_tests)} required verification tests")

    risk_ids = set(table_ids(text_by_key["risk_register"], RISK_ID_RE))
    expected_risks = set(data.get("risk_ids", []))
    require(risk_ids == expected_risks,
            f"risk IDs differ: contract-only={sorted(expected_risks-risk_ids)} docs-only={sorted(risk_ids-expected_risks)}")
    checks.append(f"{len(risk_ids)} required risks")

    measurement = data.get("measurement")
    require(isinstance(measurement, dict), "measurement must be an object")
    require(measurement.get("minimum_calibration_count", 0) >= 10,
            "minimum calibration count must be at least 10")
    require(measurement.get("minimum_stability_seconds", 0) >= 2,
            "minimum stability dwell must be at least two seconds")
    require(measurement.get("minimum_stability_samples", 0) >= 20,
            "minimum stability sample count must be at least 20")
    require(measurement.get("minimum_unit_mass_to_noise_band_ratio", 0) >= 20,
            "minimum unit-mass/noise ratio must be at least 20")
    no_count = set(measurement.get("required_no_count_states", []))
    require(no_count == REQUIRED_NO_COUNT_STATES,
            "required_no_count_states must equal the canonical fail-closed set")
    architecture = text_by_key["architecture"]
    for state in no_count:
        require(f"`{state}`" in architecture, f"architecture omits no-count state {state}")
    checks.append(f"measurement model and {len(no_count)} no-count states")

    require("/api/v1" in text_by_key["protocol"], "protocol must retain /api/v1 boundary")
    require("No Internet service is required" in text_by_key["protocol"],
            "protocol must retain local-only operation")
    for state in no_count:
        require(f"`{state}`" in text_by_key["protocol"],
                f"protocol omits no-count state {state}")
    require("`estimatedCount` and `uncertaintyPieces` are `null`" in text_by_key["protocol"],
            "protocol must null count and uncertainty in every no-count state")
    checks.append("protocol boundary")

    gates = data.get("dependency_gates")
    require(isinstance(gates, dict), "dependency_gates must be an object")
    require(list(gates.values()) == sorted(gates.values()), "dependency gates must remain ordered")
    require(set(gates.values()) == set(range(2, 8)), "dependency gates must cover issues 2 through 7")
    checks.append("dependency order")

    evidence = data.get("evidence_status")
    require(isinstance(evidence, dict), "evidence_status must be an object")
    require(evidence == EXPECTED_EVIDENCE_STATUS,
            "evidence_status must equal the canonical pre-implementation states")
    checks.append("evidence separation")

    return checks


def main() -> int:
    try:
        checks = validate_contract(load_contract())
    except ContractError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    for check in checks:
        print(f"PASS: {check}")
    print(f"PASS: architecture contract validation complete ({len(checks)} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
