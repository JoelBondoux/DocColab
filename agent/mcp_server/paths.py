from __future__ import annotations

from pathlib import Path

from agent.mcp_server.models import ProjectDefinition


class ProjectPathResolver:
    """Resolves paths only when they remain inside an explicitly exposed folder."""

    def resolve(
        self,
        project: ProjectDefinition,
        value: str,
        *,
        must_exist: bool = True,
    ) -> Path:
        relative = Path(value)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise PathAccessDenied("Path must be project-relative and cannot contain '..'")
        project_root = project.root_path.resolve(strict=False)
        candidate = (project_root / relative).resolve(strict=False)
        if candidate != project_root and not candidate.is_relative_to(project_root):
            raise PathAccessDenied("Path resolves outside the project root")
        allowed = [
            (project_root / exposed).resolve(strict=False)
            for exposed in project.exposed_folders
        ]
        if not any(candidate == root or candidate.is_relative_to(root) for root in allowed):
            raise PathAccessDenied("Path is outside this project's exposed folders")
        if must_exist and not candidate.exists():
            raise FileNotFoundError(candidate)
        return candidate

    def relative(self, project: ProjectDefinition, path: Path) -> str:
        return path.resolve().relative_to(project.root_path).as_posix()


class PathAccessDenied(PermissionError):
    pass
