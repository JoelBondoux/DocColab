# Contributing to DocColab

Thank you for helping build DocColab.

## Ways to contribute

- Describe document collaboration use cases and constraints.
- Propose a canonical, Git-friendly document representation.
- Explore Microsoft Graph and Google Workspace integration approaches.
- Prototype import, export, diff, merge, or preview capabilities.
- Improve documentation, tests, accessibility, and security.

## Workflow

1. Open an issue for substantial changes so the approach can be discussed.
2. Create a short-lived, focused branch from the latest `main`.
3. Add a failing test first, implement the smallest fix, then refactor with the
   suite green.
4. Open a pull request targeting `main` and explain the change, its motivation,
   and any trade-offs.

Please keep pull requests focused and do not commit credentials, access tokens,
private documents, or exported user data. Complete the repository pull request
template with the checks actually run; explain any unchecked item rather than
marking it complete without evidence.

Before opening a pull request, run:

```powershell
ruff check agent tests
mypy agent
pytest
pip-audit --cache-dir .doccolab/pip-audit-cache
bandit -c pyproject.toml -r agent
```

`pyproject.toml` supplies the branch-coverage configuration and 60% floor. Before
publishing project-memory changes, also review the diff for credentials, personal
contact handles, private document content, raw transcripts, and tool telemetry.
