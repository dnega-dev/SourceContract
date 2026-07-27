"""Immutable validation findings and aggregate reports."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from .contract import CONTRACT_VERSION


@dataclass(frozen=True, order=True)
class Issue:
    """One invariant violation with a stable rule identifier."""

    rule_id: str
    message: str
    fixture_id: str
    record_id: Optional[str] = None
    level: str = "error"

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "rule_id": self.rule_id,
            "level": self.level,
            "message": self.message,
            "fixture_id": self.fixture_id,
        }
        if self.record_id is not None:
            result["record_id"] = self.record_id
        return result


@dataclass(frozen=True)
class FixtureResult:
    """Validation outcome for one deterministic fixture."""

    fixture_id: str
    family: str
    title: str
    issues: Tuple[Issue, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        return not any(issue.level == "error" for issue in self.issues)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "family": self.family,
            "title": self.title,
            "passed": self.passed,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(frozen=True)
class ValidationReport:
    """Aggregate report returned by the library and rendered by CLI reporters."""

    adapter_name: str
    adapter_contract_version: str
    fixture_results: Tuple[FixtureResult, ...]
    contract_version: str = CONTRACT_VERSION

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.fixture_results)

    @property
    def fixture_count(self) -> int:
        return len(self.fixture_results)

    @property
    def passed_count(self) -> int:
        return sum(result.passed for result in self.fixture_results)

    @property
    def failed_count(self) -> int:
        return self.fixture_count - self.passed_count

    @property
    def issue_count(self) -> int:
        return sum(len(result.issues) for result in self.fixture_results)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": "SourceContract",
            "contract_version": self.contract_version,
            "adapter": {
                "name": self.adapter_name,
                "contract_version": self.adapter_contract_version,
            },
            "passed": self.passed,
            "summary": {
                "fixtures": self.fixture_count,
                "passed": self.passed_count,
                "failed": self.failed_count,
                "issues": self.issue_count,
            },
            "fixtures": [result.to_dict() for result in self.fixture_results],
        }
