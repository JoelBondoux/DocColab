# Operations

## Continuous agent

`doccolab run` starts periodic Google/GitHub checks, Microsoft delta polling, and
the local webhook receiver. `doccolab-mcp serve` optionally supervises all enabled
project agents and hot-reloads registry files at the configured interval.

Use one running supervisor per state database. DocColab acquires an advisory
`<state.db>.lock` file and refuses a second runtime for the same state database.
SQLite WAL still provides crash-safe checkpoints, while the lock prevents
multiple independent publishers for one logical document.

Shutdown signals stop new polling work and let in-flight sync operations drain
before provider clients, state, and the instance lock are closed. A process
supervisor should allow at least 120 seconds before forcing termination.

## Health and status

```powershell
Invoke-RestMethod http://127.0.0.1:8765/healthz
Invoke-RestMethod http://127.0.0.1:8765/readyz
doccolab --config config.json status
tailscale serve status
```

`/healthz` reports that HTTP is alive. `/readyz` returns HTTP 200 only when all
enabled project agents are running; it returns 503 for missing or failed agents.
The public response contains counts, not project identifiers.

Logs go to stdout. MCP authorization attempts, denials, and final
success/failure outcomes go to `.doccolab/audit.jsonl`; error classes are stored,
not exception text that could contain secrets. `audit_max_bytes` and
`audit_backup_count` bound local audit retention.

Provider clients retry throttling and transient HTTP failures on idempotent
requests with bounded exponential backoff and jitter. Non-idempotent creates are
not replayed automatically. A valid `Retry-After` response overrides the
calculated delay. Persistent failures remain visible in logs and readiness rather
than retrying without limit.

## Backup

Create and verify a transactionally consistent state backup while the service is
running:

```powershell
doccolab --config config.json backup-state --output D:\Backups\state-2026-07-27.db
doccolab --config config.json verify-state-backup --input D:\Backups\state-2026-07-27.db
```

The output path must not already exist. Also back up:

- GitHub repository and protected branches/tags;
- project config (without secrets);
- Google/OneDrive originals through provider retention policies.

Encrypt backup media. Do not back up OS-keyring exports into the repository.
Restore drills should use an isolated project copy: stop its service, preserve
the current database, place the verified backup at the configured
`state_database` path, start once in read-only provider mode, and inspect
`doccolab status` before enabling writes.

Set deployment-specific recovery objectives. A practical starting template is:

- RPO: backup interval plus the maximum acceptable uncommitted provider window;
- RTO: time to provision the service account, restore configuration/state, and
  complete a read-only reconciliation;
- retention: enough verified generations to survive delayed corruption or an
  accidental provider write.

State event rows older than `agent.event_retention_days` are pruned during
runtime construction. This bounds local event history; it does not delete Git
history or provider revisions.

## Branches, tags, and release hygiene

- Develop changes on `develop`.
- Require CI and review before merging release-ready changes to `main`.
- Protect both branches against force pushes.
- Document sync conflicts use generated `conflicts/...` branches.
- Successful document versions use `doc/<id>/v<major>.<minor>.<sequence>`.
- Dependabot groups Python and Actions updates into weekly pull requests.
- A `v<project-version>` tag builds and checks wheel/sdist artifacts, smoke-tests
  the wheel, and publishes through the protected `pypi` GitHub environment using
  PyPI trusted publishing.

Before the first release, configure the repository/environment as a PyPI trusted
publisher and require human approval on the `pypi` environment. The workflow
contains no long-lived PyPI API token. A tag whose version does not match
`pyproject.toml` fails before publication.

## Conflict response

When DocColab reports `conflict`:

1. Open the generated GitHub pull request.
2. Resolve Markdown conflict markers using the human and provider versions.
3. Run conversion tests or preview the regenerated DOCX.
4. Merge the PR into the configured branch.
5. Run one sync pass. DocColab will regenerate both cloud surfaces.

No cloud surface is overwritten while an unresolved merge is preserved.

## Credential rotation

- MCP token: use `doccolab-mcp rotate-token`.
- GitHub/AI keys: issue replacement, run `doccolab set-secret --name <NAME>`,
  restart, verify read-only access, and revoke the old key.
- Google/Microsoft OAuth: remove the keyring entry, revoke provider consent, and
  run the corresponding authorization command again.
- Offboarding: remove project membership, remove/disable the user, revoke Tailnet
  access, review audit logs, and rotate exposed shared credentials.
