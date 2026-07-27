# Project Soul

> This file is the living identity of the project.

## Project Type
Python application and MCP service

## Vision
DocColab is an open project exploring a Git-native collaboration method for
people and AI agents working together on Microsoft Office and Google Workspace
documents.

## Principles
- Default to the safest reasonable behavior.
- Keep project knowledge structured, current, and reviewable.
- Prefer explicit approvals and traceable automation for risky work.
- Treat documentation, versioning, and release hygiene as part of correctness.

## Key Decisions
- Safety and security regressions are correctness bugs, not polish work.
- Long-term project context belongs in the SSOT under `project_memory/`.
- Provider credentials live in SecretStorage, not in project memory or source.
- `develop` is the routine integration branch and `main` is the protected release-ready branch.
- `docs/ARCHITECTURE.md`, `SECURITY.md`, and `docs/OPERATIONS.md` are the
  implementation, security, and operational sources of truth.

## Imported References
- ../README.md
- ../docs/ARCHITECTURE.md
- ../docs/OPERATIONS.md
- ../docs/TESTING.md
- ../SECURITY.md
- ../CONTRIBUTING.md
