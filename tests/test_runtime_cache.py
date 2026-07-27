from __future__ import annotations

import asyncio
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


class DrainingManager:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.cancelled = False
        self.stopped = False

    async def run_forever(self) -> None:
        self.started.set()
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise

    def stop(self) -> None:
        self.stopped = True
        self.release.set()


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

    assert supervisor.status()["ready"] is True


@pytest.mark.asyncio
async def test_project_stop_drains_in_flight_sync_before_closing(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    project = ProjectDefinition(id="project", title="Project", root_path=tmp_path)
    manager = DrainingManager()
    runtime = FakeRuntime()
    runtime.manager = manager
    cache = ProjectRuntimeCache()
    cache._entries[project.id] = runtime  # noqa: SLF001
    config = MCPServerConfig(
        users_file=tmp_path / "users.json",
        projects_directory=tmp_path / "projects",
        audit_log=tmp_path / "audit.jsonl",
        allowed_project_roots=[tmp_path],
    )
    supervisor = SyncSupervisor(
        server_config=config,
        projects=SimpleNamespace(list=lambda: [project]),  # type: ignore[arg-type]
        runtimes=cache,
    )
    task = asyncio.create_task(manager.run_forever())
    supervisor.tasks[project.id] = task
    await manager.started.wait()

    await supervisor._stop_project(project.id)  # noqa: SLF001

    assert manager.stopped
    assert not manager.cancelled
    assert task.done()
    assert runtime.closed


def test_supervisor_readiness_reports_missing_projects(tmp_path: Path) -> None:
    project = ProjectDefinition(id="project", title="Project", root_path=tmp_path)
    config = MCPServerConfig(
        users_file=tmp_path / "users.json",
        projects_directory=tmp_path / "projects",
        audit_log=tmp_path / "audit.jsonl",
        allowed_project_roots=[tmp_path],
    )
    supervisor = SyncSupervisor(
        server_config=config,
        projects=SimpleNamespace(list=lambda: [project]),  # type: ignore[arg-type]
        runtimes=ProjectRuntimeCache(),
    )

    status = supervisor.status()

    assert status["ready"] is False
    assert status["missing_projects"] == ["project"]
