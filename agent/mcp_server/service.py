from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from agent.ai.base import AIProvider
from agent.ai.claude_client import ClaudeRewriteClient
from agent.ai.openai_client import OpenAIRewriteClient
from agent.ai.pipeline import RewritePipeline
from agent.config import DocumentConfig, load_config, require_env
from agent.conversion.converter import DocumentConverter
from agent.mcp_server.access import AccessController
from agent.mcp_server.audit import AuditLogger
from agent.mcp_server.identity import current_user
from agent.mcp_server.models import (
    MCPServerConfig,
    ProjectDefinition,
    Role,
    ToolResult,
)
from agent.mcp_server.paths import ProjectPathResolver
from agent.mcp_server.registry import ProjectRegistry, UserRegistry
from agent.mcp_server.runtime_cache import ProjectRuntimeCache


class MCPService:
    def __init__(
        self,
        *,
        config: MCPServerConfig,
        users: UserRegistry,
        projects: ProjectRegistry,
        runtimes: ProjectRuntimeCache,
    ) -> None:
        self.config = config
        self.users = users
        self.projects = projects
        self.runtimes = runtimes
        self.access = AccessController(projects)
        self.paths = ProjectPathResolver()
        self.audit = AuditLogger(config.audit_log)

    def begin(
        self,
        tool: str,
        project_id: str,
        role: Role,
        detail: dict[str, Any] | None = None,
    ) -> ProjectDefinition:
        user = current_user()
        project = self.access.authorize(user, project_id, tool, role)
        self.audit.record(
            user_id=user.user_id,
            tool=tool,
            project_id=project_id,
            detail=detail,
        )
        return project

    def begin_global(self, tool: str) -> None:
        user = current_user()
        self.access.require_global_owner(user)
        self.audit.record(user_id=user.user_id, tool=tool, project_id=None)

    def read_file(self, project_id: str, path: str) -> ToolResult:
        project = self.begin("doccolab.read_file", project_id, Role.VIEWER, {"path": path})
        target = self.paths.resolve(project, path)
        if not target.is_file():
            raise ValueError("Path is not a file")
        if target.stat().st_size > self.config.max_read_bytes:
            raise ValueError("File exceeds the configured MCP read limit")
        return ToolResult(
            project_id=project_id,
            detail="File read",
            data={"path": path, "content": target.read_text(encoding="utf-8")},
        )

    def write_file(self, project_id: str, path: str, content: str) -> ToolResult:
        project = self.begin("doccolab.write_file", project_id, Role.EDITOR, {"path": path})
        encoded = content.encode("utf-8")
        if len(encoded) > self.config.max_write_bytes:
            raise ValueError("Content exceeds the configured MCP write limit")
        target = self.paths.resolve(project, path, must_exist=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + f".{os.getpid()}.tmp")
        temporary.write_bytes(encoded)
        os.replace(temporary, target)
        return ToolResult(
            project_id=project_id,
            detail="File written atomically",
            data={"path": path, "bytes": len(encoded)},
        )

    def list_files(self, project_id: str, directory: str) -> ToolResult:
        project = self.begin(
            "doccolab.list_files",
            project_id,
            Role.VIEWER,
            {"directory": directory},
        )
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
            project_id=project_id,
            detail=f"Listed {len(entries)} entries",
            data={"directory": directory, "entries": entries},
        )

    def convert_docx_to_md(self, project_id: str, path: str) -> ToolResult:
        project = self.begin(
            "doccolab.convert_docx_to_md",
            project_id,
            Role.EDITOR,
            {"path": path},
        )
        source = self.paths.resolve(project, path)
        target = self.paths.resolve(
            project,
            str(Path(path).with_suffix(".md")),
            must_exist=False,
        )
        converter = self._converter(project)
        markdown = converter.docx_to_markdown(source.read_bytes())
        target.write_text(markdown, encoding="utf-8")
        return ToolResult(
            project_id=project_id,
            detail="DOCX converted to Markdown",
            data={"path": self.paths.relative(project, target), "content": markdown},
        )

    def convert_md_to_docx(self, project_id: str, path: str) -> ToolResult:
        project = self.begin(
            "doccolab.convert_md_to_docx",
            project_id,
            Role.EDITOR,
            {"path": path},
        )
        source = self.paths.resolve(project, path)
        target = self.paths.resolve(
            project,
            str(Path(path).with_suffix(".docx")),
            must_exist=False,
        )
        converter = self._converter(project)
        content = converter.markdown_to_docx(source.read_text(encoding="utf-8"))
        target.write_bytes(content)
        return ToolResult(
            project_id=project_id,
            detail="Markdown converted to DOCX",
            data={"path": self.paths.relative(project, target), "bytes": len(content)},
        )

    def pull_google_doc(self, project_id: str, doc_id: str) -> ToolResult:
        project = self.begin("doccolab.pull_google_doc", project_id, Role.EDITOR)
        runtime = self.runtimes.get(project)
        document = _document(runtime.manager.config.documents, doc_id, "google")
        markdown = runtime.manager._google_markdown(document)
        target = self.paths.resolve(project, document.markdown_path, must_exist=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(markdown, encoding="utf-8")
        return ToolResult(
            project_id=project_id,
            detail="Google Doc pulled",
            data={"document_id": document.id, "path": document.markdown_path, "content": markdown},
        )

    def push_google_doc(
        self,
        project_id: str,
        doc_id: str,
        docx_path: str,
    ) -> ToolResult:
        project = self.begin("doccolab.push_google_doc", project_id, Role.EDITOR)
        runtime = self.runtimes.get(project)
        document = _document(runtime.manager.config.documents, doc_id, "google")
        source = self.paths.resolve(project, docx_path)
        metadata = runtime.manager._google_metadata(document)
        if not runtime.manager.google_drive or not document.google_file_id or not metadata:
            raise RuntimeError("Google document is not configured")
        updated = runtime.manager.google_drive.replace_google_doc(
            document.google_file_id,
            source.read_bytes(),
            expected_version=metadata.version,
        )
        return ToolResult(
            project_id=project_id,
            detail="Google Doc updated",
            data={"document_id": document.id, "version": updated.version},
        )

    def pull_onedrive_file(self, project_id: str, file_id: str) -> ToolResult:
        project = self.begin("doccolab.pull_onedrive_file", project_id, Role.EDITOR)
        runtime = self.runtimes.get(project)
        document = _document(runtime.manager.config.documents, file_id, "microsoft")
        markdown = runtime.manager._microsoft_markdown(document)
        target = self.paths.resolve(project, document.markdown_path, must_exist=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(markdown, encoding="utf-8")
        return ToolResult(
            project_id=project_id,
            detail="OneDrive document pulled",
            data={"document_id": document.id, "path": document.markdown_path, "content": markdown},
        )

    def push_onedrive_file(
        self,
        project_id: str,
        file_id: str,
        docx_path: str,
    ) -> ToolResult:
        project = self.begin("doccolab.push_onedrive_file", project_id, Role.EDITOR)
        runtime = self.runtimes.get(project)
        document = _document(runtime.manager.config.documents, file_id, "microsoft")
        source = self.paths.resolve(project, docx_path)
        metadata = runtime.manager._microsoft_metadata(document)
        if not runtime.manager.onedrive or not document.microsoft_item_id or not metadata:
            raise RuntimeError("OneDrive document is not configured")
        updated = runtime.manager.onedrive.replace(
            document.microsoft_item_id,
            source.read_bytes(),
            document.microsoft_drive_id,
            expected_etag=metadata.etag,
        )
        return ToolResult(
            project_id=project_id,
            detail="OneDrive document updated",
            data={"document_id": document.id, "etag": updated.etag},
        )

    async def sync_github(
        self,
        project_id: str,
        repo: str,
        branch: str,
    ) -> ToolResult:
        project = self.begin("doccolab.sync_github", project_id, Role.EDITOR)
        runtime = self.runtimes.get(project)
        expected_repo = (
            f"{runtime.manager.config.github.owner}/"
            f"{runtime.manager.config.github.repository}"
        )
        allowed_branches = {
            runtime.manager.config.github.branch,
            *(
                document.github_branch
                for document in runtime.manager.config.documents
                if document.github_branch
            ),
        }
        if repo.casefold() != expected_repo.casefold() or branch not in allowed_branches:
            raise PermissionError("Repository or branch is outside the project mapping")
        results = await runtime.manager.sync_all()
        return ToolResult(
            project_id=project_id,
            detail="GitHub synchronization pass complete",
            data={"results": [asdict(result) for result in results]},
        )

    def run_ai(self, project_id: str, provider_name: str, markdown: str) -> ToolResult:
        tool = f"doccolab.run_{provider_name}_pipeline"
        project = self.begin(tool, project_id, Role.EDITOR)
        ai_config = load_config(project.root_path / project.sync_config).ai
        provider: AIProvider
        if provider_name == "openai":
            provider = OpenAIRewriteClient(
                api_key=require_env("OPENAI_API_KEY"),
                model=ai_config.openai_model,
                max_output_tokens=ai_config.max_output_tokens,
            )
        elif provider_name == "claude":
            provider = ClaudeRewriteClient(
                api_key=require_env("ANTHROPIC_API_KEY"),
                model=ai_config.anthropic_model,
                max_output_tokens=ai_config.max_output_tokens,
            )
        else:
            raise ValueError(provider_name)
        rewritten = RewritePipeline(provider, ai_config).rewrite(markdown)
        return ToolResult(
            project_id=project_id,
            detail=f"{provider_name} rewrite complete",
            data={"markdown": rewritten},
        )

    async def update_document(self, project_id: str, doc_id: str, tool: str) -> ToolResult:
        project = self.begin(tool, project_id, Role.EDITOR)
        runtime = self.runtimes.get(project)
        document = _document(runtime.manager.config.documents, doc_id)
        result = await runtime.manager.sync_document(document.id)
        return ToolResult(
            project_id=project_id,
            detail=result.detail,
            data={
                "document_id": result.document_id,
                "status": result.status.value,
                "source": result.source.value if result.source else None,
                "version": result.version,
            },
        )

    async def roundtrip_github(
        self,
        project_id: str,
        repo: str,
        path: str,
    ) -> ToolResult:
        project = self.begin("doccolab.roundtrip_github", project_id, Role.EDITOR)
        runtime = self.runtimes.get(project)
        expected_repo = (
            f"{runtime.manager.config.github.owner}/"
            f"{runtime.manager.config.github.repository}"
        )
        if repo.casefold() != expected_repo.casefold():
            raise PermissionError("Repository is outside the project mapping")
        document = next(
            (
                document
                for document in runtime.manager.config.documents
                if document.markdown_path == path
            ),
            None,
        )
        if not document:
            raise KeyError(path)
        result = await runtime.manager.sync_document(document.id)
        return ToolResult(
            project_id=project_id,
            detail=result.detail,
            data={"document_id": document.id, "status": result.status.value},
        )

    def list_projects(self) -> ToolResult:
        user = current_user()
        visible: list[tuple[ProjectDefinition, Role]] = []
        for project in self.projects.list():
            role = self.access.role_for(user, project)
            if role is not None:
                visible.append((project, role))
        self.audit.record(user_id=user.user_id, tool="doccolab.list_projects", project_id=None)
        return ToolResult(
            detail=f"{len(visible)} accessible projects",
            data={
                "projects": [
                    {
                        "id": project.id,
                        "title": project.title,
                        "role": role.value,
                    }
                    for project, role in visible
                ]
            },
        )

    def get_project_config(self, project_id: str) -> ToolResult:
        project = self.begin("doccolab.get_project_config", project_id, Role.VIEWER)
        return ToolResult(
            project_id=project_id,
            detail="Project configuration",
            data={"config": project.model_dump(mode="json")},
        )

    def set_project_config(self, project_id: str, value: dict[str, Any]) -> ToolResult:
        user = current_user()
        try:
            existing = self.projects.get(project_id)
        except KeyError:
            self.access.require_global_owner(user)
        else:
            self.access.authorize(
                user,
                project_id,
                "doccolab.set_project_config",
                Role.OWNER,
            )
            if existing.id != project_id:
                raise ValueError("Project id mismatch")
        value["id"] = project_id
        project = self.projects.set(ProjectDefinition.model_validate(value))
        self.audit.record(
            user_id=user.user_id,
            tool="doccolab.set_project_config",
            project_id=project_id,
        )
        return ToolResult(
            project_id=project_id,
            detail="Project configuration saved",
            data={"config": project.model_dump(mode="json")},
        )

    def expose_folder(self, project_id: str, folder_path: str) -> ToolResult:
        self.begin("doccolab.expose_folder", project_id, Role.OWNER)
        project = self.projects.expose_folder(project_id, folder_path)
        return ToolResult(
            project_id=project_id,
            detail="Folder exposed",
            data={"exposed_folders": project.exposed_folders},
        )

    def revoke_folder(self, project_id: str, folder_path: str) -> ToolResult:
        self.begin("doccolab.revoke_folder", project_id, Role.OWNER)
        project = self.projects.revoke_folder(project_id, folder_path)
        return ToolResult(
            project_id=project_id,
            detail="Folder exposure revoked",
            data={"exposed_folders": project.exposed_folders},
        )

    def list_users(self) -> ToolResult:
        self.begin_global("doccolab.list_users")
        users = [
            {
                "user_id": user.user_id,
                "display_name": user.display_name,
                "role": user.role.value,
                "enabled": user.enabled,
            }
            for user in self.users.list()
        ]
        return ToolResult(detail=f"{len(users)} users", data={"users": users})

    def add_user(self, user_id: str, role: Role) -> ToolResult:
        self.begin_global("doccolab.add_user")
        record, token = self.users.add(user_id, role)
        return ToolResult(
            detail="User added; this bearer token is shown only once",
            data={"user_id": record.user_id, "role": record.role.value, "token": token},
        )

    def remove_user(self, user_id: str) -> ToolResult:
        self.begin_global("doccolab.remove_user")
        self.users.remove(user_id)
        return ToolResult(detail="User removed", data={"user_id": user_id})

    def set_user_role(self, user_id: str, role: Role) -> ToolResult:
        self.begin_global("doccolab.set_user_role")
        record = self.users.set_role(user_id, role)
        return ToolResult(
            detail="User role updated",
            data={"user_id": record.user_id, "role": record.role.value},
        )

    @staticmethod
    def _converter(project: ProjectDefinition) -> DocumentConverter:
        config = load_config(project.root_path / project.sync_config)
        return DocumentConverter(config.conversion)


def _document(
    documents: list[DocumentConfig],
    identifier: str,
    surface: str | None = None,
) -> DocumentConfig:
    for document in documents:
        identifiers = {document.id}
        if surface in (None, "google") and document.google_file_id:
            identifiers.add(document.google_file_id)
        if surface in (None, "microsoft") and document.microsoft_item_id:
            identifiers.add(document.microsoft_item_id)
        if identifier in identifiers:
            if surface == "google" and not document.google_file_id:
                continue
            if surface == "microsoft" and not document.microsoft_item_id:
                continue
            return document
    raise KeyError(identifier)
