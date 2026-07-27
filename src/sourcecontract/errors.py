"""SourceContract exception hierarchy.

Exceptions carry stable machine-readable codes so fixture expectations and CLI callers
never need to match human prose.
"""

from typing import Optional


class SourceContractError(Exception):
    """Base error raised for expected SourceContract failures."""

    code = "SOURCECONTRACT_ERROR"

    def __init__(self, message: str, *, detail: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def __str__(self) -> str:
        if self.detail:
            return "{}: {}".format(self.message, self.detail)
        return self.message


class ContractVersionError(SourceContractError):
    """The adapter does not implement a compatible contract version."""

    code = "CONTRACT_VERSION"


class AdapterContractError(SourceContractError):
    """The adapter object is missing required contract surface area."""

    code = "ADAPTER_CONTRACT"


class AdapterInputError(SourceContractError):
    """Input bytes cannot be decoded according to an adapter format."""

    code = "ADAPTER_INPUT"


class PartialFetchError(SourceContractError):
    """Input is explicitly incomplete and therefore unsafe to emit."""

    code = "PARTIAL_FETCH"


class RecordValidationError(SourceContractError):
    """A canonical SourceRecord is malformed."""

    code = "RECORD_VALIDATION"


class FixtureError(SourceContractError):
    """A fixture manifest or payload is malformed."""

    code = "FIXTURE_ERROR"


class AdapterLoadError(SourceContractError):
    """A CLI adapter target cannot be imported or instantiated."""

    code = "ADAPTER_LOAD"
