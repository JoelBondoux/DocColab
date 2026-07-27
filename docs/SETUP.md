# Complete setup

## Guided setup

The recommended Windows path is:

```powershell
.\setup.ps1
```

Optional launcher parameters:

```powershell
.\setup.ps1 -SkipInstall
.\setup.ps1 -OutputDirectory C:\Documents\MyDocColabProject
```

The launcher creates `.venv`, installs the project, and starts
`doccolab-setup`. The wizard:

- checks for Git, Pandoc, and Tailscale;
- leaves cloud integrations disabled unless selected and requires explicit
  acknowledgement of provider-wide consent;
- configures Google read-only by default and explains the residual race before
  offering full-document replacement;
- configures GitHub and leaves the OpenAI/Anthropic pipeline off unless selected;
- creates the MCP server, project membership, and exposed-folder settings;
- stores provider API tokens and the webhook verification token in the operating
  system keyring; `.env` contains only non-secret local overrides;
- keeps generated live configuration, membership files, and OAuth secrets out of Git;
- generates a high-entropy webhook token;
- issues the first owner bearer token once while storing only its SHA-256 digest;
- validates all configuration models before writing anything;
- refuses to overwrite any existing setup file.

On macOS, Linux, or an existing Python environment:

```text
python -m pip install -e .
doccolab-setup
```

To configure a different directory:

```text
doccolab-setup --output-dir /absolute/path/to/project
```

Save the displayed MCP owner token immediately. If setup finds `config.json`,
`mcp-config.json`, `.env`, or matching registry files, it stops without modifying
any of them. Move or back up the old configuration before rerunning.

## 1. Install local dependencies

Install Git, Python 3.11 or later, and optionally Pandoc. Pandoc gives the best
round-trip fidelity; the built-in converter supports headings, lists, tables,
bold, italics, links, code, and paragraphs when Pandoc is unavailable.

```powershell
git clone https://github.com/JoelBondoux/DocColab.git
Set-Location DocColab
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
Copy-Item config.example.json config.json
Copy-Item mcp-config.example.json mcp-config.json
```

The remaining sections describe every provider step in detail and are useful
after the wizard prints its follow-up commands.

## 2. Google OAuth

1. Create or select a Google Cloud project.
2. Enable Google Drive API and Google Docs API.
3. Configure the OAuth consent screen.
4. Create a Desktop application OAuth client.
5. Download it as `secrets/google-oauth-client.json`.
6. Add your account as a test user while the consent app is in testing.
7. Run `doccolab --config config.json auth-google`.

The refresh credential is serialized into the OS keyring, not the repository.
The installed-app implementation currently requests Drive and Docs access that
can reach more than the configured document IDs. Set
`google.acknowledge_broad_access` only after reviewing that consent. DocColab
enforces document IDs in its own configuration, but that does not narrow the
OAuth grant itself.

Google starts in `write_mode: "read_only"`. To opt into full-document
replacement, use:

```json
{
  "google": {
    "enabled": true,
    "acknowledge_broad_access": true,
    "write_mode": "replace",
    "acknowledge_non_atomic_replacement": true
  }
}
```

The opt-in path checks the current Drive version before updating the existing
file ID, but Google does not provide an atomic conditional replacement for this
conversion flow. Use a disposable copy first and retain provider version history.

For Drive webhooks, set a random `GOOGLE_WEBHOOK_TOKEN`, configure a public HTTPS
relay URL in `agent.public_webhook_base_url`, and run:

```powershell
doccolab --config config.json watch-google
```

Google cannot call a Tailnet-only URL. Leave `public_webhook_base_url` null to
use the built-in polling path.

## 3. Microsoft Entra and Graph

1. Register an application in Microsoft Entra ID.
2. Enable public client flows for the desktop/device-code client.
3. Add delegated Microsoft Graph permissions `Files.ReadWrite.All` and
   `User.Read`, then grant consent as required by your tenant.
4. Put the Application (client) ID in `.env` as `MICROSOFT_CLIENT_ID`.
5. Set `microsoft.tenant` to your tenant ID for an organization-only app, or keep
   `common` for supported multi-tenant/personal accounts.
6. Run `doccolab --config config.json auth-microsoft` and complete device login.

The MSAL token cache is encrypted by the OS keyring.
`Files.ReadWrite.All` can reach files beyond the configured item. Set
`microsoft.acknowledge_broad_access` only after reviewing tenant consent. If a
narrower delegated permission works for your deployment, configure
`microsoft.scopes` accordingly; the acknowledgement is required whenever a known
broad write scope is enabled.

## 4. GitHub authentication

Create a fine-grained personal access token restricted to the target repository.
Grant repository Contents read/write and Pull requests read/write. If tags or
branch protection require additional organization approval, obtain that approval.
Store the token without exposing it on the command line:

```powershell
doccolab set-secret --name GITHUB_TOKEN
```

For an unattended service account without a usable keyring, set `GITHUB_TOKEN`
through the service manager's protected environment configuration.

Set `github.owner`, `repository`, `branch`, and commit identity in `config.json`.
Never put the PAT directly in JSON.

## 5. AI providers

Create an API key in the provider console and store only the provider you use:

```powershell
doccolab set-secret --name OPENAI_API_KEY
doccolab set-secret --name ANTHROPIC_API_KEY
```

AI is disabled by default and human changes are never automatically sent to a
model unless `ai.enabled` and `ai.auto_rewrite_human_changes` are both enabled.
Select `openai` or `anthropic` under `ai.provider`. Configure rewrite operations:
`summarize`, `improve_clarity`, `improve_structure`, and/or `expand_sections`.
Tone and style rules are injected into a safety-oriented Markdown-preservation
prompt. Model IDs can be overridden through `DOCCOLAB_OPENAI_MODEL` and
`DOCCOLAB_ANTHROPIC_MODEL`.

Before enabling AI, confirm that the document's classification and the provider's
data-processing terms permit sending its contents.

## 6. Map documents

In `config.json`, give every logical document:

- a stable lowercase `id`;
- a safe repository-relative `markdown_path`;
- a Google Drive file ID, OneDrive item ID, or both;
- an optional OneDrive drive ID and GitHub branch.

The Google file ID appears in the document URL. For OneDrive, use Microsoft Graph
Explorer or the driveItem API to obtain the item and drive IDs.

## 7. Configure projects and users

Create one project file per allowed root:

```powershell
New-Item -ItemType Directory -Force registry\projects
Copy-Item project.example.json registry\projects\example.json
```

Set an absolute `root_path`, a relative `sync_config`, and only the folders agents
may see in `exposed_folders`. The root must be beneath one of
`mcp-config.json.allowed_project_roots`.

Each exposed folder is recursive: agents can access every child file and subfolder
beneath it. Add the highest-level folder whose full contents should be available;
you do not need to list its descendants separately. Folder exposure does not copy
or move content, and resolved paths that escape through `..` or a symlink remain
blocked.

Create the first owner:

```powershell
doccolab-mcp --config mcp-config.json init-owner --user-id owner@example.com
```

Copy the displayed token once into secret storage. DocColab stores only its
SHA-256 digest. Validate everything:

```powershell
doccolab-mcp --config mcp-config.json validate
```

## 8. Run

One synchronization:

```powershell
doccolab --config config.json once
```

Continuous local agent with webhook receiver:

```powershell
doccolab --config config.json run
```

Authenticated MCP service:

```powershell
doccolab-mcp --config mcp-config.json serve
```

The MCP service can supervise every enabled project agent when
`run_sync_agents` is true. Project and user files are re-read without a process
restart.

Common configuration, authorization, credential, and provider failures return a
concise operator message. Exit codes are `0` for success, `1` for an operation or
provider failure, `2` for invalid configuration, `3` for denied access, and `130`
for cancellation.

## Secret precedence and rotation

DocColab checks a named environment variable first, then the
`doccolab-secrets` operating-system keyring service. This precedence allows
service managers to inject credentials without modifying configuration files.

```powershell
doccolab set-secret --name GITHUB_TOKEN
doccolab delete-secret --name GITHUB_TOKEN
```

Restart the running agent after changing a provider credential. Revoke the old
credential at its provider after the replacement has passed a read-only smoke
test.
