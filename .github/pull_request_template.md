## Summary

Describe the change and why it is needed.

## Validation

List the checks you ran and their results.

- [ ] `ruff check agent tests`
- [ ] `mypy agent`
- [ ] `pytest --cov=agent --cov-branch --cov-fail-under=50`
- [ ] `bandit -c pyproject.toml -r agent`
- [ ] `pip-audit --cache-dir .doccolab/pip-audit-cache` (or explain why unavailable)

## Safety and compatibility

- [ ] I added or updated tests for behavior changes.
- [ ] I did not commit credentials, tokens, private documents, or exported user data.
- [ ] I documented configuration, security, or operator-facing changes.
- [ ] I considered rollback and compatibility for persisted state and public interfaces.
