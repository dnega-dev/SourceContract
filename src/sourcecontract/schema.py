"""JSON Schema documents for the public SourceContract wire formats."""

from copy import deepcopy
from typing import Any, Dict

from .contract import CONTRACT_NAME, CONTRACT_VERSION
from .model import ALLOWED_RELATIONSHIPS, ALLOWED_STATUSES, SOURCE_HASH_RE, STABLE_ID_RE

_RELATIONSHIP_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["type", "target"],
    "properties": {
        "type": {"type": "string", "enum": list(ALLOWED_RELATIONSHIPS)},
        "target": {"type": "string", "pattern": STABLE_ID_RE.pattern},
        "detail": {"type": "string"},
    },
}

_SOURCE_RECORD_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "urn:sourcecontract:schema:source-record:1.0",
    "title": "SourceContract SourceRecord",
    "type": "object",
    "additionalProperties": False,
    "required": [
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
    ],
    "properties": {
        "stable_id": {"type": "string", "pattern": STABLE_ID_RE.pattern},
        "source_url": {"type": "string", "format": "uri", "pattern": "^https?://"},
        "title": {"type": "string", "minLength": 1},
        "hierarchy_path": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "minLength": 1},
        },
        "effective_from": {
            "anyOf": [
                {"type": "string", "format": "date"},
                {"type": "string", "format": "date-time"},
                {"type": "null"},
            ]
        },
        "effective_to": {
            "anyOf": [
                {"type": "string", "format": "date"},
                {"type": "string", "format": "date-time"},
                {"type": "null"},
            ]
        },
        "exact_text": {"type": "string"},
        "source_hash": {"type": "string", "pattern": SOURCE_HASH_RE.pattern},
        "retrieved_at": {"type": "string", "format": "date-time"},
        "status": {"type": "string", "enum": list(ALLOWED_STATUSES)},
        "relationships": {
            "type": "array",
            "uniqueItems": True,
            "items": _RELATIONSHIP_SCHEMA,
        },
    },
}

_EXPECTED_RECORD_SCHEMA: Dict[str, Any] = deepcopy(_SOURCE_RECORD_SCHEMA)
_EXPECTED_RECORD_SCHEMA.pop("$schema")
_EXPECTED_RECORD_SCHEMA.pop("$id")
_EXPECTED_RECORD_SCHEMA["title"] = "SourceContract fixture expected record"
_EXPECTED_RECORD_SCHEMA["required"] = [
    "stable_id",
    "title",
    "hierarchy_path",
    "effective_from",
    "effective_to",
    "exact_text",
]

_FIXTURE_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "urn:sourcecontract:schema:fixture:1.0",
    "title": "SourceContract Fixture Manifest",
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "family", "title", "payload", "context", "expect"],
    "properties": {
        "id": {"type": "string", "minLength": 1},
        "family": {"type": "string", "minLength": 1},
        "title": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
        "payload": {"type": "string", "minLength": 1},
        "context": {
            "type": "object",
            "additionalProperties": False,
            "required": ["source_url", "retrieved_at"],
            "properties": {
                "source_url": {"type": "string", "format": "uri"},
                "retrieved_at": {"type": "string", "format": "date-time"},
                "complete": {"type": "boolean", "default": True},
                "metadata": {"type": "object"},
            },
        },
        "expect": {
            "oneOf": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["error"],
                    "properties": {"error": {"type": "string", "minLength": 1}},
                },
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["records"],
                    "properties": {
                        "records": {
                            "type": "array",
                            "items": _EXPECTED_RECORD_SCHEMA,
                        }
                    },
                },
            ]
        },
    },
}

_CONTRACT_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "urn:sourcecontract:schema:adapter-contract:1.0",
    "title": "SourceContract Adapter Contract",
    "type": "object",
    "additionalProperties": False,
    "required": ["contract_name", "contract_version", "name", "fixture_family"],
    "properties": {
        "contract_name": {"const": CONTRACT_NAME},
        "contract_version": {"const": CONTRACT_VERSION},
        "name": {"type": "string", "minLength": 1},
        "fixture_family": {"type": "string", "minLength": 1},
    },
}

_SCHEMAS = {
    "source-record": _SOURCE_RECORD_SCHEMA,
    "fixture": _FIXTURE_SCHEMA,
    "contract": _CONTRACT_SCHEMA,
}


def schema_names():
    """Return supported schema names in deterministic order."""

    return tuple(sorted(_SCHEMAS))


def get_schema(name: str = "source-record") -> Dict[str, Any]:
    """Return an isolated schema mapping safe for caller mutation."""

    try:
        return deepcopy(_SCHEMAS[name])
    except KeyError as exc:
        raise KeyError(
            "unknown schema {!r}; choose {}".format(name, ", ".join(schema_names()))
        ) from exc
