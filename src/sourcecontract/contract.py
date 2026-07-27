"""Versioned adapter protocol shared by adapters and fixture runners."""

from dataclasses import dataclass, field
import re
from types import MappingProxyType
from typing import Any, Mapping, Protocol, Tuple, runtime_checkable

from .errors import AdapterContractError, ContractVersionError, PartialFetchError
from .model import SourceRecord, canonical_retrieved_at, validate_source_url

CONTRACT_VERSION = "1.0"
CONTRACT_NAME = "sourcecontract.adapter"
_VERSION_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


@dataclass(frozen=True)
class AdapterContext:
    """Immutable retrieval metadata supplied to an adapter for one payload."""

    source_url: str
    retrieved_at: str
    complete: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_source_url(self.source_url)
        object.__setattr__(self, "retrieved_at", canonical_retrieved_at(self.retrieved_at))
        if not isinstance(self.complete, bool):
            raise AdapterContractError("adapter context complete must be boolean")
        if not isinstance(self.metadata, Mapping):
            raise AdapterContractError("adapter context metadata must be a mapping")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def require_complete(self) -> None:
        """Reject partial transport results before parsing any payload bytes."""

        if not self.complete:
            raise PartialFetchError("adapter input is marked as an incomplete fetch")


@dataclass(frozen=True)
class AdapterResult:
    """Complete deterministic adapter output for one source payload."""

    records: Tuple[SourceRecord, ...]
    complete: bool = True
    warnings: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.records, tuple):
            raise AdapterContractError("AdapterResult.records must be a tuple")
        if any(not isinstance(record, SourceRecord) for record in self.records):
            raise AdapterContractError("AdapterResult.records must contain SourceRecord values")
        if not isinstance(self.complete, bool):
            raise AdapterContractError("AdapterResult.complete must be boolean")
        if not isinstance(self.warnings, tuple) or any(
            not isinstance(warning, str) for warning in self.warnings
        ):
            raise AdapterContractError("AdapterResult.warnings must be a tuple of strings")

    def canonical_key(self) -> Tuple[Any, ...]:
        return (
            tuple(record.canonical_key() for record in self.records),
            self.complete,
            self.warnings,
        )


@runtime_checkable
class SourceAdapter(Protocol):
    """Structural protocol implemented by SourceContract adapters."""

    contract_name: str
    contract_version: str
    name: str
    fixture_family: str

    def ingest(self, payload: bytes, context: AdapterContext) -> AdapterResult:
        """Convert complete source bytes to canonical records."""
        ...


def parse_contract_version(version: str) -> Tuple[int, int]:
    if not isinstance(version, str) or not _VERSION_RE.fullmatch(version):
        raise ContractVersionError("contract_version must use MAJOR.MINOR syntax")
    major, minor = version.split(".", 1)
    return int(major), int(minor)


def validate_adapter_contract(adapter: object) -> None:
    """Validate adapter metadata and major-version compatibility."""

    required_text = ("contract_name", "contract_version", "name", "fixture_family")
    missing = [
        field
        for field in required_text
        if not isinstance(getattr(adapter, field, None), str)
        or not getattr(adapter, field)
    ]
    if missing:
        raise AdapterContractError(
            "adapter is missing non-empty string attributes: {}".format(
                ", ".join(missing)
            )
        )
    if getattr(adapter, "contract_name") != CONTRACT_NAME:
        raise AdapterContractError(
            "adapter contract_name must be {!r}".format(CONTRACT_NAME)
        )
    if not callable(getattr(adapter, "ingest", None)):
        raise AdapterContractError("adapter must define callable ingest(payload, context)")
    expected_major, expected_minor = parse_contract_version(CONTRACT_VERSION)
    actual_major, actual_minor = parse_contract_version(getattr(adapter, "contract_version"))
    if actual_major != expected_major:
        raise ContractVersionError(
            "adapter contract major {} is incompatible with supported major {}".format(
                actual_major, expected_major
            )
        )
    if actual_minor > expected_minor:
        raise ContractVersionError(
            "adapter contract minor {} requires newer runner minor {}".format(
                actual_minor, expected_minor
            )
        )
