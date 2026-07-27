import json
from pathlib import Path
import shutil
import unittest

from _support import ROOT, make_record

from sourcecontract import AdapterResult, SourceRecord
from sourcecontract.adapters import JSONReferenceAdapter, XMLReferenceAdapter
from sourcecontract.errors import FixtureError
from sourcecontract.runner import FixtureRepository, FixtureRunner


class FixtureRepositoryTests(unittest.TestCase):
    def test_packaged_repository_has_twenty_adversarial_fixtures(self):
        fixtures = FixtureRepository().load()
        self.assertEqual(len(fixtures), 20)
        self.assertEqual(len({fixture.fixture_id for fixture in fixtures}), 20)
        self.assertEqual(sum(f.family == "json" for f in fixtures), 11)
        self.assertEqual(sum(f.family == "xml" for f in fixtures), 9)

    def test_fixture_order_is_deterministic(self):
        ids = [fixture.fixture_id for fixture in FixtureRepository().load()]
        self.assertEqual(ids, sorted(ids))

    def test_fixtures_cover_required_adversarial_tags(self):
        tags = {tag for fixture in FixtureRepository().load() for tag in fixture.tags}
        required = {
            "identity",
            "exact-span",
            "hierarchy",
            "hashing",
            "temporal",
            "duplicates",
            "supersession",
            "tombstone",
            "partial-fetch",
        }
        self.assertTrue(required.issubset(tags), required - tags)

    def test_unknown_fixture_selection_fails(self):
        with self.assertRaisesRegex(FixtureError, "unknown"):
            FixtureRunner().fixtures(fixture_ids=["does-not-exist"])

    def test_family_selection_is_strict(self):
        fixtures = FixtureRunner().fixtures(family="json")
        self.assertTrue(fixtures)
        self.assertTrue(all(fixture.family == "json" for fixture in fixtures))
        with self.assertRaisesRegex(FixtureError, "no fixtures"):
            FixtureRunner().fixtures(family="other")

    def test_custom_repository_rejects_payload_traversal(self):
        scratch = ROOT / "tests" / ".fixture-scratch"
        shutil.rmtree(scratch, ignore_errors=True)
        scratch.mkdir()
        manifest = {
            "id": "escape",
            "family": "json",
            "title": "Escape",
            "payload": "../outside.json",
            "context": {
                "source_url": "https://official.example.test/a",
                "retrieved_at": "2025-01-01T00:00:00Z",
            },
            "expect": {"records": []},
        }
        (scratch / "escape.fixture.json").write_text(json.dumps(manifest), encoding="utf-8")
        try:
            with self.assertRaisesRegex(FixtureError, "traversal"):
                FixtureRepository(scratch).load()
        finally:
            shutil.rmtree(scratch)


class FixtureRunnerTests(unittest.TestCase):
    def test_json_reference_adapter_passes_all_json_fixtures(self):
        report = FixtureRunner().run(JSONReferenceAdapter())
        self.assertTrue(report.passed)
        self.assertEqual(report.fixture_count, 11)
        self.assertEqual(report.issue_count, 0)

    def test_xml_reference_adapter_passes_all_xml_fixtures(self):
        report = FixtureRunner().run(XMLReferenceAdapter())
        self.assertTrue(report.passed)
        self.assertEqual(report.fixture_count, 9)

    def test_fixture_subset_runs_only_requested_case(self):
        report = FixtureRunner().run(
            JSONReferenceAdapter(), fixture_ids=["json-basic"]
        )
        self.assertEqual(report.fixture_count, 1)
        self.assertEqual(report.fixture_results[0].fixture_id, "json-basic")

    def test_family_mismatch_fails_before_execution(self):
        with self.assertRaisesRegex(FixtureError, "does not match"):
            FixtureRunner().run(JSONReferenceAdapter(), family="xml")

    def test_nondeterministic_output_is_reported(self):
        class AlternatingAdapter(JSONReferenceAdapter):
            name = "alternating"

            def __init__(self):
                self.calls = 0

            def ingest(self, payload, context):
                result = super().ingest(payload, context)
                self.calls += 1
                if self.calls % 2 == 0 and result.records:
                    changed = SourceRecord.from_mapping(
                        {**result.records[0].to_dict(), "title": "changed"}
                    )
                    return AdapterResult(records=(changed,) + result.records[1:])
                return result

        report = FixtureRunner().run(
            AlternatingAdapter(), fixture_ids=["json-basic"]
        )
        self.assertFalse(report.passed)
        self.assertIn("SC101", {issue.rule_id for issue in report.fixture_results[0].issues})

    def test_duplicate_identity_is_reported(self):
        class DuplicateAdapter(JSONReferenceAdapter):
            name = "duplicate"

            def ingest(self, payload, context):
                result = super().ingest(payload, context)
                return AdapterResult(records=result.records + result.records)

        report = FixtureRunner().run(
            DuplicateAdapter(), fixture_ids=["json-basic"]
        )
        rules = {issue.rule_id for issue in report.fixture_results[0].issues}
        self.assertIn("SC107", rules)
        self.assertIn("SC102", rules)

    def test_wrong_hash_is_reported(self):
        class WrongHashAdapter(JSONReferenceAdapter):
            name = "wrong-hash"

            def ingest(self, payload, context):
                result = super().ingest(payload, context)
                changed = SourceRecord.from_mapping(
                    {
                        **result.records[0].to_dict(),
                        "source_hash": "sha256:" + "0" * 64,
                    }
                )
                return AdapterResult(records=(changed,))

        report = FixtureRunner().run(
            WrongHashAdapter(), fixture_ids=["json-basic"]
        )
        self.assertIn(
            "SC105", {issue.rule_id for issue in report.fixture_results[0].issues}
        )

    def test_partial_fixture_requires_typed_rejection(self):
        class IgnoresPartialAdapter(JSONReferenceAdapter):
            name = "ignores-partial"

            def ingest(self, payload, context):
                return AdapterResult(records=())

        report = FixtureRunner().run(
            IgnoresPartialAdapter(), fixture_ids=["json-partial-context"]
        )
        self.assertFalse(report.passed)
        self.assertEqual(report.fixture_results[0].issues[0].rule_id, "SC109")

    def test_non_result_return_is_reported(self):
        class BadReturnAdapter(JSONReferenceAdapter):
            name = "bad-return"

            def ingest(self, payload, context):
                return []

        report = FixtureRunner().run(
            BadReturnAdapter(), fixture_ids=["json-basic"]
        )
        self.assertEqual(report.fixture_results[0].issues[0].rule_id, "SC111")


if __name__ == "__main__":
    unittest.main()
