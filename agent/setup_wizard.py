from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import secrets
import shutil
from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel

from agent.config import AppConfig
from agent.mcp_server.models import (
    MCPServerConfig,
    ProjectDefinition,
    Role,
    UserRecord,
    UsersFile,
)

AIProvider = Literal["openai", "anthropic", "none"]
InputFunction = Callable[[str], str]
OutputFunction = Callable[[str], None]


class SetupConflict(RuntimeError):
    """Raised when setup would overwrite an existing configuration file."""


class SetupCancelled(RuntimeError):
    """Raised when the operator cancels interactive setup."""


@dataclass(frozen=True, slots=True)
class SetupAnswers:
    output_directory: Path
    project_id: str
    project_title: str
    owner_user_id: str
    github_owner: str
    github_repository: str
    github_branch: str = "develop"
    document_id: str = "main-document"
    document_title: str = "Main document"
    exposed_folders: tuple[str, ...] = ("documents", "references")
    google_enabled: bool = True
    google_file_id: str | None = None
    microsoft_enabled: bool = False
    microsoft_drive_id: str | None = None
    microsoft_item_id: str | None = None
    ai_provider: AIProvider = "openai"
    tailnet_hostname: str | None = None
    github_token: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    microsoft_client_id: str = ""

    def __post_init__(self) -> None:
        if not _valid_project_id(self.project_id):
            raise ValueError("project_id must contain lowercase letters, numbers, or hyphens")
        if not _valid_project_id(self.document_id):
            raise ValueError("document_id must contain lowercase letters, numbers, or hyphens")
        if not self.project_title.strip() or not self.owner_user_id.strip():
            raise ValueError("Project title and owner user ID are required")
        if not self.google_enabled and not self.microsoft_enabled:
            raise ValueError("Enable at least one Google Docs or OneDrive surface")
        if self.google_enabled and not self.google_file_id:
            raise ValueError("google_file_id is required when Google Docs is enabled")
        if self.microsoft_enabled and not self.microsoft_item_id:
            raise ValueError("microsoft_item_id is required when OneDrive is enabled")
        if not self.github_owner.strip() or not self.github_repository.strip():
            raise ValueError("GitHub owner and repository are required")
        if not self.github_branch.strip():
            raise ValueError("GitHub branch is required")
        for folder in self.exposed_folders:
            path = Path(folder)
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise ValueError(
                    "exposed_folders must contain only safe project-relative paths"
                )
        if "documents" not in self.exposed_folders:
            raise ValueError("exposed_folders must include the canonical documents folder")
        if self.tailnet_hostname and not _valid_hostname(self.tailnet_hostname):
            raise ValueError("tailnet_hostname must be a hostname without a URL scheme or path")


@dataclass(frozen=True, slots=True)
class SetupResult:
    owner_token: str
    created_files: tuple[Path, ...]
    next_commands: tuple[str, ...]


def generate_setup(answers: SetupAnswers) -> SetupResult:
    root = answers.output_directory.resolve()
    project_path = Path("registry/projects") / f"{answers.project_id}.json"
    relative_targets = (
        Path(".env"),
        Path("config.json"),
        Path("mcp-config.json"),
        Path("registry/users.json"),
        project_path,
    )
    conflicts = [root / target for target in relative_targets if (root / target).exists()]
    if conflicts:
        rendered = ", ".join(str(path.relative_to(root)) for path in conflicts)
        raise SetupConflict(
            f"Refusing to overwrite existing setup files: {rendered}. "
            "Move or back up those files before running setup again."
        )

    owner_token = secrets.token_urlsafe(36)
    artifacts = _build_artifacts(answers, root, owner_token, project_path)
    created_files: list[Path] = []
    created_directories: list[Path] = []
    root_was_created = not root.exists()
    try:
        root.mkdir(parents=True, exist_ok=True)
        for folder in answers.exposed_folders:
            directory = (root / folder).resolve()
            if not directory.is_relative_to(root):
                raise ValueError(f"Exposed folder {folder!r} escapes the project root")
            if directory.exists() and not directory.is_dir():
                raise ValueError(f"Exposed folder {folder!r} exists but is not a directory")
            if not directory.exists():
                directory.mkdir(parents=True)
                created_directories.append(directory)
        for relative, content in artifacts.items():
            target = root / relative
            _atomic_write(target, content)
            created_files.append(target)
    except Exception:
        _clean_partial_setup(
            created_files,
            created_directories,
            root if root_was_created else None,
        )
        raise

    python_command = "python"
    next_commands = (
        f"{python_command} -m agent.main --config {root / 'config.json'} auth-google"
        if answers.google_enabled
        else "",
        f"{python_command} -m agent.main --config {root / 'config.json'} auth-microsoft"
        if answers.microsoft_enabled
        else "",
        f"{python_command} -m agent.mcp_server.main "
        f"--config {root / 'mcp-config.json'} validate",
        f"{python_command} -m agent.mcp_server.main "
        f"--config {root / 'mcp-config.json'} serve",
    )
    return SetupResult(
        owner_token=owner_token,
        created_files=tuple(created_files),
        next_commands=tuple(command for command in next_commands if command),
    )


def _build_artifacts(
    answers: SetupAnswers,
    root: Path,
    owner_token: str,
    project_path: Path,
) -> dict[Path, str]:
    ai_enabled = answers.ai_provider != "none"
    configured_ai_provider = (
        answers.ai_provider if answers.ai_provider in {"openai", "anthropic"} else "openai"
    )
    sync_config = AppConfig.model_validate(
        {
            "agent": {
                "poll_interval_seconds": 30,
                "webhook_host": "127.0.0.1",
                "webhook_port": 8787,
                "public_webhook_base_url": None,
                "state_database": ".doccolab/state.db",
                "workspace_directory": ".doccolab/work",
                "log_level": "INFO",
            },
            "google": {
                "enabled": answers.google_enabled,
                "client_secrets_file": "secrets/google-oauth-client.json",
                "credential_keyring_service": "doccolab-google",
                "credential_keyring_user": answers.owner_user_id,
                "webhook_token_env": _environment_name("GOOGLE_WEBHOOK_TOKEN"),
                "watch_ttl_seconds": 604800,
            },
            "microsoft": {
                "enabled": answers.microsoft_enabled,
                "client_id_env": "MICROSOFT_CLIENT_ID",
                "tenant": "common",
                "scopes": ["Files.ReadWrite.All", "User.Read"],
                "credential_keyring_service": "doccolab-microsoft",
                "credential_keyring_user": answers.owner_user_id,
            },
            "github": {
                "enabled": True,
                "owner": answers.github_owner,
                "repository": answers.github_repository,
                "token_env": _environment_name("GITHUB_TOKEN"),
                "branch": answers.github_branch,
                "api_url": "https://api.github.com",
                "api_version": "2026-03-10",
                "commit_author_name": "DocColab Agent",
                "commit_author_email": "doccolab-agent@users.noreply.github.com",
                "tag_prefix": "doc",
            },
            "conversion": {
                "pandoc_binary": "pandoc",
                "reference_docx": None,
                "prefer_pandoc": True,
            },
            "ai": {
                "enabled": ai_enabled,
                "provider": configured_ai_provider,
                "openai_model": "gpt-5.6-terra",
                "anthropic_model": "claude-sonnet-5",
                "max_output_tokens": 32000,
                "auto_rewrite_human_changes": ai_enabled,
                "operations": (
                    ["improve_clarity", "improve_structure"] if ai_enabled else []
                ),
                "tone": "clear, professional, and approachable",
                "style_rules": [
                    "Preserve factual meaning.",
                    "Preserve Markdown headings, lists, tables, emphasis, and links.",
                    "Do not invent citations or facts.",
                ],
            },
            "versioning": {"major": 0, "minor": 1, "create_tags": True},
            "documents": [
                {
                    "id": answers.document_id,
                    "title": answers.document_title,
                    "markdown_path": f"documents/{answers.document_id}.md",
                    "google_file_id": (
                        answers.google_file_id if answers.google_enabled else None
                    ),
                    "microsoft_drive_id": (
                        answers.microsoft_drive_id if answers.microsoft_enabled else None
                    ),
                    "microsoft_item_id": (
                        answers.microsoft_item_id if answers.microsoft_enabled else None
                    ),
                    "github_branch": None,
                    "enabled": True,
                }
            ],
        }
    )

    allowed_hosts = ["127.0.0.1:*", "localhost:*"]
    allowed_origins = ["http://127.0.0.1:*", "http://localhost:*"]
    if answers.tailnet_hostname:
        hostname = answers.tailnet_hostname.lower()
        allowed_hosts.append(hostname)
        allowed_origins.append(f"https://{hostname}")
    server_config = MCPServerConfig(
        host="127.0.0.1",
        port=8765,
        mcp_path="/mcp",
        users_file=Path("registry/users.json"),
        projects_directory=Path("registry/projects"),
        audit_log=Path(".doccolab/audit.jsonl"),
        allowed_project_roots=[root],
        hot_reload_seconds=5,
        run_sync_agents=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )
    project = ProjectDefinition(
        id=answers.project_id,
        title=answers.project_title,
        root_path=root,
        sync_config=Path("config.json"),
        exposed_folders=list(answers.exposed_folders),
        members={answers.owner_user_id: Role.OWNER},
        allowed_tools=["*"],
    )
    owner = UserRecord(
        user_id=answers.owner_user_id,
        display_name=answers.owner_user_id,
        role=Role.OWNER,
        token_sha256=hashlib.sha256(owner_token.encode("utf-8")).hexdigest(),
    )
    users = UsersFile(users=[owner])
    google_webhook_token = secrets.token_urlsafe(36) if answers.google_enabled else ""
    environment = "\n".join(
        (
            "# Generated by doccolab-setup. Keep this file private.",
            f"OPENAI_API_KEY={_dotenv_value(answers.openai_api_key)}",
            f"ANTHROPIC_API_KEY={_dotenv_value(answers.anthropic_api_key)}",
            f"GITHUB_TOKEN={_dotenv_value(answers.github_token)}",
            f"MICROSOFT_CLIENT_ID={_dotenv_value(answers.microsoft_client_id)}",
            f"GOOGLE_WEBHOOK_TOKEN={_dotenv_value(google_webhook_token)}",
            "DOCCOLAB_OPENAI_MODEL=",
            "DOCCOLAB_ANTHROPIC_MODEL=",
            "",
        )
    )
    return {
        Path(".env"): environment,
        Path("config.json"): _model_json(sync_config),
        Path("mcp-config.json"): _model_json(server_config),
        Path("registry/users.json"): _model_json(users),
        project_path: _model_json(project),
    }


def run_interactive(
    output_directory: Path,
    *,
    input_fn: InputFunction = input,
    secret_fn: InputFunction = getpass.getpass,
    output_fn: OutputFunction = print,
) -> SetupResult:
    root = output_directory.resolve()
    output_fn("DocColab guided setup")
    output_fn("======================")
    output_fn(f"Configuration directory: {root}")
    output_fn("")
    _show_prerequisites(output_fn)

    project_title = _ask(
        "Project title",
        default=root.name or "DocColab project",
        input_fn=input_fn,
    )
    project_id = _ask(
        "Project ID",
        default=_slug(project_title),
        input_fn=input_fn,
        validator=_valid_project_id,
        error="Use lowercase letters, numbers, and hyphens; start with a letter or number.",
    )
    owner_user_id = _ask(
        "Owner email or user ID",
        input_fn=input_fn,
        validator=lambda value: bool(value.strip()),
    )
    github_owner = _ask("GitHub owner or organization", input_fn=input_fn)
    github_repository = _ask(
        "GitHub repository",
        default=root.name or "DocColab",
        input_fn=input_fn,
    )
    github_branch = _ask("GitHub branch", default="develop", input_fn=input_fn)
    document_title = _ask("First document title", default="Main document", input_fn=input_fn)
    document_id = _ask(
        "First document ID",
        default=_slug(document_title),
        input_fn=input_fn,
        validator=_valid_project_id,
    )

    while True:
        google_enabled = _yes_no("Connect Google Docs?", True, input_fn)
        google_file_id = (
            _ask("Google Drive file ID", input_fn=input_fn) if google_enabled else None
        )
        microsoft_enabled = _yes_no("Connect Word Online / OneDrive?", True, input_fn)
        microsoft_item_id = (
            _ask("OneDrive item ID", input_fn=input_fn) if microsoft_enabled else None
        )
        microsoft_drive_id = (
            _ask(
                "OneDrive drive ID",
                default="",
                required=False,
                input_fn=input_fn,
            )
            if microsoft_enabled
            else None
        )
        if google_enabled or microsoft_enabled:
            break
        output_fn("Enable at least one Google Docs or OneDrive surface.")

    ai_provider = _choice(
        "AI rewrite provider",
        ("openai", "anthropic", "none"),
        "openai",
        input_fn,
    )
    exposed_text = _ask(
        "Folders exposed to MCP agents (comma-separated; includes all descendants)",
        default="documents,references",
        input_fn=input_fn,
        validator=_valid_exposed_input,
        error=(
            "Use safe project-relative folders and include 'documents'; "
            "do not use absolute paths or '..'."
        ),
    )
    exposed_folders = tuple(
        part.strip().replace("\\", "/") for part in exposed_text.split(",") if part.strip()
    )
    tailnet_hostname = _ask(
        "Tailscale MagicDNS hostname (optional)",
        default="",
        required=False,
        input_fn=input_fn,
        validator=lambda value: not value or _valid_hostname(value),
        error="Enter only a hostname, for example doccolab.example.ts.net.",
    )

    output_fn("")
    output_fn("Secrets are written only to the ignored local .env file.")
    github_token = secret_fn("GitHub fine-grained PAT (optional now): ").strip()
    microsoft_client_id = (
        _ask(
            "Microsoft Entra application/client ID",
            default="",
            required=False,
            input_fn=input_fn,
        )
        if microsoft_enabled
        else ""
    )
    openai_api_key = (
        secret_fn("OpenAI API key (optional now): ").strip()
        if ai_provider == "openai"
        else ""
    )
    anthropic_api_key = (
        secret_fn("Anthropic API key (optional now): ").strip()
        if ai_provider == "anthropic"
        else ""
    )

    answers = SetupAnswers(
        output_directory=root,
        project_id=project_id,
        project_title=project_title,
        owner_user_id=owner_user_id,
        github_owner=github_owner,
        github_repository=github_repository,
        github_branch=github_branch,
        document_id=document_id,
        document_title=document_title,
        exposed_folders=exposed_folders,
        google_enabled=google_enabled,
        google_file_id=google_file_id,
        microsoft_enabled=microsoft_enabled,
        microsoft_drive_id=microsoft_drive_id or None,
        microsoft_item_id=microsoft_item_id,
        ai_provider=ai_provider,
        tailnet_hostname=tailnet_hostname or None,
        github_token=github_token,
        openai_api_key=openai_api_key,
        anthropic_api_key=anthropic_api_key,
        microsoft_client_id=microsoft_client_id,
    )
    output_fn("")
    output_fn(f"Project: {answers.project_title} ({answers.project_id})")
    output_fn(f"GitHub: {answers.github_owner}/{answers.github_repository}")
    output_fn(f"Exposed folders: {', '.join(answers.exposed_folders)}")
    if not _yes_no("Create these configuration files?", True, input_fn):
        raise SetupCancelled("Setup cancelled; no files were written")
    return generate_setup(answers)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doccolab-setup",
        description="Interactively create a safe local DocColab configuration.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory that will contain config.json (default: current directory)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        result = run_interactive(arguments.output_dir)
    except (EOFError, KeyboardInterrupt, SetupCancelled) as exc:
        print(f"\n{exc or 'Setup cancelled; no files were written.'}")
        return 130
    except (SetupConflict, ValueError) as exc:
        print(f"\nSetup stopped: {exc}")
        return 1

    print("")
    print("Setup complete.")
    print("Store this MCP owner bearer token now; it cannot be recovered:")
    print(result.owner_token)
    print("")
    print("Next commands:")
    for command in result.next_commands:
        print(f"  {command}")
    return 0


def cli() -> None:
    raise SystemExit(main())


def _show_prerequisites(output_fn: OutputFunction) -> None:
    checks = {
        "Git": shutil.which("git"),
        "Pandoc (recommended)": shutil.which("pandoc"),
        "Tailscale (optional)": shutil.which("tailscale"),
    }
    for label, executable in checks.items():
        output_fn(f"[{'ok' if executable else '--'}] {label}")
    output_fn("")


def _ask(
    label: str,
    *,
    input_fn: InputFunction,
    default: str | None = None,
    required: bool = True,
    validator: Callable[[str], bool] | None = None,
    error: str = "Please enter a valid value.",
) -> str:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        value = input_fn(f"{label}{suffix}: ").strip()
        if not value and default is not None:
            value = default
        if not value and not required:
            return ""
        if value and (validator is None or validator(value)):
            return value
        print(error)


def _yes_no(label: str, default: bool, input_fn: InputFunction) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        value = input_fn(f"{label} [{suffix}]: ").strip().lower()
        if not value:
            return default
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        print("Enter yes or no.")


def _choice(
    label: str,
    choices: tuple[AIProvider, ...],
    default: AIProvider,
    input_fn: InputFunction,
) -> AIProvider:
    rendered = "/".join(choices)
    while True:
        value = input_fn(f"{label} ({rendered}) [{default}]: ").strip().lower()
        selected = value or default
        if selected in choices:
            return cast(AIProvider, selected)
        print(f"Choose one of: {', '.join(choices)}.")


def _valid_project_id(value: str) -> bool:
    return re.fullmatch(r"[a-z0-9][a-z0-9-]*", value) is not None


def _valid_hostname(value: str) -> bool:
    return (
        len(value) <= 253
        and re.fullmatch(
            r"(?=.{1,253}\Z)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*"
            r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?",
            value,
        )
        is not None
    )


def _valid_exposed_input(value: str) -> bool:
    folders = tuple(
        part.strip().replace("\\", "/") for part in value.split(",") if part.strip()
    )
    if "documents" not in folders:
        return False
    return all(
        not Path(folder).is_absolute()
        and ".." not in Path(folder).parts
        and bool(Path(folder).parts)
        for folder in folders
    )


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "project"


def _model_json(model: BaseModel) -> str:
    return json.dumps(model.model_dump(mode="json"), indent=2) + "\n"


def _dotenv_value(value: str) -> str:
    return json.dumps(value)


def _environment_name(value: str) -> str:
    """Mark a literal as an environment-variable identifier rather than a secret."""
    return value


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        with suppress(OSError):
            temporary.chmod(0o600)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _clean_partial_setup(
    files: list[Path],
    directories: list[Path],
    root: Path | None,
) -> None:
    for path in reversed(files):
        with suppress(OSError):
            path.unlink()
    for path in reversed(directories):
        with suppress(OSError):
            path.rmdir()
    parent_candidates = {path.parent for path in files}
    for path in sorted(parent_candidates, key=lambda item: len(item.parts), reverse=True):
        with suppress(OSError):
            path.rmdir()
    if root is not None:
        with suppress(OSError):
            root.rmdir()


if __name__ == "__main__":
    cli()
