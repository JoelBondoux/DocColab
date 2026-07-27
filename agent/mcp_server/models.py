from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Role(StrEnum):
    VIEWER = "viewer"
    EDITOR = "editor"
    OWNER = "owner"


ROLE_LEVEL = {
    Role.VIEWER: 10,
    Role.EDITOR: 20,
    Role.OWNER: 30,
}


class UserRecord(StrictModel):
    user_id: str = Field(min_length=1, max_length=254)
    display_name: str | None = None
    role: Role = Role.VIEWER
    token_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    enabled: bool = True


class UsersFile(StrictModel):
    version: int = 1
    users: list[UserRecord] = Field(default_factory=list)


class ProjectDefinition(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: str
    root_path: Path
    sync_config: Path = Path("config.json")
    exposed_folders: list[str] = Field(default_factory=list)
    members: dict[str, Role] = Field(default_factory=dict)
    allowed_tools: list[str] = Field(default_factory=lambda: ["*"])
    enabled: bool = True

    @field_validator("exposed_folders")
    @classmethod
    def validate_exposed_folders(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            path = Path(value)
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise ValueError("exposed folders must be safe project-relative paths")
            normalized.append(path.as_posix().strip("/"))
        if len(normalized) != len(set(normalized)):
            raise ValueError("exposed folders must be unique")
        return normalized

    @field_validator("sync_config")
    @classmethod
    def validate_sync_config(cls, value: Path) -> Path:
        if value.is_absolute() or ".." in value.parts:
            raise ValueError("sync_config must be project-relative")
        return value


class MCPServerConfig(StrictModel):
    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1, le=65535)
    mcp_path: str = "/mcp"
    users_file: Path = Path("registry/users.json")
    projects_directory: Path = Path("registry/projects")
    audit_log: Path = Path(".doccolab/audit.jsonl")
    audit_max_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    audit_backup_count: int = Field(default=10, ge=1, le=100)
    allowed_project_roots: list[Path]
    hot_reload_seconds: int = Field(default=5, ge=1)
    run_sync_agents: bool = True
    max_read_bytes: int = Field(default=5 * 1024 * 1024, ge=1024)
    max_write_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    allowed_hosts: list[str] = Field(
        default_factory=lambda: ["127.0.0.1:*", "localhost:*"]
    )
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:*", "http://localhost:*"]
    )
    log_level: str = "INFO"

    @field_validator("mcp_path")
    @classmethod
    def valid_mcp_path(cls, value: str) -> str:
        if not value.startswith("/") or value == "/":
            raise ValueError("mcp_path must be a non-root absolute URL path")
        return value.rstrip("/")


class ToolResult(StrictModel):
    ok: bool = True
    project_id: str | None = None
    detail: str
    data: dict[str, object] = Field(default_factory=dict)
