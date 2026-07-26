# Testing

DocColab follows the testing protocols in `CLAUDE.md`: TDD, unit testing,
continuous/shift-left testing, and security testing.

## Local checks

```powershell
.\.venv\Scripts\ruff.exe check agent tests
.\.venv\Scripts\mypy.exe agent
.\.venv\Scripts\pytest.exe --cov=agent --cov-branch --cov-report=term-missing --cov-fail-under=50
.\.venv\Scripts\pip-audit.exe --cache-dir .doccolab\pip-audit-cache
.\.venv\Scripts\bandit.exe -c pyproject.toml -r agent
```

Unit tests isolate conversion, three-way merge, path containment, ACLs, token
hashing, API request shapes, state transitions, and registry invariants.
Integration-style tests exercise the MCP HTTP initialize handshake and a complete
Google → GitHub human commit → AI commit → cloud update transaction with fakes.

Provider live tests are intentionally not part of CI because they would require
user documents and secrets. Run initial live tests against non-sensitive document
copies in a dedicated repository.

## CI

Every push and pull request to `develop` or `main` runs:

- Ruff and strict mypy;
- pytest on Python 3.11, 3.13, and 3.14;
- branch coverage with a 50% repository floor;
- pip-audit and Bandit.

Dependency review runs on pull requests. CodeQL runs on changes and weekly.
Dependabot checks Python and GitHub Actions weekly.

## TDD contribution loop

1. Express the behavior or regression as a failing test.
2. Make the smallest implementation change that passes it.
3. Refactor while keeping unit, type, lint, and security checks green.
4. Record the exact checks and assertions in the pull request.
