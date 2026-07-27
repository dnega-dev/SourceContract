import json
import unittest

from _support import ROOT

from sourcecontract import AdapterContext, hash_payload
from sourcecontract.adapters import JSONReferenceAdapter, XMLReferenceAdapter
from sourcecontract.errors import AdapterInputError, ContractVersionError, PartialFetchError
from sourcecontract.runner import FixtureRepository


class ReferenceAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = {item.fixture_id: item for item in FixtureRepository().load()}

    def test_json_basic_record(self):
        fixture = self.fixtures["json-basic"]
        result = JSONReferenceAdapter().ingest(fixture.payload, fixture.context)
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0].stable_id, "rule:lights:1")
        self.assertEqual(result.records[0].source_hash, hash_payload(fixture.payload))

    def test_json_unicode_and_whitespace_are_exact(self):
        unicode_fixture = self.fixtures["json-unicode"]
        whitespace_fixture = self.fixtures["json-whitespace"]
        unicode_record = JSONReferenceAdapter().ingest(
            unicode_fixture.payload, unicode_fixture.context
        ).records[0]
        whitespace_record = JSONReferenceAdapter().ingest(
            whitespace_fixture.payload, whitespace_fixture.context
        ).records[0]
        self.assertIn("Cafe\u0301", unicode_record.exact_text)
        self.assertEqual(whitespace_record.exact_text, "  keep\tall spaces  \n")

    def test_json_rejects_malformed_and_non_utf8(self):
        context = AdapterContext("https://official.example.test/a", "2025-01-01T00:00:00Z")
        for payload in (b"{", b"\xff"):
            with self.subTest(payload=payload), self.assertRaises(AdapterInputError):
                JSONReferenceAdapter().ingest(payload, context)

    def test_json_rejects_unknown_root_field(self):
        context = AdapterContext("https://official.example.test/a", "2025-01-01T00:00:00Z")
        payload = json.dumps(
            {
                "contract_version": "1.0",
                "complete": True,
                "document_text": "",
                "records": [],
                "extra": True,
            }
        ).encode()
        with self.assertRaisesRegex(AdapterInputError, "unknown"):
            JSONReferenceAdapter().ingest(payload, context)

    def test_json_rejects_duplicate_object_keys(self):
        context = AdapterContext("https://official.example.test/a", "2025-01-01T00:00:00Z")
        payload = b'{"contract_version":"1.0","contract_version":"1.0","complete":true,"document_text":"","records":[]}'
        with self.assertRaisesRegex(AdapterInputError, "duplicate key"):
            JSONReferenceAdapter().ingest(payload, context)

    def test_json_rejects_incorrect_exact_text_assertion(self):
        context = AdapterContext("https://official.example.test/a", "2025-01-01T00:00:00Z")
        envelope = {
            "contract_version": "1.0",
            "complete": True,
            "document_text": "abc",
            "records": [
                {
                    "stable_id": "a",
                    "title": "A",
                    "hierarchy_path": ["A"],
                    "text_start": 0,
                    "text_end": 3,
                    "exact_text": "abd",
                    "effective_from": None,
                    "effective_to": None,
                }
            ],
        }
        with self.assertRaisesRegex(AdapterInputError, "exact_text"):
            JSONReferenceAdapter().ingest(json.dumps(envelope).encode(), context)

    def test_json_rejects_envelope_and_transport_partial_fetches(self):
        adapter = JSONReferenceAdapter()
        for fixture_id in ("json-partial-envelope", "json-partial-context"):
            fixture = self.fixtures[fixture_id]
            with self.subTest(fixture=fixture_id), self.assertRaises(PartialFetchError):
                adapter.ingest(fixture.payload, fixture.context)

    def test_json_rejects_incompatible_envelope_version(self):
        context = AdapterContext("https://official.example.test/a", "2025-01-01T00:00:00Z")
        envelope = {
            "contract_version": "2.0",
            "complete": True,
            "document_text": "",
            "records": [],
        }
        with self.assertRaises(ContractVersionError):
            JSONReferenceAdapter().ingest(json.dumps(envelope).encode(), context)

    def test_xml_basic_and_entity_decoding(self):
        adapter = XMLReferenceAdapter()
        basic = self.fixtures["xml-basic"]
        hierarchy = self.fixtures["xml-unicode-hierarchy"]
        basic_result = adapter.ingest(basic.payload, basic.context)
        hierarchy_result = adapter.ingest(hierarchy.payload, hierarchy.context)
        self.assertEqual(basic_result.records[0].stable_id, "xml:rule:a")
        self.assertEqual(
            hierarchy_result.records[1].exact_text,
            "Clause β says “safe & sound”.",
        )

    def test_xml_rejects_malformed_document(self):
        context = AdapterContext("https://official.example.test/a", "2025-01-01T00:00:00Z")
        with self.assertRaises(AdapterInputError):
            XMLReferenceAdapter().ingest(b"<source>", context)

    def test_xml_rejects_doctype_and_entity_declarations(self):
        context = AdapterContext("https://official.example.test/a", "2025-01-01T00:00:00Z")
        payload = b'<!DOCTYPE source [<!ENTITY x "boom">]><source complete="true" contract_version="1.0"><document>&x;</document></source>'
        with self.assertRaisesRegex(AdapterInputError, "DOCTYPE"):
            XMLReferenceAdapter().ingest(payload, context)

    def test_xml_rejects_unknown_attributes(self):
        context = AdapterContext("https://official.example.test/a", "2025-01-01T00:00:00Z")
        payload = b'<source complete="true" contract_version="1.0" extra="x"><document/></source>'
        with self.assertRaisesRegex(AdapterInputError, "unknown"):
            XMLReferenceAdapter().ingest(payload, context)

    def test_xml_rejects_relationship_missing_required_attributes(self):
        context = AdapterContext("https://official.example.test/a", "2025-01-01T00:00:00Z")
        payload = b'<source complete="true" contract_version="1.0"><document>a</document><record stable_id="a" title="A" start="0" end="1"><path><segment>A</segment></path><relationships><relationship detail="missing"/></relationships></record></source>'
        with self.assertRaisesRegex(AdapterInputError, "requires type and target"):
            XMLReferenceAdapter().ingest(payload, context)

    def test_xml_rejects_envelope_and_transport_partial_fetches(self):
        adapter = XMLReferenceAdapter()
        for fixture_id in ("xml-partial-envelope", "xml-partial-context"):
            fixture = self.fixtures[fixture_id]
            with self.subTest(fixture=fixture_id), self.assertRaises(PartialFetchError):
                adapter.ingest(fixture.payload, fixture.context)


if __name__ == "__main__":
    unittest.main()
