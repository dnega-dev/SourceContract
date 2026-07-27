import unittest

from _support import make_record

from sourcecontract import Relationship, SourceRecord, hash_payload
from sourcecontract.errors import RecordValidationError
from sourcecontract.model import canonical_retrieved_at, parse_effective


class SourceRecordTests(unittest.TestCase):
    def test_hash_payload_known_value(self):
        self.assertEqual(
            hash_payload(b"abc"),
            "sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        )

    def test_mapping_round_trip_is_canonical(self):
        original = make_record(
            relationships=(Relationship("cites", "record:2", "footnote"),),
            retrieved_at="2025-01-15T07:30:00-05:00",
        )
        restored = SourceRecord.from_mapping(original.to_dict())
        self.assertEqual(restored, original)
        self.assertEqual(restored.retrieved_at, "2025-01-15T12:30:00Z")

    def test_record_is_immutable(self):
        record = make_record()
        with self.assertRaises(AttributeError):
            record.title = "changed"

    def test_invalid_stable_id_is_rejected(self):
        with self.assertRaisesRegex(RecordValidationError, "stable_id"):
            make_record(stable_id="space is invalid")

    def test_source_url_must_be_http_without_fragment(self):
        for value in ("relative/path", "ftp://example.test/a", "https://example.test/a#part"):
            with self.subTest(value=value), self.assertRaises(RecordValidationError):
                make_record(source_url=value)

    def test_non_tombstone_requires_text(self):
        with self.assertRaisesRegex(RecordValidationError, "tombstones"):
            make_record(exact_text="")
        self.assertEqual(make_record(status="tombstone", exact_text="").exact_text, "")

    def test_hierarchy_requires_nonempty_segments(self):
        with self.assertRaises(RecordValidationError):
            make_record(hierarchy_path=())
        with self.assertRaises(RecordValidationError):
            make_record(hierarchy_path=("Code", ""))

    def test_effective_range_is_ordered(self):
        with self.assertRaisesRegex(RecordValidationError, "later"):
            make_record(effective_from="2025-02-01", effective_to="2025-01-01")

    def test_naive_effective_datetime_is_rejected(self):
        with self.assertRaisesRegex(RecordValidationError, "UTC offset"):
            make_record(effective_from="2025-01-01T12:00:00")

    def test_retrieved_at_must_be_offset_aware(self):
        with self.assertRaisesRegex(RecordValidationError, "UTC offset"):
            make_record(retrieved_at="2025-01-01T12:00:00")

    def test_retrieved_at_is_canonicalized(self):
        self.assertEqual(
            canonical_retrieved_at("2025-01-15T07:30:00-05:00"),
            "2025-01-15T12:30:00Z",
        )

    def test_relationship_type_and_target_are_strict(self):
        with self.assertRaises(RecordValidationError):
            Relationship("unknown", "record:2")
        with self.assertRaises(RecordValidationError):
            Relationship("cites", "bad target")

    def test_duplicate_relationships_are_rejected(self):
        edge = Relationship("cites", "record:2")
        with self.assertRaisesRegex(RecordValidationError, "duplicate"):
            make_record(relationships=(edge, edge))

    def test_mapping_rejects_unknown_fields(self):
        mapping = make_record().to_dict()
        mapping["unexpected"] = True
        with self.assertRaisesRegex(RecordValidationError, "unknown"):
            SourceRecord.from_mapping(mapping)


if __name__ == "__main__":
    unittest.main()
