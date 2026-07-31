# Production deployment

DocColab is designed as a single-host, single-writer service behind a private
network boundary. Run it under an operating-system service manager, using a
dedicated unprivileged account and an encrypted local volume.

## Service contract

The service manager should:

- run `doccolab-mcp --config <absolute-path> serve` from the project root;
- restart on non-zero exit with a bounded delay;
- allow at least 120 seconds for graceful shutdown;
- capture stdout/stderr in the host logging system;
- inject unattended secrets through a protected environment file or service
  secret facility when the account has no interactive OS keyring;
- probe `/healthz` for liveness and `/readyz` for traffic readiness;
- alert on repeated restarts, readiness 503, backup verification failures, and
  audit-log write failures.

Do not run a separate `doccolab run` process when `run_sync_agents` is true in
the MCP configuration. The MCP supervisor already owns those project agents.

## Filesystem layout

Use absolute, operator-owned locations in production:

```text
configuration   /etc/doccolab or C:\ProgramData\DocColab\config
project data    encrypted project volume
state/audit     encrypted local application-data volume
backups         separate encrypted backup target
```

Grant the service account read access to configuration and OAuth client files,
read/write access only to configured project roots and `.doccolab`, and no
interactive administrator privileges. Never place the state database on a
network filesystem or a directory concurrently synchronized by a desktop cloud
client.

## Deployment sequence

1. Install from a pinned wheel or locked source checkout.
2. Provision configuration and secrets as the service account.
3. Run `doccolab-mcp --config <path> validate`.
4. Start with cloud writes and automatic AI rewriting disabled.
5. Confirm liveness, readiness, logs, audit rotation, and an online backup.
6. Run the opt-in read-only live-provider smoke tests against disposable files.
7. Enable one write surface at a time and retain provider revision history.
8. Record the deployed version, config checksum, recovery objectives, and rollback
   artifact.

Rollback uses the previous tested wheel/config and the most recent verified state
backup. Reconcile provider versions in read-only mode before re-enabling writes;
never assume state rollback also rolled back GitHub, Google Drive, or OneDrive.
