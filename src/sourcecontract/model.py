"""Canonical SourceRecord value objects and validation helpers."""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
import hashlib
import re
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlsplit

from .errors import RecordValidationError

SOURCE_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
STABLE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@~-]{0,254}$")
ALLOWED_STATUSES = ("active", "superseded", "tombstone")
ALLOWED_RELATIONSHIPS = (
    "amends",
    "cites",
    "parent",
    "replaces",
    "superseded_by",
    "supersedes",
)


def hash_payload(payload: bytes) -> str:
    """Return the contract's canonical digest representation for source bytes."""

    return "sha256:" + hashlib.sha256(payload).hexdigest()


def parse_retrieved_at(value: str) -> datetime:
    """Parse a timezone-aware ISO-8601 retrieval timestamp."""

    if not isinstance(value, str) or not value:
        raise RecordValidationError("retrieved_at must be a non-empty ISO-8601 string")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise RecordValidationError("retrieved_at is not valid ISO-8601", detail=str(exc)) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RecordValidationError("retrieved_at must include a UTC offset")
    return parsed


def canonical_retrieved_at(value: str) -> str:
    """Normalize a retrieval timestamp to UTC with a ``Z`` suffix."""

    parsed = parse_retrieved_at(value).astimezone(timezone.utc)
    if parsed.microsecond:
        rendered = parsed.isoformat(timespec="microseconds")
    else:
        rendered = parsed.isoformat(timespec="seconds")
    return rendered.replace("+00:00", "Z")


def parse_effective(value: Optional[str], field_name: str) -> Optional[datetime]:
    """Parse an effective date or timezone-aware date-time for ordering checks."""

    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise RecordValidationError("{} must be null or a non-empty ISO-8601 string".format(field_name))
    try:
        if "T" not in value:
            parsed_date = date.fromisoformat(value)
            return datetime.combine(parsed_date, datetime.min.time(), tzinfo=timezone.utc)
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise RecordValidationError("{} is not valid ISO-8601".format(field_name), detail=str(exc)) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RecordValidationError("{} date-time must include a UTC offset".format(field_name))
    return parsed.astimezone(timezone.utc)


def validate_source_url(value: str) -> None:
    if not isinstance(value, str) or not value:
        raise RecordValidationError("source_url must be a non-empty string")
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise RecordValidationError("source_url must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password:
        raise RecordValidationError("source_url must not contain user information")
    if parsed.fragment:
        raise RecordValidationError("source_url must not contain a fragment")


@dataclass(frozen=True, order=True)
class Relationship:
    """A typed edge from one SourceRecord to another stable identifier."""

    type: str
    target: str
    detail: Optional[str] = None

    def __post_init__(self) -> None:
        if self.type not in ALLOWED_RELATIONSHIPS:
            raise RecordValidationError(
                "unsupported relationship type {!r}; expected one of {}".format(
                    self.type, ", ".join(ALLOWED_RELATIONSHIPS)
                )
            )
        if not isinstance(self.target, str) or not STABLE_ID_RE.fullmatch(self.target):
            raise RecordValidationError("relationship target is not a valid stable_id")
        if self.detail is not None and not isinstance(self.detail, str):
            raise RecordValidationError("relationship detail must be a string or null")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "Relationship":
        if not isinstance(value, Mapping):
            raise RecordValidationError("relationship must be an object")
        unknown = set(value) - {"type", "target", "detail"}
        if unknown:
            raise RecordValidationError(
                "relationship contains unknown fields: {}".format(", ".join(sorted(unknown)))
            )
        try:
            return cls(type=value["type"], target=value["target"], detail=value.get("detail"))
        except KeyError as exc:
            raise RecordValidationError("relationship requires type and target") from exc

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"type": self.type, "target": self.target}
        if self.detail is not None:
            result["detail"] = self.detail
        return result


@dataclass(frozen=True)
class SourceRecord:
    """Canonical, immutable record emitted by every conforming adapter.

    Field order is contract order and is preserved by :meth:`to_dict` for readable,
    deterministic output.  ``source_hash`` always hashes the unmodified fetched bytes,
    while ``exact_text`` is the authoritative text span represented by this record.
    """

    stable_id: str
    source_url: str
    title: str
    hierarchy_path: Tuple[str, ...]
    effective_from: Optional[str]
    effective_to: Optional[str]
    exact_text: str
    source_hash: str
    retrieved_at: str
    status: str = "active"
    relationships: Tuple[Relationship, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.stable_id, str) or not STABLE_ID_RE.fullmatch(self.stable_id):
            raise RecordValidationError(
                "stable_id must match {}".format(STABLE_ID_RE.pattern)
            )
        validate_source_url(self.source_url)
        if not isinstance(self.title, str) or not self.title.strip():
            raise RecordValidationError("title must be a non-empty string")
        if not isinstance(self.hierarchy_path, tuple) or not self.hierarchy_path:
            raise RecordValidationError("hierarchy_path must be a non-empty tuple")
        for segment in self.hierarchy_path:
            if not isinstance(segment, str) or not segment.strip():
                raise RecordValidationError("hierarchy_path segments must be non-empty strings")
        if not isinstance(self.exact_text, str):
            raise RecordValidationError("exact_text must be a string")
        if self.status != "tombstone" and self.exact_text == "":
            raise RecordValidationError("exact_text may be empty only for tombstones")
        if not isinstance(self.source_hash, str) or not SOURCE_HASH_RE.fullmatch(self.source_hash):
            raise RecordValidationError("source_hash must be sha256:<64 lowercase hex digits>")
        object.__setattr__(
            self, "retrieved_at", canonical_retrieved_at(self.retrieved_at)
        )
        start = parse_effective(self.effective_from, "effective_from")
        end = parse_effective(self.effective_to, "effective_to")
        if start is not None and end is not None and start > end:
            raise RecordValidationError("effective_from must not be later than effective_to")
        if self.status not in ALLOWED_STATUSES:
            raise RecordValidationError(
                "status must be one of {}".format(", ".join(ALLOWED_STATUSES))
            )
        if not isinstance(self.relationships, tuple):
            raise RecordValidationError("relationships must be a tuple")
        for relationship in self.relationships:
            if not isinstance(relationship, Relationship):
                raise RecordValidationError("relationships must contain Relationship values")
        if len(set(self.relationships)) != len(self.relationships):
            raise RecordValidationError("relationships must not contain duplicate edges")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "SourceRecord":
        """Construct a strict SourceRecord from a JSON-like mapping."""

        if not isinstance(value, Mapping):
            raise RecordValidationError("SourceRecord must be an object")
        fields = {
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
        unknown = set(value) - fields
        if unknown:
            raise RecordValidationError(
                "SourceRecord contains unknown fields: {}".format(", ".join(sorted(unknown)))
            )
        required = fields - {"status", "relationships"}
        missing = required - set(value)
        if missing:
            raise RecordValidationError(
                "SourceRecord is missing fields: {}".format(", ".join(sorted(missing)))
            )
        path_value = value["hierarchy_path"]
        if isinstance(path_value, (str, bytes)) or not isinstance(path_value, Sequence):
            raise RecordValidationError("hierarchy_path must be an array of strings")
        relationships_value = value.get("relationships", ())
        if isinstance(relationships_value, (str, bytes)) or not isinstance(
            relationships_value, Sequence
        ):
            raise RecordValidationError("relationships must be an array")
        return cls(
            stable_id=value["stable_id"],
            source_url=value["source_url"],
            title=value["title"],
            hierarchy_path=tuple(path_value),
            effective_from=value["effective_from"],
            effective_to=value["effective_to"],
            exact_text=value["exact_text"],
            source_hash=value["source_hash"],
            retrieved_at=canonical_retrieved_at(value["retrieved_at"]),
            status=value.get("status", "active"),
            relationships=tuple(Relationship.from_mapping(item) for item in relationships_value),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Return the canonical JSON-compatible representation."""

        return {
            "stable_id": self.stable_id,
            "source_url": self.source_url,
            "title": self.title,
            "hierarchy_path": list(self.hierarchy_path),
            "effective_from": self.effective_from,
            "effective_to": self.effective_to,
            "exact_text": self.exact_text,
            "source_hash": self.source_hash,
            "retrieved_at": canonical_retrieved_at(self.retrieved_at),
            "status": self.status,
            "relationships": [relationship.to_dict() for relationship in self.relationships],
        }

    def canonical_key(self) -> Tuple[Any, ...]:
        """Return a hashable value suitable for deterministic comparisons."""

        return (
            self.stable_id,
            self.source_url,
            self.title,
            self.hierarchy_path,
            self.effective_from,
            self.effective_to,
            self.exact_text,
            self.source_hash,
            canonical_retrieved_at(self.retrieved_at),
            self.status,
            self.relationships,
        )
