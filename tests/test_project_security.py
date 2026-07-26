from pathlib import Path

import pytest

from agent.mcp_server.models import MCPServerConfig, ProjectDefinition, Role
from agent.mcp_server.paths import PathAccessDenied, ProjectPathResolver
from agent.mcp_server.registry import ProjectRegistry, UserRegistry


def test_path_resolver_only_allows_explicitly_exposed_folders(tmp_path: Path) -> None:
    root = tmp_path / "project"
    exposed = root / "documents"
    nested = exposed / "chapters" / "drafts"
    private = root / "private"
    nested.mkdir(parents=True)
    private.mkdir()
    (exposed / "allowed.md").write_text("ok", encoding="utf-8")
    (nested / "nested.md").write_text("nested", encoding="utf-8")
    (private / "secret.md").write_text("secret", encoding="utf-8")
    project = ProjectDefinition(
        id="alpha",
        title="Alpha",
        root_path=root,
        exposed_folders=["documents"],
    )
    resolver = ProjectPathResolver()

    assert resolver.resolve(project, "documents/allowed.md").read_text() == "ok"
    assert (
        resolver.resolve(project, "documents/chapters/drafts/nested.md").read_text()
        == "nested"
    )
    with pytest.raises(PathAccessDenied):
        resolver.resolve(project, "private/secret.md")
    with pytest.raises(PathAccessDenied):
        resolver.resolve(project, "../outside.md", must_exist=False)


def test_user_registry_stores_only_token_hash_and_protects_last_owner(
    tmp_path: Path,
) -> None:
    path = tmp_path / "users.json"
    registry = UserRegistry(path)

    owner, token = registry.add("owner@example.com", Role.OWNER)

    assert registry.authenticate(token) == owner
    assert token not in path.read_text(encoding="utf-8")
    assert owner.token_sha256 in path.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="last enabled global owner"):
        registry.remove(owner.user_id)


def test_project_registry_rejects_roots_outside_operator_allowlist(
    tmp_path: Path,
) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    config = MCPServerConfig(
        users_file=tmp_path / "users.json",
        projects_directory=tmp_path / "projects",
        audit_log=tmp_path / "audit.jsonl",
        allowed_project_roots=[allowed],
    )
    registry = ProjectRegistry(config)
    outside = tmp_path / "outside"
    outside.mkdir()

    with pytest.raises(ValueError, match="outside"):
        registry.set(
            ProjectDefinition(
                id="outside",
                title="Outside",
                root_path=outside,
                exposed_folders=[],
            )
        )
