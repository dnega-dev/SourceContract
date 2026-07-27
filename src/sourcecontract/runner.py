"""Deterministic fixture discovery and adapter validation runner."""

from dataclasses import dataclass
import importlib.resources
import json
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .contract import AdapterContext, AdapterResult, validate_adapter_contract
from .errors import FixtureError, SourceContractError
from .invariants import check_all, check_determinism, check_expected_records
from .model import Relationship, SourceRecord, hash_payload
from .result import FixtureResult, Issue, ValidationReport


@dataclass(frozen=True)
class Fixture:
    """One parsed fixture manifest plus immutable source payload bytes."""

    fixture_id: str
    family: str
    title: str
    description: str
    tags: Tuple[str, ...]
    payload_name: str
    payload: bytes
    context: AdapterContext
    expected_records: Optional[Tuple[SourceRecord, ...]]
    expected_error: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.fixture_id,
            "family": self.family,
            "title": self.title,
            "description": self.description,
            "tags": list(self.tags),
            "payload": self.payload_name,
            "expectation": (
                {"error": self.expected_error}
                if self.expected_error is not None
                else {"records": len(self.expected_records or ())}
            ),
        }


class FixtureRepository:
    """Load packaged or caller-supplied fixture directories without mutation."""

    def __init__(self, directory: Optional[Path] = None) -> None:
        self.directory = Path(directory) if directory is not None else None

    def load(self) -> Tuple[Fixture, ...]:
        if self.directory is None:
            root = importlib.resources.files("sourcecontract.fixtures")
            manifests = sorted(
                (item for item in root.iterdir() if item.name.endswith(".fixture.json")),
                key=lambda item: item.name,
            )
            fixtures = [self._from_traversable(root, item) for item in manifests]
        else:
            if not self.directory.is_dir():
                raise FixtureError("fixture directory does not exist", detail=str(self.directory))
            manifests = sorted(self.directory.glob("*.fixture.json"))
            fixtures = [self._from_path(self.directory, item) for item in manifests]
        if not fixtures:
            raise FixtureError("fixture repository contains no *.fixture.json manifests")
        ids = [fixture.fixture_id for fixture in fixtures]
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        if duplicates:
            raise FixtureError("duplicate fixture ids: {}".format(", ".join(duplicates)))
        return tuple(fixtures)

    def _from_traversable(self, root: Any, manifest: Any) -> Fixture:
        try:
            parsed = json.loads(manifest.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            raise FixtureError("cannot read fixture manifest {}".format(manifest.name), detail=str(exc)) from exc
        payload_name = self._payload_name(parsed, manifest.name)
        payload_resource = root.joinpath(*PurePosixPath(payload_name).parts)
        try:
            payload = payload_resource.read_bytes()
        except OSError as exc:
            raise FixtureError(
                "cannot read fixture payload {}".format(payload_name), detail=str(exc)
            ) from exc
        return self._parse(parsed, payload_name, payload, manifest.name)

    def _from_path(self, root: Path, manifest: Path) -> Fixture:
        try:
            parsed = json.loads(manifest.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            raise FixtureError("cannot read fixture manifest {}".format(manifest.name), detail=str(exc)) from exc
        payload_name = self._payload_name(parsed, manifest.name)
        root_resolved = root.resolve()
        payload_path = (root / payload_name).resolve()
        try:
            payload_path.relative_to(root_resolved)
        except ValueError as exc:
            raise FixtureError("fixture payload path escapes its repository") from exc
        try:
            payload = payload_path.read_bytes()
        except OSError as exc:
            raise FixtureError(
                "cannot read fixture payload {}".format(payload_name), detail=str(exc)
            ) from exc
        return self._parse(parsed, payload_name, payload, manifest.name)

    @staticmethod
    def _payload_name(parsed: Any, manifest_name: str) -> str:
        if not isinstance(parsed, dict) or not isinstance(parsed.get("payload"), str):
            raise FixtureError("fixture {} requires a string payload field".format(manifest_name))
        value = parsed["payload"]
        posix = PurePosixPath(value)
        if posix.is_absolute() or ".." in posix.parts or not posix.parts:
            raise FixtureError("fixture payload path must be relative and traversal-free")
        return value

    @classmethod
    def _parse(
        cls, parsed: Any, payload_name: str, payload: bytes, manifest_name: str
    ) -> Fixture:
        if not isinstance(parsed, dict):
            raise FixtureError("fixture {} root must be an object".format(manifest_name))
        allowed = {
            "id",
            "family",
            "title",
            "description",
            "tags",
            "payload",
            "context",
            "expect",
        }
        unknown = set(parsed) - allowed
        if unknown:
            raise FixtureError(
                "fixture {} has unknown fields: {}".format(
                    manifest_name, ", ".join(sorted(unknown))
                )
            )
        required = allowed - {"description", "tags"}
        missing = required - set(parsed)
        if missing:
            raise FixtureError(
                "fixture {} is missing fields: {}".format(
                    manifest_name, ", ".join(sorted(missing))
                )
            )
        for field_name in ("id", "family", "title"):
            if not isinstance(parsed[field_name], str) or not parsed[field_name]:
                raise FixtureError("fixture {} must have non-empty string {}".format(manifest_name, field_name))
        description = parsed.get("description", "")
        tags = parsed.get("tags", [])
        if not isinstance(description, str):
            raise FixtureError("fixture description must be a string")
        if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            raise FixtureError("fixture tags must be an array of strings")
        context_data = parsed["context"]
        if not isinstance(context_data, dict):
            raise FixtureError("fixture context must be an object")
        context_allowed = {"source_url", "retrieved_at", "complete", "metadata"}
        if set(context_data) - context_allowed:
            raise FixtureError("fixture context contains unknown fields")
        if not {"source_url", "retrieved_at"}.issubset(context_data):
            raise FixtureError("fixture context requires source_url and retrieved_at")
        context = AdapterContext(
            source_url=context_data["source_url"],
            retrieved_at=context_data["retrieved_at"],
            complete=context_data.get("complete", True),
            metadata=context_data.get("metadata", {}),
        )
        expectation = parsed["expect"]
        if not isinstance(expectation, dict):
            raise FixtureError("fixture expect must be an object")
        if set(expectation) not in ({"records"}, {"error"}):
            raise FixtureError("fixture expect must contain exactly one of records or error")
        expected_records: Optional[Tuple[SourceRecord, ...]] = None
        expected_error: Optional[str] = None
        if "error" in expectation:
            if not isinstance(expectation["error"], str) or not expectation["error"]:
                raise FixtureError("fixture expected error must be a non-empty code")
            expected_error = expectation["error"]
        else:
            records_data = expectation["records"]
            if not isinstance(records_data, list):
                raise FixtureError("fixture expected records must be an array")
            expected_records = tuple(
                cls._expected_record(value, context, payload, index)
                for index, value in enumerate(records_data)
            )
        return Fixture(
            fixture_id=parsed["id"],
            family=parsed["family"],
            title=parsed["title"],
            description=description,
            tags=tuple(tags),
            payload_name=payload_name,
            payload=payload,
            context=context,
            expected_records=expected_records,
            expected_error=expected_error,
        )

    @staticmethod
    def _expected_record(
        value: Any, context: AdapterContext, payload: bytes, index: int
    ) -> SourceRecord:
        if not isinstance(value, dict):
            raise FixtureError("expected record {} must be an object".format(index))
        expanded = dict(value)
        expanded.setdefault("source_url", context.source_url)
        expanded.setdefault("source_hash", hash_payload(payload))
        expanded.setdefault("retrieved_at", context.retrieved_at)
        expanded.setdefault("status", "active")
        expanded.setdefault("relationships", [])
        try:
            return SourceRecord.from_mapping(expanded)
        except SourceContractError as exc:
            raise FixtureError(
                "expected record {} is invalid".format(index), detail=str(exc)
            ) from exc


class FixtureRunner:
    """Execute selected fixtures twice and apply all contract invariants."""

    def __init__(self, repository: Optional[FixtureRepository] = None) -> None:
        self.repository = repository or FixtureRepository()

    def fixtures(
        self,
        *,
        family: Optional[str] = None,
        fixture_ids: Optional[Sequence[str]] = None,
    ) -> Tuple[Fixture, ...]:
        fixtures = self.repository.load()
        selected = [fixture for fixture in fixtures if family is None or fixture.family == family]
        if fixture_ids:
            wanted = set(fixture_ids)
            known = {fixture.fixture_id for fixture in fixtures}
            missing = sorted(wanted - known)
            if missing:
                raise FixtureError("unknown fixture ids: {}".format(", ".join(missing)))
            selected = [fixture for fixture in selected if fixture.fixture_id in wanted]
        if not selected:
            raise FixtureError("no fixtures matched the requested selection")
        return tuple(selected)

    def run(
        self,
        adapter: object,
        *,
        family: Optional[str] = None,
        fixture_ids: Optional[Sequence[str]] = None,
    ) -> ValidationReport:
        validate_adapter_contract(adapter)
        adapter_family = getattr(adapter, "fixture_family")
        selected_family = family or adapter_family
        if family is not None and family != adapter_family:
            raise FixtureError(
                "requested family {!r} does not match adapter family {!r}".format(
                    family, adapter_family
                )
            )
        fixtures = self.fixtures(family=selected_family, fixture_ids=fixture_ids)
        results = tuple(self._run_one(adapter, fixture) for fixture in fixtures)
        return ValidationReport(
            adapter_name=getattr(adapter, "name"),
            adapter_contract_version=getattr(adapter, "contract_version"),
            fixture_results=results,
        )

    @staticmethod
    def _run_one(adapter: object, fixture: Fixture) -> FixtureResult:
        first: Optional[AdapterResult] = None
        first_error: Optional[Exception] = None
        try:
            first = adapter.ingest(fixture.payload, fixture.context)  # type: ignore[attr-defined]
        except Exception as exc:
            first_error = exc
        expected_error = fixture.expected_error
        if expected_error is not None:
            if first_error is None:
                rule = "SC109" if expected_error == "PARTIAL_FETCH" else "SC110"
                issues = (
                    Issue(
                        rule,
                        "expected adapter error {}, but ingestion succeeded".format(expected_error),
                        fixture.fixture_id,
                    ),
                )
            else:
                actual_code = getattr(first_error, "code", first_error.__class__.__name__)
                issues = () if actual_code == expected_error else (
                    Issue(
                        "SC110",
                        "expected adapter error {}, got {}: {}".format(
                            expected_error, actual_code, first_error
                        ),
                        fixture.fixture_id,
                    ),
                )
            return FixtureResult(fixture.fixture_id, fixture.family, fixture.title, issues)
        if first_error is not None:
            issue = Issue(
                "SC110",
                "adapter raised {}: {}".format(first_error.__class__.__name__, first_error),
                fixture.fixture_id,
            )
            return FixtureResult(fixture.fixture_id, fixture.family, fixture.title, (issue,))
        if not isinstance(first, AdapterResult):
            issue = Issue(
                "SC111",
                "adapter ingest must return AdapterResult, got {}".format(
                    type(first).__name__
                ),
                fixture.fixture_id,
            )
            return FixtureResult(fixture.fixture_id, fixture.family, fixture.title, (issue,))
        issues: List[Issue] = []
        if not first.complete:
            issues.append(
                Issue("SC109", "adapter emitted an incomplete result", fixture.fixture_id)
            )
        try:
            second = adapter.ingest(fixture.payload, fixture.context)  # type: ignore[attr-defined]
        except Exception as exc:
            issues.append(
                Issue(
                    "SC101",
                    "second identical ingestion raised {}: {}".format(
                        exc.__class__.__name__, exc
                    ),
                    fixture.fixture_id,
                )
            )
        else:
            if not isinstance(second, AdapterResult):
                issues.append(
                    Issue(
                        "SC101",
                        "second identical ingestion returned a non-AdapterResult",
                        fixture.fixture_id,
                    )
                )
            else:
                issues.extend(check_determinism(first, second, fixture.fixture_id))
        issues.extend(check_all(first, fixture.payload, fixture.context, fixture.fixture_id))
        issues.extend(
            check_expected_records(
                first, fixture.expected_records or (), fixture.fixture_id
            )
        )
        ordered = tuple(sorted(set(issues)))
        return FixtureResult(fixture.fixture_id, fixture.family, fixture.title, ordered)
