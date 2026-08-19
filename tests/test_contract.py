from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_contract.py"
SPEC = importlib.util.spec_from_file_location("validate_contract", SCRIPT)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class ArchitectureContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = validator.load_contract()

    def test_repository_contract_passes(self) -> None:
        checks = validator.validate_contract(self.contract)
        self.assertGreaterEqual(len(checks), 10)

    def test_invalid_safety_scope_fails_closed(self) -> None:
        altered = json.loads(json.dumps(self.contract))
        altered["safety_scope"]["power"] = "mains"
        with self.assertRaisesRegex(validator.ContractError, "USB 5 V SELV"):
            validator.validate_contract(altered)

    def test_any_evidence_stage_cannot_be_preclaimed(self) -> None:
        for stage in validator.EXPECTED_EVIDENCE_STATUS:
            with self.subTest(stage=stage):
                altered = json.loads(json.dumps(self.contract))
                altered["evidence_status"][stage] = "passed"
                with self.assertRaisesRegex(validator.ContractError, "canonical pre-implementation"):
                    validator.validate_contract(altered)

    def test_required_verification_ids_fail_closed(self) -> None:
        altered = json.loads(json.dumps(self.contract))
        altered["verification_tests"] = []
        with self.assertRaisesRegex(validator.ContractError, "canonical acceptance test set"):
            validator.validate_contract(altered)

    def test_no_count_state_mutation_fails_closed(self) -> None:
        altered = json.loads(json.dumps(self.contract))
        altered["measurement"]["required_no_count_states"].remove("stale")
        with self.assertRaisesRegex(validator.ContractError, "canonical fail-closed set"):
            validator.validate_contract(altered)

    def test_document_mapping_is_required(self) -> None:
        altered = json.loads(json.dumps(self.contract))
        del altered["documents"]["risk_register"]
        with self.assertRaisesRegex(validator.ContractError, "document map is incomplete"):
            validator.validate_contract(altered)

    def test_dependency_gate_order_is_protected(self) -> None:
        altered = json.loads(json.dumps(self.contract))
        altered["dependency_gates"]["component_selection"] = 7
        with self.assertRaises(validator.ContractError):
            validator.validate_contract(altered)

    def test_risk_set_is_protected(self) -> None:
        altered = json.loads(json.dumps(self.contract))
        altered["risk_ids"].pop()
        with self.assertRaisesRegex(validator.ContractError, "risk IDs differ"):
            validator.validate_contract(altered)

    def test_contract_json_is_portable_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "contract.json"
            output.write_text(json.dumps(self.contract, indent=2) + "\n", encoding="utf-8")
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), self.contract)


if __name__ == "__main__":
    unittest.main()
