# Contributing

SourceContract changes should preserve deterministic behavior, strict input handling, and Python 3.9 compatibility. Runtime code must use only the Python standard library.

## Local setup

From the repository root, either install the package locally or point Python at `src`:

```sh
python3 -m pip install -e .
# or for commands that do not require installation:
export PYTHONPATH="$PWD/src"
```

## Required checks

Run these exact commands before proposing a change:

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests
```

The convenience script also validates the built-in adapters:

```sh
./ci/check.sh
```

Tests must use `unittest` and the standard library only. A defect fix should include a regression test. Keep tests deterministic: do not use the network, ambient current time, random values without a fixed seed, or ordering that depends on sets or filesystem enumeration.

## Contract changes

1. Describe the semantic behavior and migration impact.
2. Add or update schemas, fixtures, invariant checks, reports, tests, examples, and architecture notes together.
3. Increment the contract minor version for backward-compatible additions.
4. Increment the contract major version for incompatible changes.
5. Do not silently reinterpret existing fields or fixture expectations.

Fixture manifests are strict and payload-relative. New fixture IDs must be unique, descriptive, and stable. Add adversarial data that isolates one or more documented invariants; do not use real confidential source material.

## Code style

- Prefer small typed value objects and pure deterministic functions.
- Raise a `SourceContractError` subclass for expected user/input failures.
- Keep stable machine-readable error and rule IDs separate from prose.
- Reject unknown fields where silent acceptance could hide source drift.
- Read complete bytes before hashing; do not hash normalized or parsed content.
- Avoid claims not demonstrated by tests or documented constraints.

## Documentation and changelog

Update `README.md` for user-visible behavior, `docs/architecture.md` for design changes, and `CHANGELOG.md` for release-facing changes. Keep examples executable and avoid placeholder implementations.

By contributing, you agree that your contribution is licensed under Apache License 2.0.
