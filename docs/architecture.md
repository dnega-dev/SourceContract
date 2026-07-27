# Architecture

## Goals and boundaries

SourceContract is a local conformance harness for source-ingestion adapters. Its boundary begins with already-fetched bytes plus retrieval metadata and ends with a deterministic validation report. Fetching, authentication, source-authority selection, storage, scheduling, and downstream search/indexing are deliberately outside the MVP.

The runtime uses the Python 3.9 standard library only. Adapter code is trusted executable Python; payloads and fixture manifests are treated as untrusted data.

## Data flow

```text
fixture manifest ─┐
fixture payload ──┼─> FixtureRepository ─> FixtureRunner ─> ValidationReport ─> renderer
adapter target ───┘                         │
                                            ├─ contract validation
                                            ├─ two identical ingest calls
                                            ├─ invariant checks
                                            └─ expected-output comparison
```

1. `FixtureRepository` discovers `*.fixture.json` names in sorted order, parses strict manifests, constrains payload paths to the fixture repository, and constructs immutable `Fixture` objects.
2. `FixtureRunner` validates the adapter metadata and contract version before selecting only the adapter's fixture family.
3. Each successful fixture is ingested twice with the same immutable bytes and `AdapterContext`. Equality covers record order, fields, completeness, and warnings.
4. Local invariants inspect hashes, temporal context, duplicate identities, parent-path consistency, and lifecycle edges.
5. The runner compares the canonical result to the fixture's expected records. Expected failures compare stable error codes rather than prose.
6. Renderers consume a `ValidationReport` and do not rerun adapters or inspect ambient state.

There are no generated timestamps in reports. Fixture retrieval times are fixed data. Directory traversal and set-derived nondeterministic output are avoided or sorted.

## Contract versioning

The adapter contract has a separate version from the Python package. `contract_name` prevents accidental structural matches with an unrelated protocol. Versions are `MAJOR.MINOR`:

- Major mismatch means incompatible behavior.
- A newer adapter minor means the runner may not understand required additions and is rejected.
- An equal or older adapter minor within the current major can be accepted.

Version 1.0 requires:

```python
contract_name: str
contract_version: str
name: str
fixture_family: str
ingest(payload: bytes, context: AdapterContext) -> AdapterResult
```

`AdapterResult.records` is a tuple to make order explicit and discourage mutation after return. Structural metadata is validated before fixture execution; runtime return values are validated per call.

## Canonical model decisions

### Identity

`stable_id` is source identity, not a hash of mutable title or text. Tests therefore include duplicate titles and revisions. The allowed character set is intentionally conservative so IDs are portable in JSON, XML attributes, report locations, and logs.

### Source bytes and exact text

`source_hash` is SHA-256 over the complete original payload bytes, represented as `sha256:<lowercase hex>`. Parsing, Unicode normalization, newline conversion, and serialization must not occur before hashing.

`exact_text` is a character span from the source's decoded authoritative text. Reference envelopes carry explicit start/end indices and assert optional exact text. Unicode and whitespace fixtures catch normalization, trimming, and reflow.

These are distinct checks: the payload hash proves which byte sequence was processed; exact-span fidelity proves which source characters became a record.

### Time

`retrieved_at` belongs to `AdapterContext`; an adapter must not call the clock. It is parsed as an offset-aware ISO-8601 date-time and canonicalized to UTC. Effective bounds allow either dates or offset-aware date-times and enforce `from <= to` when both exist.

### Lifecycle

Records are `active`, `superseded`, or `tombstone`:

- A superseded record closes its effective range and points to a successor.
- A tombstone retains an identity event with empty text and points to what it replaces or supersedes.
- Records are never silently omitted merely because an upstream source removed their former text.

Relationship targets need not all be emitted in the same payload because official documents can reference records outside a selected page or response. Local targets receive additional hierarchy and lifecycle consistency checks.

### Completeness

Completeness is represented at two boundaries:

- `AdapterContext.complete` reflects transport-level knowledge.
- The built-in envelopes require their own `complete=true` assertion.

Either negative signal raises `PartialFetchError`. `AdapterResult.complete=False` is itself a validation failure; successful partial output is not an accepted state.

## Built-in adapters

### JSON

`JSONReferenceAdapter` requires UTF-8, an object root, a 1.0 envelope, exact known fields, Boolean completeness, one document string, and an array of record objects. It validates offsets before constructing strict model values.

### XML

`XMLReferenceAdapter` requires a namespace-free source envelope, one first `<document>`, known elements/attributes, and explicit record offsets. `DOCTYPE` and `ENTITY` tokens are rejected before ElementTree parsing. XML text uses XML-defined character/entity decoding, so fixture offsets refer to the decoded document text.

Both adapters calculate one digest over the original payload and copy retrieval context into every record.

## Fixture format

A fixture has stable metadata, a repository-relative payload, context, and exactly one expectation:

- `records`: canonical expected values, with payload hash and retrieval fields injected by the repository; or
- `error`: a stable `SourceContractError.code`.

Manifests remain human-reviewable and do not execute code. Private fixture repositories can be supplied without modifying the package.

## Invariant layering

Model constructors reject malformed individual values early. Runner checks then cover properties that require input bytes, context, multiple records, a second call, or fixture ground truth. This split keeps adapters from creating invalid canonical values while preserving actionable rule IDs for cross-record conformance failures.

Expected-output differences are assigned to the narrowest available rule (`SC102` identity, `SC103` text, `SC104` hierarchy, `SC105` hash, `SC106` time), with `SC110` for remaining expected fields. `SC111` reserves return-type violations.

## Reports and exit behavior

All renderers are pure deterministic transformations:

- Text is intended for terminals and logs.
- JSON is the complete machine-readable report.
- JUnit models each fixture as one test case.
- SARIF models each issue as one result and uses fixture URIs plus logical record locations.

The CLI separates conformance failure (`1`) from expected invocation/configuration failure (`2`) and an unexpected internal boundary failure (`3`). Library callers receive typed exceptions and report objects instead of process exits.

## Security considerations

Module imports execute trusted adapter code. SourceContract does not sandbox adapters. Fixture payload path traversal is rejected, but callers remain responsible for filesystem permissions and resource limits. No network request is made from `source_url`. See `SECURITY.md` for the reporting process and complete trust-boundary notes.
