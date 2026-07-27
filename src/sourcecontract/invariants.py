"""Named invariant checks used by the fixture runner."""

from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .contract import AdapterContext, AdapterResult
from .model import SourceRecord, canonical_retrieved_at, hash_payload
from .result import Issue

RULES: Mapping[str, str] = {
    "SC101": "Deterministic output",
    "SC102": "Stable identity",
    "SC103": "Exact-span fidelity",
    "SC104": "Hierarchy integrity",
    "SC105": "Source hashing",
    "SC106": "Temporal fields",
    "SC107": "Duplicate records",
    "SC108": "Supersession and tombstones",
    "SC109": "Partial-fetch rejection",
    "SC110": "Expected fixture outcome",
    "SC111": "Adapter result contract",
}


def check_determinism(
    first: AdapterResult, second: AdapterResult, fixture_id: str
) -> List[Issue]:
    if first.canonical_key() == second.canonical_key():
        return []
    return [
        Issue(
            "SC101",
            "identical payload and context produced different AdapterResult values",
            fixture_id,
        )
    ]


def check_source_hashing(
    result: AdapterResult, payload: bytes, fixture_id: str
) -> List[Issue]:
    expected = hash_payload(payload)
    return [
        Issue(
            "SC105",
            "source_hash does not equal SHA-256 of the exact fetched payload bytes",
            fixture_id,
            record.stable_id,
        )
        for record in result.records
        if record.source_hash != expected
    ]


def check_temporal_context(
    result: AdapterResult, context: AdapterContext, fixture_id: str
) -> List[Issue]:
    expected = canonical_retrieved_at(context.retrieved_at)
    return [
        Issue(
            "SC106",
            "retrieved_at differs from the retrieval context timestamp",
            fixture_id,
            record.stable_id,
        )
        for record in result.records
        if canonical_retrieved_at(record.retrieved_at) != expected
    ]


def check_duplicates(result: AdapterResult, fixture_id: str) -> List[Issue]:
    issues: List[Issue] = []
    seen_ids: Dict[str, int] = {}
    seen_records: Dict[Tuple[object, ...], int] = {}
    for index, record in enumerate(result.records):
        if record.stable_id in seen_ids:
            issues.append(
                Issue(
                    "SC107",
                    "stable_id appears more than once (positions {} and {})".format(
                        seen_ids[record.stable_id], index
                    ),
                    fixture_id,
                    record.stable_id,
                )
            )
        else:
            seen_ids[record.stable_id] = index
        key = record.canonical_key()
        if key in seen_records and record.stable_id not in {
            issue.record_id for issue in issues if issue.rule_id == "SC107"
        }:
            issues.append(
                Issue(
                    "SC107",
                    "identical record appears more than once (positions {} and {})".format(
                        seen_records[key], index
                    ),
                    fixture_id,
                    record.stable_id,
                )
            )
        else:
            seen_records[key] = index
    return issues


def check_hierarchy(result: AdapterResult, fixture_id: str) -> List[Issue]:
    issues: List[Issue] = []
    records = {record.stable_id: record for record in result.records}
    for record in result.records:
        for relationship in record.relationships:
            if relationship.type != "parent":
                continue
            if relationship.target == record.stable_id:
                issues.append(
                    Issue("SC104", "parent relationship is self-referential", fixture_id, record.stable_id)
                )
                continue
            parent = records.get(relationship.target)
            if parent is None:
                continue
            parent_path = parent.hierarchy_path
            child_path = record.hierarchy_path
            if len(parent_path) >= len(child_path) or child_path[: len(parent_path)] != parent_path:
                issues.append(
                    Issue(
                        "SC104",
                        "parent record hierarchy_path is not a strict prefix of child path",
                        fixture_id,
                        record.stable_id,
                    )
                )
    return issues


def check_lifecycle(result: AdapterResult, fixture_id: str) -> List[Issue]:
    issues: List[Issue] = []
    by_id = {record.stable_id: record for record in result.records}
    for record in result.records:
        relationship_types = {edge.type for edge in record.relationships}
        if record.status == "superseded":
            if record.effective_to is None:
                issues.append(
                    Issue(
                        "SC108",
                        "superseded record must define effective_to",
                        fixture_id,
                        record.stable_id,
                    )
                )
            if "superseded_by" not in relationship_types:
                issues.append(
                    Issue(
                        "SC108",
                        "superseded record must identify a superseded_by target",
                        fixture_id,
                        record.stable_id,
                    )
                )
        if record.status == "tombstone":
            if record.exact_text != "":
                issues.append(
                    Issue(
                        "SC108",
                        "tombstone exact_text must be empty",
                        fixture_id,
                        record.stable_id,
                    )
                )
            if not relationship_types.intersection({"replaces", "supersedes"}):
                issues.append(
                    Issue(
                        "SC108",
                        "tombstone must carry a replaces or supersedes relationship",
                        fixture_id,
                        record.stable_id,
                    )
                )
        for edge in record.relationships:
            if edge.type in {"replaces", "supersedes", "superseded_by"} and edge.target == record.stable_id:
                issues.append(
                    Issue(
                        "SC108",
                        "lifecycle relationship must not target the same stable_id",
                        fixture_id,
                        record.stable_id,
                    )
                )
            target = by_id.get(edge.target)
            if edge.type == "superseded_by" and target is not None and target.status == "superseded":
                issues.append(
                    Issue(
                        "SC108",
                        "superseded_by target is itself superseded in this result",
                        fixture_id,
                        record.stable_id,
                    )
                )
    return issues


def check_expected_records(
    actual: AdapterResult,
    expected: Sequence[SourceRecord],
    fixture_id: str,
) -> List[Issue]:
    """Compare expected canonical output while assigning semantic rule IDs."""

    issues: List[Issue] = []
    actual_ids = [record.stable_id for record in actual.records]
    expected_ids = [record.stable_id for record in expected]
    if actual_ids != expected_ids:
        issues.append(
            Issue(
                "SC102",
                "stable_id sequence differs: expected {!r}, got {!r}".format(
                    expected_ids, actual_ids
                ),
                fixture_id,
            )
        )
    actual_by_id = {record.stable_id: record for record in actual.records}
    for expected_record in expected:
        record = actual_by_id.get(expected_record.stable_id)
        if record is None:
            continue
        if record.exact_text != expected_record.exact_text:
            issues.append(
                Issue(
                    "SC103",
                    "exact_text differs from the fixture's authoritative source span",
                    fixture_id,
                    record.stable_id,
                )
            )
        if record.hierarchy_path != expected_record.hierarchy_path:
            issues.append(
                Issue(
                    "SC104",
                    "hierarchy_path differs from the fixture hierarchy",
                    fixture_id,
                    record.stable_id,
                )
            )
        if record.source_hash != expected_record.source_hash:
            issues.append(
                Issue(
                    "SC105",
                    "source_hash differs from the fixture payload digest",
                    fixture_id,
                    record.stable_id,
                )
            )
        if (
            record.effective_from != expected_record.effective_from
            or record.effective_to != expected_record.effective_to
            or canonical_retrieved_at(record.retrieved_at)
            != canonical_retrieved_at(expected_record.retrieved_at)
        ):
            issues.append(
                Issue(
                    "SC106",
                    "effective or retrieval temporal fields differ from fixture values",
                    fixture_id,
                    record.stable_id,
                )
            )
        nonsemantic_actual = (
            record.source_url,
            record.title,
            record.status,
            record.relationships,
        )
        nonsemantic_expected = (
            expected_record.source_url,
            expected_record.title,
            expected_record.status,
            expected_record.relationships,
        )
        if nonsemantic_actual != nonsemantic_expected:
            issues.append(
                Issue(
                    "SC110",
                    "record URL, title, status, or relationships differ from fixture values",
                    fixture_id,
                    record.stable_id,
                )
            )
    return issues


def check_all(
    result: AdapterResult,
    payload: bytes,
    context: AdapterContext,
    fixture_id: str,
) -> List[Issue]:
    issues: List[Issue] = []
    issues.extend(check_source_hashing(result, payload, fixture_id))
    issues.extend(check_temporal_context(result, context, fixture_id))
    issues.extend(check_duplicates(result, fixture_id))
    issues.extend(check_hierarchy(result, fixture_id))
    issues.extend(check_lifecycle(result, fixture_id))
    return issues
