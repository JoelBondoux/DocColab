# Project-wide gap analysis

Date: 2026-07-27

## Outcome

The failed automated run was not a reliable assessment: six subtasks either
reported unavailable tools or stopped at an iteration cap, and synthesis never
ran. Direct inspection and validation overturn several of its preliminary
signals. DocColab has implemented Google Docs, OneDrive, GitHub, AI, conversion,
conflict, state, webhook, and MCP paths; it is not merely a scaffold.

Recovery work also fixed two security defects and the broken test introduced by
the failed run:

1. A project membership can no longer elevate a non-owner above their global
   role.
2. Resolved paths must remain below the canonical project root, including through
   symlinks or Windows junctions.
3. The CI signal test now checks the repository's actual Ruff, mypy, pytest,
   coverage, Bandit, and pip-audit commands instead of a nonexistent Hatch task.
4. CODEOWNERS, pull-request guidance, MCP role documentation, and project-memory
   branch/source references are aligned with the repository.

## Evidence by area

| Area | Evidence and assessment |
| --- | --- |
| Architecture | Provider, conversion, sync, state, MCP, and webhook boundaries are visible and documented. `MCPService` still reaches into private `SyncManager` methods, and the two orchestration classes are large integration hotspots. |
| Safety/security | Bearer authentication, role/project/tool controls, canonical path checks, size limits, token hashing, atomic writes, optimistic concurrency, Bandit, CodeQL, dependency review, and Dependabot are present. Bandit found no issues. Local pip-audit could not reach PyPI because the machine's CA chain rejected the certificate; CI still runs the audit. |
| Functionality/features | The intended provider and synchronization paths are implemented and fake-backed integration tests exercise the Google → GitHub → AI → Google transaction. Live provider smoke tests are intentionally excluded, leaving real OAuth/API compatibility operator-verified. |
| UI/UX | This is a CLI/MCP service rather than a graphical product. The guided setup has defaults, validation, cancellation, no-overwrite behavior, prerequisite checks, and follow-up commands. Operational CLIs still rely on raw exception output for several configuration/provider failures. |
| Memory/SSOT | Project soul, testing, delivery, privacy, risk, documents, and project-director records exist. Incorrect `master` references, nonexistent imported references, the owner handle, and an inaccurately active PyPI stage were corrected. |
| Code structure | Package boundaries are coherent and strict configuration models are centralized. `setup_wizard.py`, `sync_manager.py`, and `mcp_server/service.py` remain the main candidates for smaller orchestration units and public integration interfaces. |
| Testing | 30 tests pass with branch coverage enabled. Coverage is surfaced in the terminal, emitted as XML, uploaded by CI, and enforced at 50%; the observed total was 58.87%. Microsoft, webhook, supervisor/runtime-cache, CLI execution, and many MCP service branches remain comparatively thin. |
| Delivery | CI runs on Python 3.11, 3.13, and 3.14; separate CodeQL and dependency-review workflows and Dependabot are configured. PyPI publishing is now explicitly recorded as planned because no trusted-publishing release workflow exists. |
| Documentation | Architecture, setup, MCP, operations, provider examples, testing, troubleshooting, Tailscale, contribution, and security guidance are present. A PR template now turns contribution guidance into a repeatable review checklist. |

## Preliminary signal disposition

| Preliminary signal | Result |
| --- | --- |
| Core functionality is largely incomplete | Overturned: core paths exist; live-provider verification and broader branch coverage remain. |
| Architecture seams need review | Confirmed at P2, especially private cross-layer calls and large orchestration modules. |
| Code structure needs tightening | Confirmed at P2 for the orchestration hotspots, not the overall package layout. |
| Coverage is not surfaced | Overturned: terminal/XML reports, artifact upload, and a CI floor are configured. |
| Pull-request guidance is missing | Partly overturned: `CONTRIBUTING.md` already had guidance; a PR template was added. |
| UI/UX needs review | Confirmed at P3 for CLI failure presentation; no graphical UI is part of the stated architecture. |
| Only two test files exist | Overturned: the suite contains 15 focused test modules after replacing the placeholder test. |
| Three delivery workflows exist | Confirmed: CI, CodeQL, and dependency review are configured. |
| Security policy exists | Confirmed. |
| Memory/SSOT coverage is strong | Confirmed with corrected drift; several memory categories remain intentionally empty. |

## Outstanding checklist

### P1

No unresolved P1 finding was reproduced after the authorization and path-boundary
fixes above.

### P2

- [ ] [P2] [architecture] [concern] Replace `MCPService` calls to private `SyncManager` methods with explicit public provider/synchronization interfaces, then split the two orchestration hotspots along those seams.
- [ ] [P2] [security] [concern] Extend audit events to record denied authorization attempts and final success/failure outcomes, not only authorization-time invocations.
- [ ] [P2] [functionality] [gap] Add opt-in live smoke tests for disposable Google, Microsoft, and GitHub fixtures so provider API and OAuth compatibility can be verified before releases.
- [ ] [P2] [testing] [concern] Raise coverage around Microsoft delta/ETag handling, webhooks, crash-resume conflicts, runtime supervision, and mutating MCP tools before increasing the 50% repository floor.
- [ ] [P2] [delivery] [gap] Configure PyPI trusted publishing and a release workflow before treating the planned production stage as active.

### P3

- [ ] [P3] [ui-ux] [concern] Convert common configuration, credential, network, and provider failures into concise CLI messages with remediation hints and stable exit codes.
- [ ] [P3] [architecture] [praise] Provider, sync, state, conversion, webhook, and MCP responsibilities are already separated into recognizable packages with documented trust boundaries.
- [ ] [P3] [security] [praise] The project combines a visible security policy with bearer authentication, layered authorization, concurrency safeguards, static analysis, dependency review, and regression tests.
- [ ] [P3] [testing] [praise] The test suite, branch-coverage output, XML artifact, multi-version CI matrix, and security jobs provide a credible automated baseline.
- [ ] [P3] [delivery] [praise] CI, CodeQL, dependency review, Dependabot, release hygiene documentation, and a valid CODEOWNERS file support disciplined review and maintenance.
- [ ] [P3] [documentation] [praise] Setup, architecture, MCP, operations, testing, troubleshooting, security, and contribution guidance are comprehensive and now include a pull-request checklist.
- [ ] [P3] [memory] [praise] The tracked project-memory mirrors cover identity, testing, delivery, privacy, risks, documents, and ownership and now agree on `develop`/`main`.
