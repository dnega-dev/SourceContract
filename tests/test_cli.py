import contextlib
import io
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from _support import ROOT

from sourcecontract.cli import (
    EXIT_NONCONFORMANT,
    EXIT_OK,
    EXIT_USAGE,
    load_adapter,
    main,
)
from sourcecontract.errors import AdapterLoadError


class CLITests(unittest.TestCase):
    def run_cli(self, arguments):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_validate_json_success_and_json_report(self):
        code, stdout, stderr = self.run_cli(
            ["validate", "json", "--fixture", "json-basic", "--format", "json"]
        )
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(stderr, "")
        parsed = json.loads(stdout)
        self.assertTrue(parsed["passed"])
        self.assertEqual(parsed["summary"]["fixtures"], 1)

    def test_validate_xml_success_and_junit_report(self):
        code, stdout, stderr = self.run_cli(
            ["validate", "xml", "--fixture", "xml-basic", "--format", "junit"]
        )
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(stderr, "")
        self.assertEqual(ET.fromstring(stdout).attrib["failures"], "0")

    def test_nonconformant_adapter_returns_one(self):
        code, stdout, stderr = self.run_cli(
            [
                "validate",
                "_support:NonConformantJSONAdapter",
                "--fixture",
                "json-basic",
            ]
        )
        self.assertEqual(code, EXIT_NONCONFORMANT)
        self.assertIn("SC110", stdout)
        self.assertEqual(stderr, "")

    def test_adapter_load_error_returns_two(self):
        code, stdout, stderr = self.run_cli(["validate", "not-a-target"])
        self.assertEqual(code, EXIT_USAGE)
        self.assertEqual(stdout, "")
        self.assertIn("ADAPTER_LOAD", stderr)

    def test_family_mismatch_returns_two(self):
        code, stdout, stderr = self.run_cli(
            ["validate", "json", "--family", "xml"]
        )
        self.assertEqual(code, EXIT_USAGE)
        self.assertEqual(stdout, "")
        self.assertIn("FIXTURE_ERROR", stderr)

    def test_fixtures_list_json(self):
        code, stdout, stderr = self.run_cli(
            ["fixtures", "list", "--family", "xml", "--format", "json"]
        )
        parsed = json.loads(stdout)
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(parsed["count"], 9)
        self.assertTrue(all(item["family"] == "xml" for item in parsed["fixtures"]))
        self.assertEqual(stderr, "")

    def test_schema_command_defaults_to_source_record(self):
        code, stdout, stderr = self.run_cli(["schema"])
        parsed = json.loads(stdout)
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(parsed["title"], "SourceContract SourceRecord")
        self.assertEqual(stderr, "")

    def test_schema_compact_is_single_line(self):
        code, stdout, _ = self.run_cli(["schema", "contract", "--compact"])
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(len(stdout.splitlines()), 1)

    def test_report_can_be_written_to_file(self):
        destination = ROOT / "tests" / ".cli-report.json"
        destination.unlink(missing_ok=True)
        try:
            code, stdout, stderr = self.run_cli(
                [
                    "validate",
                    "json",
                    "--fixture",
                    "json-basic",
                    "--format",
                    "json",
                    "--output",
                    str(destination),
                ]
            )
            self.assertEqual(code, EXIT_OK)
            self.assertEqual(stdout, "")
            self.assertEqual(stderr, "")
            self.assertTrue(json.loads(destination.read_text(encoding="utf-8"))["passed"])
        finally:
            destination.unlink(missing_ok=True)

    def test_load_adapter_accepts_builtin_and_import_target(self):
        self.assertEqual(load_adapter("json").fixture_family, "json")
        self.assertEqual(
            load_adapter("_support:NonConformantJSONAdapter").name,
            "nonconformant-json",
        )

    def test_load_adapter_rejects_private_attribute_path(self):
        with self.assertRaises(AdapterLoadError):
            load_adapter("_support:_private")


if __name__ == "__main__":
    unittest.main()
