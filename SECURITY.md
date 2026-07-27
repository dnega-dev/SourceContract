# Security policy

## Supported versions

This repository currently contains the initial `0.1.x` release line. Security fixes are made on the current development line; no older release line is designated as supported yet.

## Reporting a vulnerability

Do not include credentials, private source documents, personal data, or exploit payloads in a public issue. Contact the repository maintainers through the private security-reporting channel configured by the repository host. Include:

- the affected SourceContract version and Python version;
- the smallest safe reproducer;
- the expected and observed behavior;
- the security impact and required preconditions; and
- whether the report may be acknowledged publicly after a fix.

If no private channel is configured, contact a maintainer directly before sharing sensitive details. Maintainers should acknowledge receipt, assess impact, coordinate remediation, and credit reporters according to their preference. This file does not promise a fixed response or remediation deadline.

## Security boundaries

SourceContract processes adapter code and fixture files supplied by its caller.

- **Adapters are trusted Python code.** Loading `module:attribute` imports and may instantiate arbitrary caller code. Run untrusted adapters in an operating-system sandbox with suitable filesystem, network, process, and resource restrictions.
- **Fixtures are data, not code.** Fixture paths are constrained to their repository. JSON parsing is strict. XML `DOCTYPE` and `ENTITY` declarations are rejected, and the standard-library ElementTree parser is used.
- **No fetching occurs.** `source_url` is provenance metadata; SourceContract does not make network requests.
- **No credential handling occurs.** Do not embed secrets in fixture payloads, URLs, reports, or adapter metadata.
- **Resource limits are external.** This MVP does not enforce payload-size, CPU, or memory quotas. Apply limits before invoking it on untrusted or unusually large data.
- **Reports can contain source text or identifiers.** Treat report destinations according to the sensitivity of the underlying fixture and adapter output.

A validation pass indicates agreement with the tested contract and fixtures. It is not a security audit and is not a legal or regulatory certification.
