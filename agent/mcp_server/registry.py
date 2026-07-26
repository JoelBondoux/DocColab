from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
from contextlib import suppress
from pathlib import Path

from agent.mcp_server.models import (
    MCPServerConfig,
    ProjectDefinition,
    Role,
    UserRecord,
    UsersFile,
)


class UserRegistry:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        if not path.exists():
            self._write(UsersFile())

    def list(self) -> list[UserRecord]:
        return self._load().users

    def get(self, user_id: str) -> UserRecord | None:
        return next((user for user in self.list() if user.user_id == user_id), None)

    def authenticate(self, token: str) -> UserRecord | None:
        candidate = _token_hash(token)
        for user in self.list():
            if user.enabled and secrets.compare_digest(user.token_sha256, candidate):
                return user
        return None

    def add(
        self,
        user_id: str,
        role: Role,
        *,
        display_name: str | None = None,
    ) -> tuple[UserRecord, str]:
        with self._lock:
            registry = self._load()
            if any(user.user_id == user_id for user in registry.users):
                raise ValueError(f"User {user_id!r} already exists")
            token = secrets.token_urlsafe(36)
            record = UserRecord(
                user_id=user_id,
                display_name=display_name,
                role=role,
                token_sha256=_token_hash(token),
            )
            registry.users.append(record)
            self._write(registry)
            return record, token

    def remove(self, user_id: str) -> None:
        with self._lock:
            registry = self._load()
            target = next((user for user in registry.users if user.user_id == user_id), None)
            if not target:
                raise KeyError(user_id)
            remaining = [user for user in registry.users if user.user_id != user_id]
            if target.role == Role.OWNER and not any(
                user.role == Role.OWNER and user.enabled for user in remaining
            ):
                raise ValueError("Cannot remove the last enabled global owner")
            registry.users = remaining
            self._write(registry)

    def set_role(self, user_id: str, role: Role) -> UserRecord:
        with self._lock:
            registry = self._load()
            for index, user in enumerate(registry.users):
                if user.user_id != user_id:
                    continue
                if user.role == Role.OWNER and role != Role.OWNER:
                    other_owner = any(
                        other.user_id != user_id
                        and other.enabled
                        and other.role == Role.OWNER
                        for other in registry.users
                    )
                    if not other_owner:
                        raise ValueError("Cannot demote the last enabled global owner")
                updated = user.model_copy(update={"role": role})
                registry.users[index] = updated
                self._write(registry)
                return updated
            raise KeyError(user_id)

    def rotate_token(self, user_id: str) -> str:
        with self._lock:
            registry = self._load()
            token = secrets.token_urlsafe(36)
            for index, user in enumerate(registry.users):
                if user.user_id == user_id:
                    registry.users[index] = user.model_copy(
                        update={"token_sha256": _token_hash(token)}
                    )
                    self._write(registry)
                    return token
            raise KeyError(user_id)

    def _load(self) -> UsersFile:
        with self._lock:
            return UsersFile.model_validate_json(self.path.read_text(encoding="utf-8"))

    def _write(self, registry: UsersFile) -> None:
        _atomic_json(self.path, registry.model_dump(mode="json"))


class ProjectRegistry:
    def __init__(self, config: MCPServerConfig) -> None:
        self.directory = config.projects_directory
        self.allowed_roots = tuple(path.resolve() for path in config.allowed_project_roots)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def list(self) -> list[ProjectDefinition]:
        projects = []
        with self._lock:
            for path in sorted(self.directory.glob("*.json")):
                project = ProjectDefinition.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
                projects.append(self._validated(project))
        return projects

    def get(self, project_id: str) -> ProjectDefinition:
        path = self.directory / f"{project_id}.json"
        if not path.exists():
            raise KeyError(project_id)
        with self._lock:
            project = ProjectDefinition.model_validate_json(path.read_text(encoding="utf-8"))
        return self._validated(project)

    def set(self, project: ProjectDefinition) -> ProjectDefinition:
        validated = self._validated(project)
        with self._lock:
            _atomic_json(
                self.directory / f"{validated.id}.json",
                validated.model_dump(mode="json"),
            )
        return validated

    def expose_folder(self, project_id: str, folder: str) -> ProjectDefinition:
        project = self.get(project_id)
        relative = _safe_relative(folder)
        folder_path = (project.root_path / relative).resolve()
        if not folder_path.is_dir() or not folder_path.is_relative_to(project.root_path):
            raise ValueError("Exposed folder must be an existing directory inside the project")
        value = relative.as_posix()
        exposed = list(project.exposed_folders)
        if value not in exposed:
            exposed.append(value)
        return self.set(project.model_copy(update={"exposed_folders": exposed}))

    def revoke_folder(self, project_id: str, folder: str) -> ProjectDefinition:
        project = self.get(project_id)
        value = _safe_relative(folder).as_posix()
        exposed = [existing for existing in project.exposed_folders if existing != value]
        return self.set(project.model_copy(update={"exposed_folders": exposed}))

    def _validated(self, project: ProjectDefinition) -> ProjectDefinition:
        root = project.root_path.resolve()
        if not any(root.is_relative_to(allowed) for allowed in self.allowed_roots):
            raise ValueError(
                f"Project root {root} is outside mcp-config allowed_project_roots"
            )
        sync_path = (root / project.sync_config).resolve()
        if not sync_path.is_relative_to(root):
            raise ValueError("Project sync_config escapes the project root")
        return project.model_copy(update={"root_path": root})


def load_server_config(path: Path) -> MCPServerConfig:
    resolved = path.resolve()
    config = MCPServerConfig.model_validate_json(resolved.read_text(encoding="utf-8"))
    base = resolved.parent
    config.users_file = _resolve(base, config.users_file)
    config.projects_directory = _resolve(base, config.projects_directory)
    config.audit_log = _resolve(base, config.audit_log)
    config.allowed_project_roots = [
        _resolve(base, path) for path in config.allowed_project_roots
    ]
    return config


def _resolve(base: Path, value: Path) -> Path:
    return value.resolve() if value.is_absolute() else (base / value).resolve()


def _safe_relative(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("Path must be a safe project-relative path")
    return path


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    with suppress(OSError):
        temporary.chmod(0o600)
    os.replace(temporary, path)
