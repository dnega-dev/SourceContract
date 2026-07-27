"""Strict reference adapter for the SourceContract JSON fixture envelope."""

import json
from typing import Any, List, Mapping, Tuple

from ..contract import CONTRACT_NAME, CONTRACT_VERSION, AdapterContext, AdapterResult
from ..errors import AdapterInputError, ContractVersionError, PartialFetchError
from ..model import Relationship, SourceRecord, hash_payload


def _strict_object(pairs: List[Tuple[str, Any]]) -> Mapping[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise AdapterInputError("JSON object contains duplicate key {!r}".format(key))
        result[key] = value
    return result


class JSONReferenceAdapter:
    """Convert a documented JSON source envelope into canonical records."""

    contract_name = CONTRACT_NAME
    contract_version = CONTRACT_VERSION
    name = "json-reference"
    fixture_family = "json"

    def ingest(self, payload: bytes, context: AdapterContext) -> AdapterResult:
        context.require_complete()
        if not isinstance(payload, bytes):
            raise AdapterInputError("JSON adapter payload must be bytes")
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AdapterInputError("JSON payload must be UTF-8", detail=str(exc)) from exc
        try:
            document = json.loads(text, object_pairs_hook=_strict_object)
        except (json.JSONDecodeError, RecursionError) as exc:
            raise AdapterInputError("JSON payload is not valid JSON", detail=str(exc)) from exc
        if not isinstance(document, dict):
            raise AdapterInputError("JSON payload root must be an object")
        self._validate_root(document)
        if document["contract_version"] != CONTRACT_VERSION:
            raise ContractVersionError(
                "JSON envelope contract_version {!r} is unsupported".format(
                    document["contract_version"]
                )
            )
        if document["complete"] is not True:
            raise PartialFetchError("JSON envelope does not assert complete=true")
        source_text = document["document_text"]
        records = tuple(
            self._record(item, source_text, payload, context) for item in document["records"]
        )
        return AdapterResult(records=records)

    @staticmethod
    def _validate_root(document: Mapping[str, Any]) -> None:
        allowed = {"contract_version", "complete", "document_text", "records"}
        unknown = set(document) - allowed
        if unknown:
            raise AdapterInputError(
                "JSON envelope contains unknown fields: {}".format(", ".join(sorted(unknown)))
            )
        missing = allowed - set(document)
        if missing:
            raise AdapterInputError(
                "JSON envelope is missing fields: {}".format(", ".join(sorted(missing)))
            )
        if not isinstance(document["contract_version"], str):
            raise AdapterInputError("contract_version must be a string")
        if not isinstance(document["complete"], bool):
            raise AdapterInputError("complete must be boolean")
        if not isinstance(document["document_text"], str):
            raise AdapterInputError("document_text must be a string")
        if not isinstance(document["records"], list):
            raise AdapterInputError("records must be an array")

    @staticmethod
    def _record(
        item: Any, source_text: str, payload: bytes, context: AdapterContext
    ) -> SourceRecord:
        if not isinstance(item, dict):
            raise AdapterInputError("each JSON records item must be an object")
        allowed = {
            "stable_id",
            "source_url",
            "title",
            "hierarchy_path",
            "text_start",
            "text_end",
            "exact_text",
            "effective_from",
            "effective_to",
            "status",
            "relationships",
        }
        unknown = set(item) - allowed
        if unknown:
            raise AdapterInputError(
                "JSON record contains unknown fields: {}".format(", ".join(sorted(unknown)))
            )
        required = {
            "stable_id",
            "title",
            "hierarchy_path",
            "text_start",
            "text_end",
            "effective_from",
            "effective_to",
        }
        missing = required - set(item)
        if missing:
            raise AdapterInputError(
                "JSON record is missing fields: {}".format(", ".join(sorted(missing)))
            )
        start = item["text_start"]
        end = item["text_end"]
        if isinstance(start, bool) or not isinstance(start, int):
            raise AdapterInputError("text_start must be an integer")
        if isinstance(end, bool) or not isinstance(end, int):
            raise AdapterInputError("text_end must be an integer")
        if start < 0 or end < start or end > len(source_text):
            raise AdapterInputError("record text span is outside document_text")
        exact_text = source_text[start:end]
        if "exact_text" in item and item["exact_text"] != exact_text:
            raise AdapterInputError("record exact_text does not match its declared text span")
        path = item["hierarchy_path"]
        if not isinstance(path, list):
            raise AdapterInputError("hierarchy_path must be an array")
        relationships = item.get("relationships", [])
        if not isinstance(relationships, list):
            raise AdapterInputError("relationships must be an array")
        source_url = item.get("source_url", context.source_url)
        return SourceRecord(
            stable_id=item["stable_id"],
            source_url=source_url,
            title=item["title"],
            hierarchy_path=tuple(path),
            effective_from=item["effective_from"],
            effective_to=item["effective_to"],
            exact_text=exact_text,
            source_hash=hash_payload(payload),
            retrieved_at=context.retrieved_at,
            status=item.get("status", "active"),
            relationships=tuple(Relationship.from_mapping(edge) for edge in relationships),
        )
