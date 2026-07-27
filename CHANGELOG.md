# Changelog

All notable changes to this project are documented here. The format follows the categories in Keep a Changelog, and releases use semantic versioning independently from the adapter contract version.

## [Unreleased]

No unreleased changes yet.

## [0.1.0] - Initial MVP

### Added

- Versioned `sourcecontract.adapter` 1.0 protocol and compatibility checks.
- Immutable canonical `SourceRecord`, `Relationship`, `AdapterContext`, and `AdapterResult` values.
- Deterministic fixture repository and runner with 20 packaged adversarial JSON/XML fixtures.
- Invariants for determinism, stable identity, exact spans, hierarchy, payload hashes, temporal fields, duplicates, lifecycle records, and partial-fetch rejection.
- Strict standard-library JSON and XML reference adapters.
- Text, JSON, JUnit XML, and SARIF 2.1.0 renderers.
- `validate`, `fixtures list`, and `schema` CLI commands with documented exit codes.
- Standard-library `unittest` suite, examples, architecture documentation, and CI check script.
