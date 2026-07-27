"""Importable adapter target used to demonstrate ``module:attribute`` loading.

Run from the repository root after installation:

    sourcecontract validate examples.custom_adapter:OfficialJSONAdapter
"""

from sourcecontract.adapters import JSONReferenceAdapter


class OfficialJSONAdapter(JSONReferenceAdapter):
    """Example project adapter reusing the strict reference envelope mapping."""

    name = "example-official-json"
