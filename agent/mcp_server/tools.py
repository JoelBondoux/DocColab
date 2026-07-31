from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from mcp.server.fastmcp import FastMCP

from agent.mcp_server.models import Role, ToolResult
from agent.mcp_server.service import MCPService

T = TypeVar("T")


def _invoke(
    service: MCPService,
    tool: str,
    project_id: str | None,
    operation: Callable[[], T],
) -> T:
    try:
        result = operation()
    except Exception as exc:
        service.record_outcome(tool, project_id, exc)
        raise
    service.record_outcome(tool, project_id)
    return result


async def _invoke_async(
    service: MCPService,
    tool: str,
    project_id: str | None,
    operation: Callable[[], Awaitable[T]],
) -> T:
    try:
        result = await operation()
    except Exception as exc:
        service.record_outcome(tool, project_id, exc)
        raise
    service.record_outcome(tool, project_id)
    return result


def register_tools(mcp: FastMCP, service: MCPService) -> None:
    """Register the complete DocColab tool surface.

    FastMCP derives each tool's JSON Schema from these type annotations and docstrings.
    """

    @mcp.tool(name="doccolab.read_file")
    def read_file(project_id: str, path: str) -> ToolResult:
        """Read a UTF-8 file from one exposed project folder."""
        return _invoke(
            service,
            "doccolab.read_file",
            project_id,
            lambda: service.read_file(project_id, path),
        )

    @mcp.tool(name="doccolab.write_file")
    def write_file(project_id: str, path: str, content: str) -> ToolResult:
        """Atomically write a UTF-8 file inside an exposed project folder."""
        return _invoke(
            service,
            "doccolab.write_file",
            project_id,
            lambda: service.write_file(project_id, path, content),
        )

    @mcp.tool(name="doccolab.list_files")
    def list_files(project_id: str, directory: str) -> ToolResult:
        """List immediate children of an exposed project directory."""
        return _invoke(
            service,
            "doccolab.list_files",
            project_id,
            lambda: service.list_files(project_id, directory),
        )

    @mcp.tool(name="doccolab.convert_docx_to_md")
    def convert_docx_to_md(project_id: str, path: str) -> ToolResult:
        """Convert an exposed DOCX file to a sibling Markdown file."""
        return _invoke(
            service,
            "doccolab.convert_docx_to_md",
            project_id,
            lambda: service.convert_docx_to_md(project_id, path),
        )

    @mcp.tool(name="doccolab.convert_md_to_docx")
    def convert_md_to_docx(project_id: str, path: str) -> ToolResult:
        """Convert an exposed Markdown file to a sibling DOCX file."""
        return _invoke(
            service,
            "doccolab.convert_md_to_docx",
            project_id,
            lambda: service.convert_md_to_docx(project_id, path),
        )

    @mcp.tool(name="doccolab.pull_google_doc")
    def pull_google_doc(project_id: str, doc_id: str) -> ToolResult:
        """Pull a configured Google Doc into its canonical local Markdown path."""
        return _invoke(
            service,
            "doccolab.pull_google_doc",
            project_id,
            lambda: service.pull_google_doc(project_id, doc_id),
        )

    @mcp.tool(name="doccolab.push_google_doc")
    def push_google_doc(project_id: str, doc_id: str, docx_path: str) -> ToolResult:
        """Replace a configured Google Doc from an exposed DOCX file."""
        return _invoke(
            service,
            "doccolab.push_google_doc",
            project_id,
            lambda: service.push_google_doc(project_id, doc_id, docx_path),
        )

    @mcp.tool(name="doccolab.pull_onedrive_file")
    def pull_onedrive_file(project_id: str, file_id: str) -> ToolResult:
        """Pull a configured OneDrive Word file into canonical local Markdown."""
        return _invoke(
            service,
            "doccolab.pull_onedrive_file",
            project_id,
            lambda: service.pull_onedrive_file(project_id, file_id),
        )

    @mcp.tool(name="doccolab.push_onedrive_file")
    def push_onedrive_file(
        project_id: str,
        file_id: str,
        docx_path: str,
    ) -> ToolResult:
        """Replace a configured OneDrive Word file from an exposed DOCX file."""
        return _invoke(
            service,
            "doccolab.push_onedrive_file",
            project_id,
            lambda: service.push_onedrive_file(project_id, file_id, docx_path),
        )

    @mcp.tool(name="doccolab.sync_github")
    async def sync_github(project_id: str, repo: str, branch: str) -> ToolResult:
        """Run a synchronization pass for the project's configured GitHub mapping."""
        return await _invoke_async(
            service,
            "doccolab.sync_github",
            project_id,
            lambda: service.sync_github(project_id, repo, branch),
        )

    @mcp.tool(name="doccolab.run_claude_pipeline")
    def run_claude_pipeline(project_id: str, md_text: str) -> ToolResult:
        """Rewrite Markdown with the project's Claude model and pipeline rules."""
        return _invoke(
            service,
            "doccolab.run_claude_pipeline",
            project_id,
            lambda: service.run_ai(project_id, "claude", md_text),
        )

    @mcp.tool(name="doccolab.run_openai_pipeline")
    def run_openai_pipeline(project_id: str, md_text: str) -> ToolResult:
        """Rewrite Markdown with the project's OpenAI model and pipeline rules."""
        return _invoke(
            service,
            "doccolab.run_openai_pipeline",
            project_id,
            lambda: service.run_ai(project_id, "openai", md_text),
        )

    @mcp.tool(name="doccolab.update_document")
    async def update_document(project_id: str, doc_id: str) -> ToolResult:
        """Synchronize one configured document across every mapped surface."""
        return await _invoke_async(
            service,
            "doccolab.update_document",
            project_id,
            lambda: service.update_document(
                project_id,
                doc_id,
                "doccolab.update_document",
            ),
        )

    @mcp.tool(name="doccolab.roundtrip_google_docs")
    async def roundtrip_google_docs(project_id: str, doc_id: str) -> ToolResult:
        """Run Google Docs to GitHub to AI to Google Docs for one document."""
        return await _invoke_async(
            service,
            "doccolab.roundtrip_google_docs",
            project_id,
            lambda: service.update_document(
                project_id,
                doc_id,
                "doccolab.roundtrip_google_docs",
            ),
        )

    @mcp.tool(name="doccolab.roundtrip_onedrive")
    async def roundtrip_onedrive(project_id: str, file_id: str) -> ToolResult:
        """Run OneDrive to GitHub to AI to OneDrive for one document."""
        return await _invoke_async(
            service,
            "doccolab.roundtrip_onedrive",
            project_id,
            lambda: service.update_document(
                project_id,
                file_id,
                "doccolab.roundtrip_onedrive",
            ),
        )

    @mcp.tool(name="doccolab.roundtrip_github")
    async def roundtrip_github(project_id: str, repo: str, path: str) -> ToolResult:
        """Propagate one configured canonical GitHub Markdown path to its surfaces."""
        return await _invoke_async(
            service,
            "doccolab.roundtrip_github",
            project_id,
            lambda: service.roundtrip_github(project_id, repo, path),
        )

    @mcp.tool(name="doccolab.list_projects")
    def list_projects() -> ToolResult:
        """List projects visible to the authenticated user."""
        return _invoke(
            service,
            "doccolab.list_projects",
            None,
            service.list_projects,
        )

    @mcp.tool(name="doccolab.get_project_config")
    def get_project_config(project_id: str) -> ToolResult:
        """Get a visible project's non-secret configuration."""
        return _invoke(
            service,
            "doccolab.get_project_config",
            project_id,
            lambda: service.get_project_config(project_id),
        )

    @mcp.tool(name="doccolab.set_project_config")
    def set_project_config(project_id: str, config: dict[str, Any]) -> ToolResult:
        """Create or replace a project configuration after owner validation."""
        return _invoke(
            service,
            "doccolab.set_project_config",
            project_id,
            lambda: service.set_project_config(project_id, config),
        )

    @mcp.tool(name="doccolab.expose_folder")
    def expose_folder(project_id: str, folder_path: str) -> ToolResult:
        """Expose an existing project-relative folder to allowed MCP tools."""
        return _invoke(
            service,
            "doccolab.expose_folder",
            project_id,
            lambda: service.expose_folder(project_id, folder_path),
        )

    @mcp.tool(name="doccolab.revoke_folder")
    def revoke_folder(project_id: str, folder_path: str) -> ToolResult:
        """Revoke MCP access to one project-relative folder."""
        return _invoke(
            service,
            "doccolab.revoke_folder",
            project_id,
            lambda: service.revoke_folder(project_id, folder_path),
        )

    @mcp.tool(name="doccolab.list_users")
    def list_users() -> ToolResult:
        """List users without returning bearer token hashes."""
        return _invoke(service, "doccolab.list_users", None, service.list_users)

    @mcp.tool(name="doccolab.add_user")
    def add_user(user_id: str, role: Role) -> ToolResult:
        """Add a user and return a new bearer token exactly once."""
        return _invoke(
            service,
            "doccolab.add_user",
            None,
            lambda: service.add_user(user_id, role),
        )

    @mcp.tool(name="doccolab.remove_user")
    def remove_user(user_id: str) -> ToolResult:
        """Remove a user; the final global owner cannot be removed."""
        return _invoke(
            service,
            "doccolab.remove_user",
            None,
            lambda: service.remove_user(user_id),
        )

    @mcp.tool(name="doccolab.set_user_role")
    def set_user_role(user_id: str, role: Role) -> ToolResult:
        """Change a user's global role."""
        return _invoke(
            service,
            "doccolab.set_user_role",
            None,
            lambda: service.set_user_role(user_id, role),
        )
