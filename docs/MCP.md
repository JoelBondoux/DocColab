# MCP server

DocColab exposes stateless Streamable HTTP at `/mcp`. Clients authenticate with:

```http
Authorization: Bearer <one-time-issued-user-token>
```

MCP `tools/list` returns a JSON Schema for every tool. The automated test suite
asserts the complete name set and validates that every project-scoped tool
requires `project_id`.

## Tools

| Tool | Minimum role | Purpose |
|---|---|---|
| `doccolab.read_file` | viewer | Read an exposed project file |
| `doccolab.write_file` | editor | Atomically write an exposed file |
| `doccolab.list_files` | viewer | List one exposed directory |
| `doccolab.convert_docx_to_md` | editor | Convert DOCX to Markdown |
| `doccolab.convert_md_to_docx` | editor | Convert Markdown to DOCX |
| `doccolab.pull_google_doc` | editor | Fetch configured Google content |
| `doccolab.push_google_doc` | editor | Update configured Google file when explicit replace mode is enabled |
| `doccolab.pull_onedrive_file` | editor | Fetch configured OneDrive item |
| `doccolab.push_onedrive_file` | editor | Update item with ETag check |
| `doccolab.sync_github` | editor | Run project GitHub synchronization |
| `doccolab.run_claude_pipeline` | editor | Rewrite supplied Markdown |
| `doccolab.run_openai_pipeline` | editor | Rewrite supplied Markdown |
| `doccolab.update_document` | editor | Synchronize one logical document |
| `doccolab.roundtrip_google_docs` | editor | Google round trip |
| `doccolab.roundtrip_onedrive` | editor | OneDrive round trip |
| `doccolab.roundtrip_github` | editor | GitHub round trip |
| `doccolab.list_projects` | viewer | List memberships |
| `doccolab.get_project_config` | viewer | Read safe project definition |
| `doccolab.set_project_config` | owner | Replace project definition |
| `doccolab.expose_folder` | owner | Add a project-relative folder |
| `doccolab.revoke_folder` | owner | Remove exposed folder access |
| `doccolab.list_users` | owner | List users without bearer secrets |
| `doccolab.add_user` | owner | Add user and issue one-time token |
| `doccolab.remove_user` | owner | Disable/remove a user |
| `doccolab.set_user_role` | owner | Change global role |

Exact arguments and return shapes are discoverable through `tools/list`; source
definitions live in `agent/mcp_server/tools.py`.

## Authorization

The effective permission is the lower of the user’s global role and their role
in the selected project. A project may also restrict `allowed_tools`. Owners
administer users, project config, and folder exposure. Editors change documents
and invoke pipelines. Viewers can read/list/convert without mutating source data.

The last enabled global owner cannot be deleted or demoted.

## Project isolation

`project_id` resolves to a hot-reloaded JSON definition. A file path must be:

1. relative and free of `..`;
2. under an explicitly exposed folder;
3. under the canonical resolved project root after symlink resolution;
4. within configured read/write byte limits.

Cloud document identifiers are resolved through the project’s `config.json`; an
agent cannot supply arbitrary provider credentials. Google push/round-trip tools
refuse to publish while the default `google.write_mode` is `read_only`.

## Client configuration

A generic MCP client needs the Streamable HTTP endpoint and bearer header:

```json
{
  "servers": {
    "doccolab": {
      "type": "streamable-http",
      "url": "https://doccolab.your-tailnet.ts.net/mcp",
      "headers": {
        "Authorization": "Bearer ${DOCCOLAB_MCP_TOKEN}"
      }
    }
  }
}
```

Client configuration keys vary. Use the client’s current MCP documentation and
secret facility rather than embedding the token in a shared file. The endpoint
works only while the client device is connected to the authorized Tailnet.

## Audit and rotation

Every tool invocation is written to the configured JSONL audit log with time,
user, project, tool, non-secret request metadata, and an outcome of `authorized`,
`denied`, `succeeded`, or `failed`. Failures retain only their error class in the
audit record. Rotate a token:

```powershell
doccolab-mcp --config mcp-config.json rotate-token --user-id user@example.com
```
