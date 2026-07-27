"""SourceContract public library API."""

from .contract import (
    CONTRACT_NAME,
    CONTRACT_VERSION,
    AdapterContext,
    AdapterResult,
    SourceAdapter,
    validate_adapter_contract,
)
from .errors import (
    AdapterContractError,
    AdapterInputError,
    AdapterLoadError,
    ContractVersionError,
    FixtureError,
    PartialFetchError,
    RecordValidationError,
    SourceContractError,
)
from .model import Relationship, SourceRecord, hash_payload

__all__ = [
    "CONTRACT_NAME",
    "CONTRACT_VERSION",
    "AdapterContext",
    "AdapterResult",
    "SourceAdapter",
    "validate_adapter_contract",
    "Relationship",
    "SourceRecord",
    "hash_payload",
    "SourceContractError",
    "AdapterContractError",
    "AdapterInputError",
    "AdapterLoadError",
    "ContractVersionError",
    "FixtureError",
    "PartialFetchError",
    "RecordValidationError",
]

__version__ = "0.1.0"
