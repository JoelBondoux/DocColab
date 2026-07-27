from __future__ import annotations

from dataclasses import asdict
from typing import Any

from agent.ai.base import AIProvider
from agent.ai.claude_client import ClaudeRewriteClient
from agent.ai.openai_client import OpenAIRewriteClient
from agent.ai.pipeline import RewritePipeline
from agent.config import DocumentConfig, load_config, require_env
from agent.mcp_server.access import AccessController, AccessDenied
from agent.mcp_server.audit import AuditLogger
from agent.mcp_server.file_service import ProjectFileService
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
        self.files = ProjectFileService(config, self.paths)
        self.audit = AuditLogger(
            config.audit_log,
            max_bytes=config.audit_max_bytes,
            backup_count=config.audit_backup_count,
        )

    def begin(
        self,
        tool: str,
        project_id: str,
        role: Role,
        detail: dict[str, Any] | None = None,
    ) -> ProjectDefinition:
        user = current_user()
        try:
            project = self.access.authorize(user, project_id, tool, role)
        except (AccessDenied, KeyError) as exc:
            self.audit.record(
                user_id=user.user_id,
                tool=tool,
                project_id=project_id,
                outcome="denied",
                detail={"error_type": type(exc).__name__},
            )
            raise
        self.audit.record(
            user_id=user.user_id,
            tool=tool,
            project_id=project_id,
            outcome="authorized",
            detail=detail,
        )
        return project

    def begin_global(self, tool: str) -> None:
        user = current_user()
        try:
            self.access.require_global_owner(user)
        except AccessDenied as exc:
            self.audit.record(
                user_id=user.user_id,
                tool=tool,
                project_id=None,
                outcome="denied",
                detail={"error_type": type(exc).__name__},
            )
            raise
        self.audit.record(
            user_id=user.user_id,
            tool=tool,
            project_id=None,
            outcome="authorized",
        )

    def record_outcome(
        self,
        tool: str,
        project_id: str | None,
        error: Exception | None = None,
    ) -> None:
        user = current_user()
        detail = {"error_type": type(error).__name__} if error else None
        self.audit.record(
            user_id=user.user_id,
            tool=tool,
            project_id=project_id,
            outcome="failed" if error else "succeeded",
            detail=detail,
        )

    def read_file(self, project_id: str, path: str) -> ToolResult:
        project = self.begin("doccolab.read_file", project_id, Role.VIEWER, {"path": path})
        return self.files.read(project, path)

    def write_file(self, project_id: str, path: str, content: str) -> ToolResult:
        project = self.begin("doccolab.write_file", project_id, Role.EDITOR, {"path": path})
        return self.files.write(project, path, content)

    def list_files(self, project_id: str, directory: str) -> ToolResult:
        project = self.begin(
            "doccolab.list_files",
            project_id,
            Role.VIEWER,
            {"directory": directory},
        )
        return self.files.list(project, directory)

    def convert_docx_to_md(self, project_id: str, path: str) -> ToolResult:
        project = self.begin(
            "doccolab.convert_docx_to_md",
            project_id,
            Role.EDITOR,
            {"path": path},
        )
        return self.files.docx_to_markdown(project, path)

    def convert_md_to_docx(self, project_id: str, path: str) -> ToolResult:
        project = self.begin(
            "doccolab.convert_md_to_docx",
            project_id,
            Role.EDITOR,
            {"path": path},
        )
        return self.files.markdown_to_docx(project, path)

    def pull_google_doc(self, project_id: str, doc_id: str) -> ToolResult:
        project = self.begin("doccolab.pull_google_doc", project_id, Role.EDITOR)
        runtime = self.runtimes.get(project)
        document = _document(runtime.manager.config.documents, doc_id, "google")
        markdown = runtime.manager.google_markdown(document)
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
        metadata = runtime.manager.google_metadata(document)
        if not runtime.manager.google_drive or not document.google_file_id or not metadata:
            raise RuntimeError("Google document is not configured")
        updated = runtime.manager.replace_google_document(
            document,
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
        markdown = runtime.manager.microsoft_markdown(document)
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
        metadata = runtime.manager.microsoft_metadata(document)
        if not runtime.manager.onedrive or not document.microsoft_item_id or not metadata:
            raise RuntimeError("OneDrive document is not configured")
        updated = runtime.manager.replace_microsoft_document(
            document,
            source.read_bytes(),
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
