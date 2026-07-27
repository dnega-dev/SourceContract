import unittest

from _support import make_record

from sourcecontract import AdapterContext, AdapterResult
from sourcecontract.adapters import JSONReferenceAdapter
from sourcecontract.contract import parse_contract_version, validate_adapter_contract
from sourcecontract.errors import (
    AdapterContractError,
    ContractVersionError,
    PartialFetchError,
    RecordValidationError,
)


class AdapterContractTests(unittest.TestCase):
    def test_reference_adapter_contract_passes(self):
        self.assertIsNone(validate_adapter_contract(JSONReferenceAdapter()))

    def test_missing_contract_metadata_fails(self):
        class Empty:
            pass

        with self.assertRaises(AdapterContractError):
            validate_adapter_contract(Empty())

    def test_wrong_contract_name_fails(self):
        adapter = JSONReferenceAdapter()
        adapter.contract_name = "other.contract"
        with self.assertRaises(AdapterContractError):
            validate_adapter_contract(adapter)

    def test_major_version_mismatch_fails(self):
        adapter = JSONReferenceAdapter()
        adapter.contract_version = "2.0"
        with self.assertRaises(ContractVersionError):
            validate_adapter_contract(adapter)

    def test_newer_minor_version_fails(self):
        adapter = JSONReferenceAdapter()
        adapter.contract_version = "1.1"
        with self.assertRaises(ContractVersionError):
            validate_adapter_contract(adapter)

    def test_version_syntax_is_strict(self):
        for value in ("1", "v1.0", "01.0", "1.0.0"):
            with self.subTest(value=value), self.assertRaises(ContractVersionError):
                parse_contract_version(value)

    def test_context_normalizes_retrieval_time(self):
        context = AdapterContext(
            "https://official.example.test/a", "2025-01-15T07:30:00-05:00"
        )
        self.assertEqual(context.retrieved_at, "2025-01-15T12:30:00Z")

    def test_context_rejects_partial_fetch(self):
        context = AdapterContext(
            "https://official.example.test/a", "2025-01-15T12:30:00Z", complete=False
        )
        with self.assertRaises(PartialFetchError):
            context.require_complete()

    def test_context_url_and_metadata_are_strict(self):
        with self.assertRaisesRegex(RecordValidationError, "HTTP"):
            AdapterContext("file:///tmp/source", "2025-01-15T12:30:00Z")
        context = AdapterContext(
            "https://official.example.test/a",
            "2025-01-15T12:30:00Z",
            metadata={"etag": "abc"},
        )
        with self.assertRaises(TypeError):
            context.metadata["etag"] = "changed"

    def test_adapter_result_requires_tuple(self):
        with self.assertRaises(AdapterContractError):
            AdapterResult(records=[make_record()])
        self.assertEqual(AdapterResult(records=(make_record(),)).records[0].stable_id, "record:1")


if __name__ == "__main__":
    unittest.main()
