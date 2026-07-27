import unittest

from _support import ROOT

from sourcecontract.schema import get_schema, schema_names


class SchemaTests(unittest.TestCase):
    def test_schema_names_are_sorted(self):
        self.assertEqual(schema_names(), ("contract", "fixture", "source-record"))

    def test_source_record_schema_contains_all_canonical_fields(self):
        schema = get_schema("source-record")
        expected = {
            "stable_id",
            "source_url",
            "title",
            "hierarchy_path",
            "effective_from",
            "effective_to",
            "exact_text",
            "source_hash",
            "retrieved_at",
            "status",
            "relationships",
        }
        self.assertEqual(set(schema["required"]), expected)
        self.assertFalse(schema["additionalProperties"])

    def test_fixture_schema_models_record_defaults(self):
        schema = get_schema("fixture")
        record_schema = schema["properties"]["expect"]["oneOf"][1]["properties"]["records"]["items"]
        self.assertIn("stable_id", record_schema["required"])
        self.assertNotIn("source_hash", record_schema["required"])
        self.assertIn("source_hash", record_schema["properties"])

    def test_get_schema_returns_an_independent_copy(self):
        first = get_schema("contract")
        first["title"] = "changed"
        self.assertNotEqual(get_schema("contract")["title"], "changed")

    def test_unknown_schema_name_fails(self):
        with self.assertRaises(KeyError):
            get_schema("other")


if __name__ == "__main__":
    unittest.main()
