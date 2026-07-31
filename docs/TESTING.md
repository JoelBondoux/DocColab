# Testing

DocColab follows the testing protocols in `CLAUDE.md`: TDD, unit testing,
continuous/shift-left testing, and security testing.

## Local checks

```powershell
uv lock --check
uv sync --locked --extra dev
.\.venv\Scripts\ruff.exe check agent tests
.\.venv\Scripts\mypy.exe agent
.\.venv\Scripts\pytest.exe
.\.venv\Scripts\pip-audit.exe --cache-dir .doccolab\pip-audit-cache
.\.venv\Scripts\bandit.exe -c pyproject.toml -r agent
```

`pyproject.toml` is the single pytest/coverage source of truth. A normal `pytest`
run enables branch coverage, prints missing lines, and enforces the 60% floor.

Unit tests isolate conversion, three-way merge, path containment, ACLs, token
hashing, API request shapes, state transitions, registry invariants, webhook
verification, Microsoft ETag/delta behavior, runtime caching, CLI exit semantics,
safe defaults, retry/backoff, instance locking, online backup/integrity, graceful
draining, readiness, keyring fallback, audit outcomes, and audit retention.
Integration-style tests exercise the MCP HTTP initialize handshake and a complete
Google → GitHub human commit → AI commit → cloud update transaction with fakes.

Provider live tests are opt-in and read-only because CI must not hold user
documents or long-lived OAuth secrets. Point `DOCCOLAB_LIVE_CONFIG` at a private
configuration containing disposable fixtures, then run:

```powershell
$env:DOCCOLAB_LIVE_CONFIG = 'C:\private\doccolab-live\config.json'
.\.venv\Scripts\pytest.exe -m live tests\test_live_provider_smoke.py
```

## CI

Every branch push and every pull request targeting `main` runs from the committed
`uv.lock` without re-resolving dependencies:

- Ruff and strict mypy;
- pytest on Python 3.11, 3.13, and 3.14;
- branch coverage with a 60% repository floor and uploaded XML report;
- pip-audit and Bandit.

Dependency review runs on pull requests. CodeQL runs on changes and weekly.
Dependabot checks Python and GitHub Actions weekly. Third-party Actions are pinned
to immutable commits.

Release tags cannot bypass CI. A release is accepted only when the tagged commit
is on `main`, the tag matches the project version, all package modules import from
the built wheel, metadata checks pass, and the protected `pypi` environment
approves publication. The workflow emits package provenance and a CycloneDX SBOM.

## TDD contribution loop

1. Express the behavior or regression as a failing test.
2. Make the smallest implementation change that passes it.
3. Refactor while keeping unit, type, lint, and security checks green.
4. Record the exact checks and assertions in the pull request.
