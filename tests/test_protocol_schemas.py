import copy
import json
import unittest
from pathlib import Path

import jsonschema
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "docs/schemas/api-v1"
FIXTURES = ROOT / "tests/fixtures/protocol/v1"
STATES = {
    "uncalibrated", "unstable", "stale", "disconnected", "saturated",
    "overload_indicated", "below_tare", "calibration_invalid",
    "uncertainty_excessive",
}


class ProtocolSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schemas = {
            path.name: json.loads(path.read_text(encoding="utf-8"))
            for path in SCHEMAS.glob("*.json")
        }
        export = cls.schemas["export.schema.json"]
        registry = Registry().with_resource(export["$id"], Resource.from_contents(export))
        cls.validators = {
            name: jsonschema.Draft202012Validator(
                schema,
                registry=registry,
            )
            for name, schema in cls.schemas.items()
        }

    def validate_fixture(self, fixture_name, schema_name):
        value = json.loads((FIXTURES / fixture_name).read_text(encoding="utf-8"))
        self.validators[schema_name].validate(value)
        return value

    def test_every_checked_in_schema_is_valid_draft_2020_12(self):
        for name, schema in self.schemas.items():
            with self.subTest(schema=name):
                jsonschema.Draft202012Validator.check_schema(schema)

    def test_every_route_family_fixture_validates(self):
        command_fixtures = [
            "tare-command.json", "calibrate-command.json",
            "profile-create-command.json", "profile-patch-command.json",
            "correction-command.json", "history-clear-command.json",
            "import-preview-command.json", "import-apply-command.json",
        ]
        for fixture in command_fixtures:
            with self.subTest(fixture=fixture):
                self.validate_fixture(fixture, "command.schema.json")
        for fixture in ("session-command.json", "provision-command.json"):
            with self.subTest(fixture=fixture):
                self.validate_fixture(fixture, "session-provision.schema.json")
        for fixture in ("status-stable.json", "status-disconnected.json"):
            with self.subTest(fixture=fixture):
                self.validate_fixture(fixture, "status.schema.json")
        self.validate_fixture("export-full.json", "export.schema.json")
        for fixture in ("event-gap-before.json", "event-gap-after.json"):
            with self.subTest(fixture=fixture):
                self.validate_fixture(fixture, "event.schema.json")

    def test_explicit_valid_and_invalid_route_examples(self):
        valid = self.validate_fixture("correction-command.json", "command.schema.json")
        for change in ({"reason": ""}, {"reason": "x" * 201}, {"count": -1}):
            invalid = dict(valid)
            invalid.update(change)
            with self.subTest(change=change):
                self.assertFalse(self.validators["command.schema.json"].is_valid(invalid))
        login = self.validate_fixture("session-command.json", "session-provision.schema.json")
        login["deviceSecret"] = "short"
        self.assertFalse(self.validators["session-provision.schema.json"].is_valid(login))

    def test_status_contract_has_every_no_count_state(self):
        schema = self.schemas["status.schema.json"]
        enum = set(schema["properties"]["measurement"]["properties"]["state"]["enum"])
        self.assertTrue(STATES <= enum)

    def test_no_count_fixture_nulls_count(self):
        value = self.validate_fixture("status-disconnected.json", "status.schema.json")
        self.assertIsNone(value["measurement"]["estimatedCount"])
        self.assertIsNone(value["measurement"]["uncertaintyPieces"])

    def test_status_count_fields_are_conditional_for_every_state(self):
        validator = self.validators["status.schema.json"]
        stable = self.validate_fixture("status-stable.json", "status.schema.json")
        disconnected = self.validate_fixture(
            "status-disconnected.json", "status.schema.json"
        )
        for state in STATES:
            value = copy.deepcopy(disconnected)
            value["measurement"]["state"] = state
            self.assertTrue(validator.is_valid(value), state)
            value["measurement"]["estimatedCount"] = 1
            value["measurement"]["uncertaintyPieces"] = 1
            self.assertFalse(validator.is_valid(value), state)
        for field in ("estimatedCount", "uncertaintyPieces"):
            value = copy.deepcopy(stable)
            value["measurement"][field] = None
            self.assertFalse(validator.is_valid(value), field)

    def test_target_adc_register_contract(self):
        source = (ROOT / "firmware/src/drivers/arduino_adapters.hpp").read_text(
            encoding="utf-8"
        )
        self.assertIn("kLdo3v0 = 0x02 << 3", source)
        self.assertIn("kPuCtrlCycleStart = 1U << 4", source)
        calibration_done = source.index("(control & kCalibrationStart) == 0")
        cycle_start = source.index("set_bits(kPuCtrl, kPuCtrlCycleStart)")
        self.assertGreater(cycle_start, calibration_done)

    def test_export_and_import_reject_secrets_at_any_depth(self):
        exported = self.validate_fixture("export-full.json", "export.schema.json")
        count_event, correction = exported["history"]
        self.assertNotEqual(count_event["eventId"], correction["eventId"])
        self.assertEqual(count_event["eventId"], correction["relatedEventId"])
        missing_reference = copy.deepcopy(exported)
        del missing_reference["history"][1]["relatedEventId"]
        self.assertFalse(
            self.validators["export.schema.json"].is_valid(missing_reference)
        )
        count_with_reference = copy.deepcopy(exported)
        count_with_reference["history"][0]["relatedEventId"] = "count-0"
        self.assertFalse(
            self.validators["export.schema.json"].is_valid(count_with_reference)
        )
        for key in ("wifiSsid", "wifiPassword", "wifiSecret", "deviceSecret", "token"):
            invalid = copy.deepcopy(exported)
            invalid["profiles"][0][key] = "must-not-export"
            with self.subTest(key=key):
                self.assertFalse(self.validators["export.schema.json"].is_valid(invalid))
        preview = self.validate_fixture("import-preview-command.json", "command.schema.json")
        preview["import"]["history"].append({"deviceSecret": "must-not-import"})
        self.assertFalse(self.validators["command.schema.json"].is_valid(preview))

    def test_event_gap_fixture_really_contains_a_gap(self):
        before = self.validate_fixture("event-gap-before.json", "event.schema.json")
        after = self.validate_fixture("event-gap-after.json", "event.schema.json")
        self.assertNotEqual(before["sequence"] + 1, after["sequence"])


if __name__ == "__main__":
    unittest.main()
