# Security Policy

## Reporting

Do not disclose suspected vulnerabilities in public issues. Use GitHub private
vulnerability reporting for this repository, or contact the repository owner
privately through their GitHub profile. Include the affected version, component,
reproduction steps, impact, and suggested mitigation.

## Security model

- The MCP and webhook listeners bind to `127.0.0.1` by default.
- Tailscale Serve provides private HTTPS; no router port forwarding is needed.
- MCP calls require a high-entropy bearer token. Only its SHA-256 digest is stored.
- Global roles and project membership are checked for every tool invocation.
- File access is restricted to configured project roots and exposed folders.
  Resolved paths are checked after symlink resolution.
- Provider credentials are loaded from environment variables or the operating
  system keyring. They must never be stored in project JSON or source control.
- Provider integrations and AI are disabled by default. Enabling known broad
  Google or Microsoft consent requires an explicit configuration acknowledgement.
- Google cloud writes remain read-only unless the operator separately acknowledges
  that the full-document replacement has a version preflight but is not atomic.
- Human document content is sent to an AI provider only after AI and automatic
  rewriting are explicitly enabled.
- Project/user configuration writes are atomic. The final enabled
  owner cannot be removed or demoted.
- Size limits, strict configuration schemas, optimistic GitHub blob checks,
  OneDrive ETags, and three-way merge checks reduce unsafe overwrite risk.
- MCP DNS-rebinding protection remains enabled. Add only the exact MagicDNS
  hostname used by your Tailnet to `allowed_hosts` and `allowed_origins`.
- The public webhook app exposes only `/healthz` and the token-verified Google
  callback; project status remains behind the authenticated CLI/MCP boundary.
- Audit events record authorization attempts, denials, and final success/failure
  without secrets. Tracked project memory excludes raw transcripts, contact
  handles, provider payloads, and tool telemetry.

Tailscale network access is an additional boundary, not a substitute for DocColab
authentication. Rotate a bearer token immediately if it is exposed.

## Automated checks

Every pull request runs unit/integration tests, branch coverage, Ruff, mypy,
Bandit, pip-audit, dependency review, and CodeQL. Dependabot covers both pip and
GitHub Actions dependencies. Security regressions are correctness bugs.

## Supported versions

Until a 1.0 release, security fixes are applied to the latest `main` branch.
