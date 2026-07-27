import unittest

from _support import make_record

from sourcecontract import AdapterContext, AdapterResult, Relationship
from sourcecontract.invariants import (
    check_duplicates,
    check_hierarchy,
    check_lifecycle,
    check_temporal_context,
)


class InvariantTests(unittest.TestCase):
    def test_parent_path_must_be_strict_prefix(self):
        parent = make_record(stable_id="parent", hierarchy_path=("Code", "Part"))
        child = make_record(
            stable_id="child",
            hierarchy_path=("Other", "Child"),
            relationships=(Relationship("parent", "parent"),),
        )
        issues = check_hierarchy(AdapterResult((parent, child)), "fixture")
        self.assertEqual([issue.rule_id for issue in issues], ["SC104"])

    def test_valid_parent_path_passes(self):
        parent = make_record(stable_id="parent", hierarchy_path=("Code", "Part"))
        child = make_record(
            stable_id="child",
            hierarchy_path=("Code", "Part", "Section"),
            relationships=(Relationship("parent", "parent"),),
        )
        self.assertEqual(check_hierarchy(AdapterResult((parent, child)), "fixture"), [])

    def test_superseded_record_requires_end_and_successor(self):
        record = make_record(status="superseded", effective_to=None)
        issues = check_lifecycle(AdapterResult((record,)), "fixture")
        self.assertEqual(sum(issue.rule_id == "SC108" for issue in issues), 2)

    def test_tombstone_requires_lifecycle_edge(self):
        record = make_record(status="tombstone", exact_text="")
        issues = check_lifecycle(AdapterResult((record,)), "fixture")
        self.assertTrue(any("tombstone" in issue.message for issue in issues))

    def test_duplicate_stable_id_is_found(self):
        first = make_record()
        second = make_record(title="Other title", exact_text="other")
        issues = check_duplicates(AdapterResult((first, second)), "fixture")
        self.assertTrue(any(issue.rule_id == "SC107" for issue in issues))

    def test_retrieval_context_difference_is_found(self):
        result = AdapterResult((make_record(retrieved_at="2025-01-01T00:00:00Z"),))
        context = AdapterContext(
            "https://official.example.test/source", "2025-01-02T00:00:00Z"
        )
        issues = check_temporal_context(result, context, "fixture")
        self.assertEqual([issue.rule_id for issue in issues], ["SC106"])


if __name__ == "__main__":
    unittest.main()
