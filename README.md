# SourceContract

SourceContract is a zero-runtime-dependency Python 3.9+ CLI and library for testing official-source ingestion adapters. It runs adapters against versioned, deterministic, adversarial fixtures and reports violations of a canonical source-record contract.

The project validates adapter behavior; it does not fetch remote sources, choose an authority, or certify the legal accuracy of source content.

## What the MVP includes

- Adapter contract `sourcecontract.adapter` version `1.0`, with explicit major/minor compatibility checks.
- Immutable `SourceRecord` values with stable identity, source provenance, hierarchy, temporal bounds, exact text, lifecycle status, and typed relationships.
- 20 packaged fixtures: 11 JSON and 9 XML, including Unicode normalization traps, duplicate titles, hierarchy edges, whitespace, empty results, supersession, tombstones, and two kinds of partial fetch.
- Built-in strict JSON and XML reference adapters.
- Determinism, identity, exact-span, hierarchy, source-hash, temporal, duplicate, lifecycle, and completeness checks.
- Deterministic text, JSON, JUnit XML, and SARIF 2.1.0 reports.
- CLI commands for validation, fixture discovery, and JSON Schema output.
- `unittest` coverage with no third-party test runner.

## Installation and development use

A local install creates the `sourcecontract` command:

```sh
python3 -m pip install .
sourcecontract --version
```

Without installing, run from the repository root:

```sh
PYTHONPATH=src python3 -m sourcecontract --version
```

There are no runtime dependencies outside the Python standard library. The build backend listed in `pyproject.toml` is used only when building/installing the package.

## Quick start

Validate both bundled reference adapters:

```sh
sourcecontract validate json
sourcecontract validate xml
```

Choose a machine-readable report or write it to a file:

```sh
sourcecontract validate json --format json
sourcecontract validate xml --format junit --output junit.xml
sourcecontract validate json --format sarif --output results.sarif
```

List fixtures and inspect schemas:

```sh
sourcecontract fixtures list
sourcecontract fixtures list --family json --format json
sourcecontract schema source-record
sourcecontract schema fixture
sourcecontract schema contract
```

Run a caller adapter exposed as an importable object or no-argument class:

```sh
sourcecontract validate your_package.adapter:OfficialAdapter
```

The target's `fixture_family` selects the fixture family. `--family` may be given explicitly, but it must agree with the adapter metadata. Use `--fixture ID` repeatedly to run a subset and `--fixtures-dir PATH` for a private fixture repository.

## Adapter contract

A conforming adapter exposes four string attributes and one method:

```python
from sourcecontract import AdapterContext, AdapterResult
from sourcecontract.adapters import JSONReferenceAdapter

class OfficialAdapter:
    contract_name = "sourcecontract.adapter"
    contract_version = "1.0"
    name = "official-json"
    fixture_family = "json"
    _mapping = JSONReferenceAdapter()

    def ingest(self, payload: bytes, context: AdapterContext) -> AdapterResult:
        context.require_complete()
        return self._mapping.ingest(payload, context)
```

`ingest` receives the exact fetched bytes and immutable retrieval metadata. It must either return a complete `AdapterResult` or raise a typed error such as `PartialFetchError`. A partial result must never be represented as a successful subset.

Contract versions use `MAJOR.MINOR`:

- Different major versions are incompatible.
- An adapter minor version newer than the runner's minor version is rejected.
- An adapter at the same major and an equal or older minor is accepted.

The current contract is `1.0`, so only `1.0` is accepted in this release.

## Canonical `SourceRecord`

| Field | Meaning |
| --- | --- |
| `stable_id` | Source-defined identity that remains stable when display text changes. |
| `source_url` | Absolute HTTP(S) URL without credentials or fragments. |
| `title` | Human-readable source title; not an identity key. |
| `hierarchy_path` | Non-empty ordered path from source root to the record. |
| `effective_from` / `effective_to` | ISO-8601 dates or offset-aware date-times; either may be `null`. |
| `exact_text` | Exact authoritative character span, including meaningful whitespace. |
| `source_hash` | `sha256:` plus the lowercase SHA-256 digest of the complete payload bytes. |
| `retrieved_at` | Offset-aware ISO-8601 retrieval time, canonicalized to UTC. |
| `status` | `active`, `superseded`, or `tombstone`. |
| `relationships` | Typed edges such as `parent`, `supersedes`, or `superseded_by`. |

A tombstone is the one status allowed to carry empty `exact_text`; it must identify what it replaces or supersedes. A superseded record must have `effective_to` and a `superseded_by` relationship.

## Reference JSON envelope

The JSON adapter accepts a strict UTF-8 object. Character offsets are Python string indices into `document_text`; the adapter verifies an optional `exact_text` assertion and computes `source_hash` itself.

```json
{
  "complete": true,
  "contract_version": "1.0",
  "document_text": "Section 1. Keep this exact text.",
  "records": [
    {
      "effective_from": "2025-01-01",
      "effective_to": null,
      "exact_text": "Keep this exact text.",
      "hierarchy_path": ["Code", "Section 1"],
      "stable_id": "code:section-1",
      "text_end": 32,
      "text_start": 11,
      "title": "Section 1"
    }
  ]
}
```

Unknown fields, malformed spans, incompatible envelope versions, and non-UTF-8 input are rejected.

## Reference XML envelope

The XML adapter accepts a namespace-free `<source complete="true" contract_version="1.0">` document containing one leading `<document>` and zero or more `<record>` elements. Each record declares `start` and `end` character offsets, a `<path>`, and optional lifecycle relationships. `DOCTYPE` and `ENTITY` declarations are rejected before parsing.

See `src/sourcecontract/fixtures/data/xml-basic.xml` for a complete example.

## Invariants and rule IDs

| Rule | Invariant |
| --- | --- |
| `SC101` | Two identical calls produce equal, equally ordered results. |
| `SC102` | Stable identifiers and their order match the source expectation. |
| `SC103` | `exact_text` equals the authoritative fixture span. |
| `SC104` | Paths preserve order and local parent paths are strict prefixes. |
| `SC105` | Every `source_hash` hashes the exact payload bytes. |
| `SC106` | Retrieval and effective temporal fields are valid and preserved. |
| `SC107` | A result has no duplicate stable IDs or identical records. |
| `SC108` | Superseded records and tombstones carry explicit lifecycle data. |
| `SC109` | Incomplete transport or envelope data is rejected, not emitted. |
| `SC110` | Remaining canonical output matches the fixture expectation. |
| `SC111` | `ingest` returns the versioned `AdapterResult` type. |

## Library use

```python
from sourcecontract.adapters import JSONReferenceAdapter
from sourcecontract.runner import FixtureRunner

report = FixtureRunner().run(JSONReferenceAdapter())
print(report.passed, report.fixture_count)
for fixture in report.fixture_results:
    for issue in fixture.issues:
        print(issue.rule_id, issue.message)
```

`FixtureRepository(path)` loads a private repository that uses the same strict manifest structure. The `sourcecontract schema fixture` command prints its schema.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Validation passed, or an inspection command succeeded. |
| `1` | At least one conformance fixture failed. |
| `2` | Usage, adapter loading, fixture loading, contract-version, or output error. |
| `3` | Unexpected internal CLI failure. |

## Development checks

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests
```

`ci/check.sh` runs both required checks plus smoke validations of the two reference adapters. See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [docs/architecture.md](docs/architecture.md).

## License

Apache License 2.0. See [LICENSE](LICENSE).
