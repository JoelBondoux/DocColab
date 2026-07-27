# Operations

## Continuous agent

`doccolab run` starts periodic Google/GitHub checks, Microsoft delta polling, and
the local webhook receiver. `doccolab-mcp serve` optionally supervises all enabled
project agents and hot-reloads registry files at the configured interval.

Use one running supervisor per state database. SQLite WAL supports crash-safe
checkpoints, but multiple independent publishers for one logical document would
create unnecessary conflicts.

## Health and status

```powershell
Invoke-RestMethod http://127.0.0.1:8765/healthz
doccolab --config config.json status
tailscale serve status
```

Logs go to stdout. MCP authorization attempts, denials, and final
success/failure outcomes go to `.doccolab/audit.jsonl`; error classes are stored,
not exception text that could contain secrets.

## Backup

Back up:

- GitHub repository and protected branches/tags;
- project config (without secrets);
- `.doccolab/state.db` while the process is stopped or through a SQLite-safe
  backup operation;
- Google/OneDrive originals through provider retention policies.

Do not back up OS-keyring exports into the repository.

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
- GitHub/AI keys: issue replacement, update `.env`, restart, revoke old key.
- Google/Microsoft OAuth: remove the keyring entry, revoke provider consent, and
  run the corresponding authorization command again.
- Offboarding: remove project membership, remove/disable the user, revoke Tailnet
  access, review audit logs, and rotate exposed shared credentials.
