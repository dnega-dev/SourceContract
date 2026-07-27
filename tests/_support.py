"""Shared test bootstrap and canonical value helpers."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sourcecontract import AdapterResult, Relationship, SourceRecord, hash_payload  # noqa: E402
from sourcecontract.adapters import JSONReferenceAdapter  # noqa: E402


def make_record(**overrides):
    payload = overrides.pop("payload", b"official bytes")
    values = {
        "stable_id": "record:1",
        "source_url": "https://official.example.test/source",
        "title": "Record 1",
        "hierarchy_path": ("Code", "Record 1"),
        "effective_from": "2024-01-01",
        "effective_to": None,
        "exact_text": "official text",
        "source_hash": hash_payload(payload),
        "retrieved_at": "2025-01-15T12:30:00Z",
        "status": "active",
        "relationships": (),
    }
    values.update(overrides)
    return SourceRecord(**values)


class NonConformantJSONAdapter(JSONReferenceAdapter):
    """Deterministic adapter that corrupts titles for CLI exit-code tests."""

    name = "nonconformant-json"

    def ingest(self, payload, context):
        result = super().ingest(payload, context)
        records = tuple(
            SourceRecord.from_mapping({**record.to_dict(), "title": "CORRUPTED"})
            for record in result.records
        )
        return AdapterResult(records=records)
