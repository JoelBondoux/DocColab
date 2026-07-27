# Changelog

All notable changes to DocColab are documented here.

## Unreleased

- Make cloud providers and AI opt-in, require explicit acknowledgement for broad
  provider consent, default Google to read-only, and gate its non-atomic
  full-document replacement behind a separate acknowledgement.
- Remove unauthenticated webhook status, validate project IDs before registry
  path construction, and record authorization denials plus final tool outcomes.
- Add stable CLI exit codes and concise configuration, access, and provider
  failure messages.
- Extract public file, provider-event, and setup-input seams from orchestration
  hotspots.
- Consolidate pytest and branch coverage in `pyproject.toml`, raise the floor to
  60%, and add provider, webhook, Microsoft, runtime, CLI, safety, and audit tests
  plus opt-in read-only live smoke tests.
- Add PyPI trusted-publishing release automation and align security, setup,
  operations, testing, architecture, and project-memory documentation.

## 0.1.0 — 2026-07-26

- Add the Python document synchronization agent for Google Docs, OneDrive,
  GitHub, OpenAI, and Anthropic.
- Add DOCX ↔ Markdown conversion with Pandoc and pure-Python paths.
- Add crash-resumable multi-surface synchronization and safe conflict pull
  requests.
- Add an authenticated, multi-user, multi-project MCP server with 25 tools,
  folder isolation, roles, auditing, and hot reload.
- Add Tailscale private-access guidance and loopback/DNS-rebinding protections.
- Add a guided cross-platform setup wizard and a one-command PowerShell launcher
  with validated configuration generation and no-overwrite protection.
- Add config, credential, OAuth, API, architecture, operations, testing, and
  troubleshooting documentation.
- Adopt the `CLAUDE.md` TDD, unit, continuous/shift-left, and security testing
  procedures.
- Add multi-version CI, coverage, Ruff, mypy, Bandit, pip-audit, CodeQL,
  dependency review, and Dependabot coverage.
