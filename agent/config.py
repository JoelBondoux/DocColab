from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentConfig(StrictModel):
    poll_interval_seconds: int = Field(default=30, ge=5)
    webhook_host: str = "127.0.0.1"
    webhook_port: int = Field(default=8787, ge=1, le=65535)
    public_webhook_base_url: str | None = None
    state_database: Path = Path(".doccolab/state.db")
    workspace_directory: Path = Path(".doccolab/work")
    log_level: str = "INFO"


class GoogleConfig(StrictModel):
    enabled: bool = False
    client_secrets_file: Path = Path("secrets/google-oauth-client.json")
    credential_keyring_service: str = "doccolab-google"
    credential_keyring_user: str = "default"
    webhook_token_env: str = "GOOGLE_WEBHOOK_TOKEN"
    watch_ttl_seconds: int = Field(default=604800, ge=3600, le=604800)
    acknowledge_broad_access: bool = False
    write_mode: Literal["read_only", "replace"] = "read_only"
    acknowledge_non_atomic_replacement: bool = False

    @model_validator(mode="after")
    def require_explicit_google_consent(self) -> GoogleConfig:
        if self.enabled and not self.acknowledge_broad_access:
            raise ValueError(
                "google.acknowledge_broad_access must be true because the installed-app "
                "OAuth flow can access more than the configured document IDs"
            )
        if self.write_mode == "replace" and not self.acknowledge_non_atomic_replacement:
            raise ValueError(
                "google.acknowledge_non_atomic_replacement must be true when "
                "google.write_mode is 'replace'"
            )
        return self


class MicrosoftConfig(StrictModel):
    enabled: bool = False
    client_id_env: str = "MICROSOFT_CLIENT_ID"
    tenant: str = "common"
    scopes: list[str] = Field(default_factory=lambda: ["Files.ReadWrite.All", "User.Read"])
    credential_keyring_service: str = "doccolab-microsoft"
    credential_keyring_user: str = "default"
    acknowledge_broad_access: bool = False

    @model_validator(mode="after")
    def require_explicit_microsoft_consent(self) -> MicrosoftConfig:
        broad = {"Files.ReadWrite.All", "Sites.ReadWrite.All"}
        if self.enabled and broad.intersection(self.scopes) and not self.acknowledge_broad_access:
            raise ValueError(
                "microsoft.acknowledge_broad_access must be true for broad Graph scopes"
            )
        return self


class GitHubConfig(StrictModel):
    enabled: bool = True
    owner: str
    repository: str
    token_env: str = "GITHUB_TOKEN"
    branch: str = "main"
    api_url: str = "https://api.github.com"
    api_version: str = "2026-03-10"
    commit_author_name: str = "DocColab Agent"
    commit_author_email: str = "doccolab-agent@users.noreply.github.com"
    tag_prefix: str = "doc"


class ConversionConfig(StrictModel):
    pandoc_binary: str = "pandoc"
    reference_docx: Path | None = None
    prefer_pandoc: bool = True


RewriteOperation = Literal[
    "summarize",
    "improve_clarity",
    "improve_structure",
    "expand_sections",
]


class AIConfig(StrictModel):
    enabled: bool = False
    provider: Literal["openai", "anthropic"] = "openai"
    openai_model: str = "gpt-5.6-terra"
    anthropic_model: str = "claude-sonnet-5"
    max_output_tokens: int = Field(default=32000, ge=256)
    auto_rewrite_human_changes: bool = False
    operations: list[RewriteOperation] = Field(default_factory=list)
    tone: str | None = None
    style_rules: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_operation(self) -> AIConfig:
        if self.enabled and not self.operations:
            raise ValueError("ai.operations must contain at least one operation when AI is enabled")
        return self


class VersioningConfig(StrictModel):
    major: int = Field(default=0, ge=0)
    minor: int = Field(default=1, ge=0)
    create_tags: bool = True


class DocumentConfig(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: str
    markdown_path: str
    google_file_id: str | None = None
    microsoft_drive_id: str | None = None
    microsoft_item_id: str | None = None
    github_branch: str | None = None
    enabled: bool = True

    @model_validator(mode="after")
    def require_surface(self) -> DocumentConfig:
        if not self.google_file_id and not self.microsoft_item_id:
            raise ValueError(
                f"document {self.id!r} must define google_file_id or microsoft_item_id"
            )
        if self.markdown_path.startswith("/") or ".." in Path(self.markdown_path).parts:
            raise ValueError("markdown_path must be a safe repository-relative path")
        return self


class AppConfig(StrictModel):
    agent: AgentConfig = Field(default_factory=AgentConfig)
    google: GoogleConfig = Field(default_factory=GoogleConfig)
    microsoft: MicrosoftConfig = Field(default_factory=MicrosoftConfig)
    github: GitHubConfig
    conversion: ConversionConfig = Field(default_factory=ConversionConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    versioning: VersioningConfig = Field(default_factory=VersioningConfig)
    documents: list[DocumentConfig]

    @model_validator(mode="after")
    def unique_documents(self) -> AppConfig:
        ids = [document.id for document in self.documents]
        paths = [document.markdown_path for document in self.documents]
        if len(ids) != len(set(ids)):
            raise ValueError("document ids must be unique")
        if len(paths) != len(set(paths)):
            raise ValueError("document markdown_path values must be unique")
        return self


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path).resolve()
    load_dotenv(config_path.parent / ".env")
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    config = AppConfig.model_validate(raw)

    base = config_path.parent
    config.agent.state_database = _resolve(base, config.agent.state_database)
    config.agent.workspace_directory = _resolve(base, config.agent.workspace_directory)
    config.google.client_secrets_file = _resolve(base, config.google.client_secrets_file)
    if config.conversion.reference_docx:
        config.conversion.reference_docx = _resolve(base, config.conversion.reference_docx)

    openai_override = os.getenv("DOCCOLAB_OPENAI_MODEL")
    anthropic_override = os.getenv("DOCCOLAB_ANTHROPIC_MODEL")
    if openai_override:
        config.ai.openai_model = openai_override
    if anthropic_override:
        config.ai.anthropic_model = anthropic_override
    return config


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


def _resolve(base: Path, value: Path) -> Path:
    return value if value.is_absolute() else (base / value).resolve()
