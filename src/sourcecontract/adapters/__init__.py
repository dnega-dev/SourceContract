"""Built-in reference adapters."""

from .json_adapter import JSONReferenceAdapter
from .xml_adapter import XMLReferenceAdapter

BUILTIN_ADAPTERS = {
    "json": JSONReferenceAdapter,
    "json-reference": JSONReferenceAdapter,
    "xml": XMLReferenceAdapter,
    "xml-reference": XMLReferenceAdapter,
}

__all__ = ["JSONReferenceAdapter", "XMLReferenceAdapter", "BUILTIN_ADAPTERS"]
