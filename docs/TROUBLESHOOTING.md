# Troubleshooting

## `No enabled global owner exists`

Run:

```powershell
doccolab-mcp --config mcp-config.json init-owner --user-id owner@example.com
```

Store the returned bearer token immediately.

## MCP returns 401

Confirm the client sends `Authorization: Bearer <token>`, the user is enabled, and
the token was not rotated. Tokens cannot be recovered because only their digest
is stored.

## MCP returns 421 / invalid Host

Add the exact MagicDNS hostname to `allowed_hosts` and its HTTPS origin to
`allowed_origins`. Keep DNS-rebinding protection enabled and restart the service.

## File is denied even though it exists

The path must be project-relative and inside an exposed folder after symlinks are
resolved. Check `root_path`, `allowed_project_roots`, project membership,
`exposed_folders`, and the project’s tool allowlist.

## Google authorization or export fails

Verify both Drive and Docs APIs are enabled, the OAuth client is a Desktop app,
your account is an allowed test user, and the file is accessible to that account.
Remove the stale keyring credential and re-run `auth-google` after scope changes.

## Google webhook never arrives

A Tailscale-only endpoint is private and cannot receive Google callbacks. Use
polling, or configure a separately secured public HTTPS relay and renew the watch.
Drive notification channels expire and must be renewed.

## Microsoft device login or file update fails

Verify public client flow, delegated Graph permissions, tenant setting, and
consent. HTTP 412 means the OneDrive ETag changed; DocColab preserves the
concurrent version and routes it through conflict handling.

## GitHub commit is rejected

Check PAT repository restriction and Contents permission. A blob-SHA mismatch
means the branch changed since it was read; run another sync so the three-way
merge can include the new version. Check branch protection if tag/ref creation is
denied.

## Pandoc not found

Either install Pandoc and keep `prefer_pandoc: true`, or set it false to use the
pure-Python converter. The fallback preserves common formatting but may not retain
complex Word layout, tracked changes, fields, drawings, or macros.

## AI response is empty or malformed

Check the selected provider key/model and outbound connectivity. Reduce document
size or output limit if the provider rejects it. DocColab validates non-empty
Markdown and does not publish a failed rewrite.

## Sync repeats after a crash

This is expected if a multi-surface publish was interrupted. The SQLite pending
record lets DocColab retry unfinished surfaces. If GitHub or a cloud version
changed meanwhile, it creates a conflict branch instead of overwriting.

## Database is locked

Stop duplicate agents using the same `.doccolab/state.db`. Do not place the
database on an unreliable network filesystem. WAL sidecar files are normal while
the process runs.
