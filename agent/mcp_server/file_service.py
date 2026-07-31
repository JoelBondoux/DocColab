from __future__ import annotations

import os
from pathlib import Path

from agent.config import load_config
from agent.conversion.converter import DocumentConverter
from agent.mcp_server.models import MCPServerConfig, ProjectDefinition, ToolResult
from agent.mcp_server.paths import ProjectPathResolver


class ProjectFileService:
    """Project-scoped local file and conversion operations."""

    def __init__(self, config: MCPServerConfig, paths: ProjectPathResolver) -> None:
        self.config = config
        self.paths = paths

    def read(self, project: ProjectDefinition, path: str) -> ToolResult:
        target = self.paths.resolve(project, path)
        if not target.is_file():
            raise ValueError("Path is not a file")
        if target.stat().st_size > self.config.max_read_bytes:
            raise ValueError("File exceeds the configured MCP read limit")
        return ToolResult(
            project_id=project.id,
            detail="File read",
            data={"path": path, "content": target.read_text(encoding="utf-8")},
        )

    def write(self, project: ProjectDefinition, path: str, content: str) -> ToolResult:
        encoded = content.encode("utf-8")
        if len(encoded) > self.config.max_write_bytes:
            raise ValueError("Content exceeds the configured MCP write limit")
        target = self.paths.resolve(project, path, must_exist=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + f".{os.getpid()}.tmp")
        temporary.write_bytes(encoded)
        os.replace(temporary, target)
        return ToolResult(
            project_id=project.id,
            detail="File written atomically",
            data={"path": path, "bytes": len(encoded)},
        )

    def list(self, project: ProjectDefinition, directory: str) -> ToolResult:
        target = self.paths.resolve(project, directory)
        if not target.is_dir():
            raise ValueError("Path is not a directory")
        entries = [
            {
                "name": child.name,
                "path": self.paths.relative(project, child),
                "type": "directory" if child.is_dir() else "file",
                "size": child.stat().st_size if child.is_file() else None,
            }
            for child in sorted(target.iterdir(), key=lambda value: value.name.lower())
        ]
        return ToolResult(
            project_id=project.id,
            detail=f"Listed {len(entries)} entries",
            data={"directory": directory, "entries": entries},
        )

    def docx_to_markdown(self, project: ProjectDefinition, path: str) -> ToolResult:
        source = self.paths.resolve(project, path)
        target = self.paths.resolve(
            project,
            str(Path(path).with_suffix(".md")),
            must_exist=False,
        )
        markdown = self._converter(project).docx_to_markdown(source.read_bytes())
        target.write_text(markdown, encoding="utf-8")
        return ToolResult(
            project_id=project.id,
            detail="DOCX converted to Markdown",
            data={"path": self.paths.relative(project, target), "content": markdown},
        )

    def markdown_to_docx(self, project: ProjectDefinition, path: str) -> ToolResult:
        source = self.paths.resolve(project, path)
        target = self.paths.resolve(
            project,
            str(Path(path).with_suffix(".docx")),
            must_exist=False,
        )
        content = self._converter(project).markdown_to_docx(
            source.read_text(encoding="utf-8")
        )
        target.write_bytes(content)
        return ToolResult(
            project_id=project.id,
            detail="Markdown converted to DOCX",
            data={"path": self.paths.relative(project, target), "bytes": len(content)},
        )

    @staticmethod
    def _converter(project: ProjectDefinition) -> DocumentConverter:
        config = load_config(project.root_path / project.sync_config)
        return DocumentConverter(config.conversion)
