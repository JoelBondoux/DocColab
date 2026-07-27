# Project-wide gap analysis and remediation

Date: 2026-07-27

## Outcome

The repository-wide architecture, security, functionality, UI/UX, memory/SSOT,
code structure, testing, delivery, and documentation findings were investigated
and remediated. The preliminary signals understated the implemented feature set
and test inventory, but correctly identified integration seams, test visibility,
and operator-polish work worth completing.

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
  publishing workflow is configured. External publisher/environment registration
  is an operator-controlled activation step.
- Setup, security, architecture, MCP, operations, testing, contribution, release,
  and memory guidance now describe the implemented behavior.

## Final verification

The final local run collected 49 tests: 46 passed, and the three read-only live
provider checks skipped because no private fixture configuration was supplied.
Branch coverage was 65.04% against the 60% floor. Ruff, mypy, Bandit, the
wheel/sdist build, and Twine metadata checks all passed.

The authoritative repository quality suite is:

```text
ruff check agent tests
mypy agent
pytest
bandit -c pyproject.toml -r agent
python -m build
python -m twine check dist/*
```

The local `pip-audit` process could not validate the machine's TLS chain for
PyPI, so no local vulnerability result is claimed. CI runs the same audit in a
clean GitHub-hosted environment and treats failure as blocking; TLS verification
was not bypassed.

Read-only cloud compatibility remains intentionally opt-in:

```text
pytest -m live tests/test_live_provider_smoke.py
```

Its credentials and disposable provider fixtures are never stored in CI or the
repository.
