from pathlib import Path

import pytest

from agent.mcp_server.access import AccessController, AccessDenied
from agent.mcp_server.models import (
    MCPServerConfig,
    ProjectDefinition,
    Role,
    UserRecord,
)
from agent.mcp_server.registry import ProjectRegistry


def _user(user_id: str, role: Role) -> UserRecord:
    return UserRecord(user_id=user_id, role=role, token_sha256="a" * 64)


def test_project_role_and_tool_allowlist_are_both_required(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    registry = ProjectRegistry(
        MCPServerConfig(
            users_file=tmp_path / "users.json",
            projects_directory=tmp_path / "projects",
            audit_log=tmp_path / "audit.jsonl",
            allowed_project_roots=[root],
        )
    )
    registry.set(
        ProjectDefinition(
            id="alpha",
            title="Alpha",
            root_path=root,
            members={"editor@example.com": Role.EDITOR},
            allowed_tools=["doccolab.read_file"],
        )
    )
    access = AccessController(registry)
    editor = _user("editor@example.com", Role.EDITOR)

    assert access.authorize(
        editor,
        "alpha",
        "doccolab.read_file",
        Role.VIEWER,
    ).id == "alpha"
    with pytest.raises(AccessDenied, match="disabled"):
        access.authorize(
            editor,
            "alpha",
            "doccolab.write_file",
            Role.EDITOR,
        )
    with pytest.raises(AccessDenied, match="requires owner"):
        access.authorize(
            editor,
            "alpha",
            "doccolab.read_file",
            Role.OWNER,
        )


def test_global_role_caps_project_membership_role(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    registry = ProjectRegistry(
        MCPServerConfig(
            users_file=tmp_path / "users.json",
            projects_directory=tmp_path / "projects",
            audit_log=tmp_path / "audit.jsonl",
            allowed_project_roots=[root],
        )
    )
    project = registry.set(
        ProjectDefinition(
            id="alpha",
            title="Alpha",
            root_path=root,
            members={
                "viewer@example.com": Role.OWNER,
                "editor@example.com": Role.OWNER,
            },
        )
    )
    access = AccessController(registry)

    assert access.role_for(_user("viewer@example.com", Role.VIEWER), project) == Role.VIEWER
    assert access.role_for(_user("editor@example.com", Role.EDITOR), project) == Role.EDITOR
    assert access.role_for(_user("global-owner@example.com", Role.OWNER), project) == Role.OWNER
    with pytest.raises(AccessDenied, match="requires editor"):
        access.authorize(
            _user("viewer@example.com", Role.VIEWER),
            "alpha",
            "doccolab.write_file",
            Role.EDITOR,
        )
