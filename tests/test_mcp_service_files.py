from pathlib import Path

import pytest

from agent.mcp_server.identity import reset_current_user, set_current_user
from agent.mcp_server.models import (
    MCPServerConfig,
    ProjectDefinition,
    Role,
    UserRecord,
)
from agent.mcp_server.registry import ProjectRegistry, UserRegistry
from agent.mcp_server.runtime_cache import ProjectRuntimeCache
from agent.mcp_server.service import MCPService


def test_file_tools_are_project_scoped_atomic_and_audited(tmp_path: Path) -> None:
    root = tmp_path / "root"
    documents = root / "documents"
    documents.mkdir(parents=True)
    config = MCPServerConfig(
        users_file=tmp_path / "users.json",
        projects_directory=tmp_path / "projects",
        audit_log=tmp_path / "audit.jsonl",
        allowed_project_roots=[root],
    )
    users = UserRegistry(config.users_file)
    projects = ProjectRegistry(config)
    projects.set(
        ProjectDefinition(
            id="alpha",
            title="Alpha",
            root_path=root,
            exposed_folders=["documents"],
            members={"editor@example.com": Role.EDITOR},
        )
    )
    service = MCPService(
        config=config,
        users=users,
        projects=projects,
        runtimes=ProjectRuntimeCache(),
    )
    identity = UserRecord(
        user_id="editor@example.com",
        role=Role.VIEWER,
        token_sha256="a" * 64,
    )
    context = set_current_user(identity)
    try:
        written = service.write_file("alpha", "documents/note.md", "# Note\n")
        read = service.read_file("alpha", "documents/note.md")
        listed = service.list_files("alpha", "documents")
        with pytest.raises(PermissionError):
            service.write_file("alpha", "private/note.md", "secret")
    finally:
        reset_current_user(context)

    assert written.data["bytes"] == 7
    assert read.data["content"] == "# Note\n"
    assert listed.data["entries"][0]["path"] == "documents/note.md"
    audit = config.audit_log.read_text(encoding="utf-8")
    assert "doccolab.write_file" in audit
    assert "editor@example.com" in audit
