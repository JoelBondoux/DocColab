from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.mcp_server.models import MCPServerConfig, ProjectDefinition
from agent.mcp_server.runtime_cache import ProjectRuntimeCache, SyncSupervisor


class FakeRuntime:
    def __init__(self) -> None:
        self.closed = False
        self.manager = SimpleNamespace(stop=lambda: None)

    def close(self) -> None:
        self.closed = True


def test_runtime_cache_reuses_fingerprints_and_closes(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    project = ProjectDefinition(id="project", title="Project", root_path=tmp_path)
    runtime = FakeRuntime()
    monkeypatch.setattr("agent.mcp_server.runtime_cache.load_config", lambda _: object())
    monkeypatch.setattr("agent.mcp_server.runtime_cache.build_runtime", lambda _: runtime)
    cache = ProjectRuntimeCache()

    assert cache.get(project) is runtime
    assert cache.get(project) is runtime
    assert len(cache.fingerprint(project)) == 64
    cache.invalidate(project.id)
    assert runtime.closed
    cache.close()


@pytest.mark.asyncio
async def test_disabled_supervisor_waits_until_stopped(tmp_path: Path) -> None:
    config = MCPServerConfig(
        users_file=tmp_path / "users.json",
        projects_directory=tmp_path / "projects",
        audit_log=tmp_path / "audit.jsonl",
        allowed_project_roots=[tmp_path],
        run_sync_agents=False,
    )
    supervisor = SyncSupervisor(
        server_config=config,
        projects=SimpleNamespace(list=lambda: []) ,  # type: ignore[arg-type]
        runtimes=ProjectRuntimeCache(),
    )

    supervisor.stop()
    await supervisor.run()
