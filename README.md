# DocColab

DocColab is an open-source, Git-native document collaboration system. People keep
editing in Google Docs and Word Online; AI agents work through an authenticated MCP
server; GitHub stores canonical Markdown, diffs, branches, tags, and conflict pull
requests.

The Python implementation includes Google Drive/Docs, Microsoft Graph/OneDrive,
GitHub, OpenAI, Anthropic, DOCX ↔ Markdown conversion, continuous synchronization,
multi-project access control, and private remote access through Tailscale.

## What works

- Google Docs and OneDrive change detection using metadata polling, Drive webhooks,
  and Microsoft Graph delta links.
- Deterministic import to Markdown, AI rewriting, DOCX regeneration, and same-file
  replacement so cloud revision/version history is retained.
- Three-way Markdown merging; unresolved concurrent edits are preserved on a
  `conflicts/<document>/<timestamp>` branch and opened as a pull request.
- Resumable multi-surface writes recorded in SQLite before cloud updates.
- An MCP Streamable HTTP server with 25 tools, generated JSON schemas, roles,
  project membership, folder allowlists, audit logging, and live config reload.
- Loopback-only service exposure through Tailscale Serve.
- Dependabot for Python and GitHub Actions, CI on Python 3.11/3.13/3.14, Ruff,
  mypy, pytest branch coverage, pip-audit, Bandit, dependency review, and CodeQL.

## Architecture

```text
 Google Docs ──┐                              ┌── OpenAI
               │                             │
 Word Online ──┼─> local sync agent ─> GitHub Markdown ─> AI rewrite
               │       │                     │
 GitHub  ──────┘       └─ SQLite state       └── Anthropic
                            │
 MCP clients ─> Tailscale HTTPS ─> authenticated MCP server
                                      │
                                allowed projects/folders
```

GitHub is the canonical content history. Google and Microsoft retain their own
revision histories because DocColab updates the existing file IDs rather than
creating replacement identities.

## Quick start

Requires Python 3.11+; Pandoc is recommended for the highest-fidelity conversion.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
Copy-Item config.example.json config.json
Copy-Item mcp-config.example.json mcp-config.json
New-Item -ItemType Directory -Force registry\projects
Copy-Item project.example.json registry\projects\example.json
doccolab-mcp --config mcp-config.json init-owner --user-id owner@example.com
doccolab-mcp --config mcp-config.json validate
doccolab-mcp --config mcp-config.json serve
```

Store the one-time owner bearer token in your MCP client’s secret storage. Do not
commit `.env`, OAuth files, bearer tokens, local state, or document exports.

For a single project sync agent:

```powershell
doccolab --config config.json auth-google
doccolab --config config.json auth-microsoft
doccolab --config config.json once
doccolab --config config.json run
```

## Documentation

- [Architecture and workflows](docs/ARCHITECTURE.md)
- [Complete setup and credentials](docs/SETUP.md)
- [MCP tools and role model](docs/MCP.md)
- [Private Tailscale access](docs/TAILSCALE.md)
- [Provider API examples](docs/API_EXAMPLES.md)
- [Operations and versioning](docs/OPERATIONS.md)
- [Testing](docs/TESTING.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Security policy](SECURITY.md)

## Project status

This is an executable reference implementation. Cloud integrations require your
own OAuth applications, API keys, and provider-side consent. Test first on copies
of non-sensitive documents before production use.

## License

[MIT](LICENSE)
