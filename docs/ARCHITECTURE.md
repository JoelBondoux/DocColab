# Architecture

## Repository layout

```text
DocColab/
├── agent/
│   ├── ai/                 OpenAI, Anthropic, prompts, pipeline
│   ├── conversion/         Pandoc and pure-Python DOCX ↔ Markdown
│   ├── github/             GitHub REST contents, branches, tags, PRs
│   ├── google/             OAuth, Drive, Docs, webhooks, revisions
│   ├── mcp_server/         MCP tools, auth, ACL, projects, audit
│   ├── microsoft/          MSAL, Graph, OneDrive, Word Online
│   ├── sync/               State, merge, orchestration, provider events
│   ├── webhook/            FastAPI webhook receiver
│   ├── cli_errors.py       Stable exit codes and concise operator errors
│   ├── config.py
│   ├── setup_inputs.py     Reusable validated setup input primitives
│   ├── main.py             `doccolab` local-agent CLI
│   └── runtime.py
├── docs/
├── tests/
├── registry/
│   ├── users.json          generated; bearer-token digests only
│   └── projects/*.json     one hot-reloadable project definition each
├── config.json             private per-project sync config
├── mcp-config.json         private MCP server config
└── .doccolab/              SQLite state, work files, audit log
```

## Components and trust boundaries

```text
┌ Human surfaces ───────────────────────────────────────────────┐
│ Google Docs/Drive                 Word Online/OneDrive        │
└──────────────┬───────────────────────────┬────────────────────┘
               │ OAuth                    │ OAuth + ETags/delta
               v                          v
┌ Local machine / Tailnet ──────────────────────────────────────┐
│  sync manager ─ conversion ─ AI clients ─ GitHub client       │
│       │              │                         │              │
│       └──── SQLite transaction/checkpoint state ┘              │
│                                                               │
│  MCP client -> Tailscale HTTPS -> bearer auth -> role/project │
│                  -> tool allowlist -> resolved folder path     │
└───────────────────────────────────────────────────────────────┘
                 outbound HTTPS only
```

The server never gives an AI agent an unrestricted filesystem path. A request
must pass global-role, project-membership, project-tool-allowlist, exposed-folder,
resolved-path, and size checks.

`MCPService` uses the public sync-provider interface and delegates local file and
conversion operations to `ProjectFileService`. `SyncManager` delegates webhook
validation, Google watch lifecycle, and Microsoft delta cursors to
`ProviderEventCoordinator`. These are the supported integration seams; callers
do not reach into private orchestration methods.

## Workflow A — Google Docs → GitHub → AI → Google Docs

```text
Drive notification or metadata poll
  -> read file metadata/revision
  -> export same Google file as DOCX
  -> DOCX to canonical Markdown
  -> optimistic commit of human import to GitHub
  -> optional, explicitly enabled AI rewrite preserving Markdown structure
  -> optional optimistic AI commit
  -> if google.write_mode=replace: Markdown to DOCX
  -> version preflight and update of the existing Drive file ID
  -> create Git tag and finalize SQLite checkpoint
```

Google push notifications require a public HTTPS callback reachable by Google.
A private Tailscale endpoint is not reachable from Google’s servers, so the
default private deployment polls metadata. Configure an authenticated public
relay before running `watch-google`.

Google Drive does not provide an atomic `If-Match` compare-and-swap for this
full-document conversion path. DocColab therefore defaults to `read_only`.
Replacement requires both `write_mode: "replace"` and an explicit
`acknowledge_non_atomic_replacement: true`. A version preflight narrows, but
cannot eliminate, the race between the check and the update.

## Workflow B — Word Online → GitHub → AI → Word Online

```text
Graph delta query -> changed driveItem
  -> download DOCX + record ETag
  -> DOCX to Markdown
  -> commit human import
  -> AI rewrite + second commit
  -> Markdown to DOCX
  -> replace existing driveItem with If-Match ETag
  -> preserve OneDrive version history
  -> tag and finalize checkpoint
```

Delta links are persisted in SQLite. A stale or rejected delta link is safely
reinitialized from the latest state.

## Workflow C — bidirectional multi-surface sync

```text
          Google edit ─┐
                       ├─> three-way merge -> canonical GitHub Markdown
        OneDrive edit ─┤                         │
                       │                         ├─> Google existing file
          GitHub edit ─┘                         └─> OneDrive existing item
```

Each successful round records source versions, the canonical base, content hash,
commit SHA, and monotonic document version. AI output regenerates every configured
surface.

## Workflow D — conflict and crash safety

```text
concurrent versions
  -> compare each against last shared base
  -> merge non-overlapping edits
  -> if overlap: write conflict markers on conflicts/<doc>/<timestamp>
  -> open PR; do not overwrite Google or OneDrive

canonical Git commit
  -> persist pending Markdown + target surfaces in SQLite
  -> publish each surface with revision/ETag precondition
  -> retry unfinished surfaces after restart
  -> tag only after all writes succeed
```

## Versioning

- Routine integration uses `develop`; releases use protected `main`.
- Each document normally uses its configured branch or the project GitHub branch.
- Human imports and AI rewrites are separate commits for attribution and review.
- Successful sync `N` creates `doc/<document-id>/v<major>.<minor>.<N>`.
- GitHub blob SHAs and OneDrive ETags are optimistic concurrency preconditions.
- Google replacement is disabled by default; its opt-in path performs a version
  preflight and documents the remaining race window.
