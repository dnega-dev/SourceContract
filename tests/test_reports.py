import json
import unittest
import xml.etree.ElementTree as ET

from _support import make_record

from sourcecontract.result import FixtureResult, Issue, ValidationReport
from sourcecontract.reports import (
    render_json,
    render_junit,
    render_report,
    render_sarif,
    render_text,
)


def sample_report(failing=True):
    issues = (
        Issue("SC103", "text differs", "fixture-bad", "record:1"),
    ) if failing else ()
    return ValidationReport(
        adapter_name="sample",
        adapter_contract_version="1.0",
        fixture_results=(
            FixtureResult("fixture-good", "json", "Good fixture", ()),
            FixtureResult("fixture-bad", "json", "Bad fixture", issues),
        ),
    )


class ReportTests(unittest.TestCase):
    def test_text_contains_summary_and_issue(self):
        rendered = render_text(sample_report())
        self.assertIn("FAIL fixture-bad", rendered)
        self.assertIn("SC103", rendered)
        self.assertIn("1 passed, 1 failed, 2 total", rendered)

    def test_json_is_parseable_complete_report(self):
        value = json.loads(render_json(sample_report()))
        self.assertFalse(value["passed"])
        self.assertEqual(value["summary"]["fixtures"], 2)
        self.assertEqual(value["fixtures"][1]["issues"][0]["record_id"], "record:1")

    def test_junit_is_parseable_and_counts_failures(self):
        root = ET.fromstring(render_junit(sample_report()))
        self.assertEqual(root.tag, "testsuite")
        self.assertEqual(root.attrib["tests"], "2")
        self.assertEqual(root.attrib["failures"], "1")
        self.assertEqual(len(root.findall("testcase/failure")), 1)

    def test_sarif_has_rule_result_and_location(self):
        value = json.loads(render_sarif(sample_report()))
        self.assertEqual(value["version"], "2.1.0")
        run = value["runs"][0]
        self.assertEqual(run["tool"]["driver"]["rules"][0]["id"], "SC103")
        self.assertEqual(run["results"][0]["ruleId"], "SC103")
        self.assertIn("sourcecontract-fixture", run["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"])

    def test_all_renderers_are_deterministic(self):
        report = sample_report()
        for format_name in ("text", "json", "junit", "sarif"):
            with self.subTest(format=format_name):
                self.assertEqual(
                    render_report(report, format_name),
                    render_report(report, format_name),
                )

    def test_unknown_report_format_fails(self):
        with self.assertRaises(ValueError):
            render_report(sample_report(), "yaml")


if __name__ == "__main__":
    unittest.main()
