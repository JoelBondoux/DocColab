# Project Soul

> This file is the living identity of the project.

## Project Type
Unknown

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
- `develop` is the routine integration branch and `master` is the protected release-ready branch.
- See `decisions/development-guardrails.md`, `operations/security-and-safety.md`, and `architecture/runtime-and-surfaces.md` for supporting detail.

## Imported References
- architecture/project-overview.md
- architecture/runtime-and-surfaces.md
- architecture/model-routing.md
- architecture/agents-and-skills.md
- operations/development-workflow.md
- decisions/development-guardrails.md
- roadmap/improvement-plan.md