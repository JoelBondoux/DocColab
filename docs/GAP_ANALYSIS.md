# Project-wide gap analysis and remediation

Date: 2026-07-27

## Outcome

The repository-wide architecture, security, functionality, memory/SSOT, code
structure, testing, delivery, and documentation findings were rechecked and the
highest-risk implementation gaps were closed. DocColab is now a production
candidate with explicit deployment prerequisites, not a claim that every
operator-specific control is automatically provisioned.

## Resolved findings

- Safe defaults now keep Google, Microsoft, and AI integrations off until
  explicitly configured. Known broad consent requires acknowledgement.
- Google is read-only by default. Its full-document write path requires a second
  acknowledgement of the documented non-atomic race; a version preflight remains
  defense in depth.
- The public webhook no longer exposes project status, and registry project IDs
  are validated before filesystem path construction.
- Audit records cover authorization, denial, success, and failure without storing
  exception text or secrets.
- MCP file operations and provider events use explicit service seams; setup input
  handling is separated from configuration generation.
- CLI failures use concise messages and stable exit codes.
- Raw session transcripts, tool telemetry, run payloads, and contact handles are
  excluded from tracked project memory. Durable decisions and lessons remain.
- `pyproject.toml` is the only pytest/coverage configuration source. Branch
  coverage is visible locally and in CI, with an enforced 60% floor.
- Focused tests cover webhook verification, provider deltas/ETags, runtime cache,
  safety defaults, CLI errors, audit outcomes, and read-only live-provider smoke
  fixtures.
- A tag-gated build, metadata check, wheel smoke test, artifact, and PyPI trusted
  publishing workflow is configured. Release tags must be on `main`, pass the
  reusable quality workflow, generate an SBOM, and receive provenance attestation.
- Transient provider failures use bounded retry/backoff with throttling support.
  One state database is guarded by an exclusive process lock, and shutdown drains
  in-flight work.
- Liveness and readiness are distinct. Online SQLite backups are integrity
  checked, state events have configurable retention, and audit logs rotate.
- Guided setup stores API tokens in the OS keyring. Environment variables remain
  an explicit unattended-service fallback.
- CI runs every branch from `uv.lock`, and third-party Actions are pinned to
  immutable revisions.
- Setup, security, architecture, MCP, operations, testing, contribution, release,
  and memory guidance now describe the implemented behavior.

## Final verification

The current local run collected 61 tests: 58 passed, and the three read-only live
provider checks skipped because no private fixture configuration was supplied.
Branch coverage remained above the enforced 60% floor. Ruff and mypy passed.

The authoritative repository quality suite is:

```text
ruff check agent tests
mypy agent
pytest
bandit -c pyproject.toml -r agent
python -m build
python -m twine check dist/*
```

The release workflow and external PyPI trusted-publisher registration still
require a real release rehearsal. Provider smoke checks still require private
disposable fixtures. Storage encryption, service-account isolation, backup
retention, alert routing, and recovery objectives remain deployment controls and
are documented rather than silently assumed.

Read-only cloud compatibility remains intentionally opt-in:

```text
pytest -m live tests/test_live_provider_smoke.py
```

Its credentials and disposable provider fixtures are never stored in CI or the
repository.
