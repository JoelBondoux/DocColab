from __future__ import annotations

import asyncio
import hashlib
import logging
import threading
from contextlib import suppress

from agent.config import load_config
from agent.mcp_server.models import MCPServerConfig, ProjectDefinition
from agent.mcp_server.registry import ProjectRegistry
from agent.runtime import Runtime, build_runtime

logger = logging.getLogger(__name__)


class ProjectRuntimeCache:
    def __init__(self) -> None:
        self._entries: dict[str, Runtime] = {}
        self._lock = threading.RLock()

    def get(self, project: ProjectDefinition) -> Runtime:
        with self._lock:
            existing = self._entries.get(project.id)
            if existing:
                return existing
            config_path = (project.root_path / project.sync_config).resolve()
            runtime = build_runtime(load_config(config_path))
            self._entries[project.id] = runtime
            return runtime

    def invalidate(self, project_id: str) -> None:
        with self._lock:
            runtime = self._entries.pop(project_id, None)
        if runtime:
            runtime.manager.stop()
            runtime.close()

    def close(self) -> None:
        with self._lock:
            project_ids = list(self._entries)
        for project_id in project_ids:
            self.invalidate(project_id)

    @staticmethod
    def fingerprint(project: ProjectDefinition) -> str:
        config_path = (project.root_path / project.sync_config).resolve()
        config_stat = config_path.stat()
        value = (
            project.model_dump_json()
            + f":{config_stat.st_mtime_ns}:{config_stat.st_size}"
        )
        return hashlib.sha256(value.encode("utf-8")).hexdigest()


class SyncSupervisor:
    def __init__(
        self,
        *,
        server_config: MCPServerConfig,
        projects: ProjectRegistry,
        runtimes: ProjectRuntimeCache,
    ) -> None:
        self.server_config = server_config
        self.projects = projects
        self.runtimes = runtimes
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self.fingerprints: dict[str, str] = {}
        self.stop_event = asyncio.Event()

    async def run(self) -> None:
        if not self.server_config.run_sync_agents:
            await self.stop_event.wait()
            return
        while not self.stop_event.is_set():
            active = {project.id: project for project in self.projects.list() if project.enabled}
            for project_id in set(self.tasks) - set(active):
                await self._stop_project(project_id)
            for project_id, project in active.items():
                fingerprint = self.runtimes.fingerprint(project)
                task = self.tasks.get(project_id)
                if task and (task.done() or self.fingerprints.get(project_id) != fingerprint):
                    if task.done():
                        error = None if task.cancelled() else task.exception()
                        if error:
                            logger.error("Sync agent stopped for %s: %r", project_id, error)
                    await self._stop_project(project_id)
                    task = None
                if task is None:
                    try:
                        runtime = await asyncio.to_thread(self.runtimes.get, project)
                    except Exception:
                        logger.exception("Unable to start project runtime %s", project_id)
                        continue
                    self.tasks[project_id] = asyncio.create_task(
                        runtime.manager.run_forever(),
                        name=f"doccolab-sync-{project_id}",
                    )
                    self.fingerprints[project_id] = fingerprint
            with suppress(TimeoutError):
                await asyncio.wait_for(
                    self.stop_event.wait(),
                    timeout=self.server_config.hot_reload_seconds,
                )
        for project_id in list(self.tasks):
            await self._stop_project(project_id)

    def stop(self) -> None:
        self.stop_event.set()

    def status(self) -> dict[str, object]:
        if not self.server_config.run_sync_agents:
            return {
                "ready": True,
                "sync_agents_enabled": False,
                "active_projects": 0,
                "running_projects": 0,
                "missing_projects": [],
                "failed_projects": [],
            }
        try:
            active = sorted(
                project.id for project in self.projects.list() if project.enabled
            )
        except Exception as exc:
            return {
                "ready": False,
                "sync_agents_enabled": True,
                "active_projects": 0,
                "running_projects": 0,
                "missing_projects": [],
                "failed_projects": [],
                "registry_error": type(exc).__name__,
            }
        failed = sorted(
            project_id
            for project_id, task in self.tasks.items()
            if task.done() and (task.cancelled() or task.exception() is not None)
        )
        running = sorted(
            project_id for project_id, task in self.tasks.items() if not task.done()
        )
        missing = sorted(set(active) - set(self.tasks))
        return {
            "ready": not missing and not failed,
            "sync_agents_enabled": True,
            "active_projects": len(active),
            "running_projects": len(running),
            "missing_projects": missing,
            "failed_projects": failed,
        }

    async def _stop_project(self, project_id: str) -> None:
        task = self.tasks.get(project_id)
        runtime = self.runtimes._entries.get(project_id)
        if runtime:
            runtime.manager.stop()
        if task:
            await asyncio.gather(task, return_exceptions=True)
        self.tasks.pop(project_id, None)
        self.fingerprints.pop(project_id, None)
        await asyncio.to_thread(self.runtimes.invalidate, project_id)
