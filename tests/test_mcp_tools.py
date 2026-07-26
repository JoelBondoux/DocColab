from unittest.mock import Mock

import pytest
from mcp.server.fastmcp import FastMCP

from agent.mcp_server.tools import register_tools


@pytest.mark.asyncio
async def test_all_required_mcp_tools_are_registered_with_json_schemas() -> None:
    mcp = FastMCP("test", stateless_http=True, json_response=True)
    register_tools(mcp, Mock())

    tools = await mcp.list_tools()
    by_name = {tool.name: tool for tool in tools}
    expected = {
        "doccolab.read_file",
        "doccolab.write_file",
        "doccolab.list_files",
        "doccolab.convert_docx_to_md",
        "doccolab.convert_md_to_docx",
        "doccolab.pull_google_doc",
        "doccolab.push_google_doc",
        "doccolab.pull_onedrive_file",
        "doccolab.push_onedrive_file",
        "doccolab.sync_github",
        "doccolab.run_claude_pipeline",
        "doccolab.run_openai_pipeline",
        "doccolab.update_document",
        "doccolab.roundtrip_google_docs",
        "doccolab.roundtrip_onedrive",
        "doccolab.roundtrip_github",
        "doccolab.list_projects",
        "doccolab.get_project_config",
        "doccolab.set_project_config",
        "doccolab.expose_folder",
        "doccolab.revoke_folder",
        "doccolab.list_users",
        "doccolab.add_user",
        "doccolab.remove_user",
        "doccolab.set_user_role",
    }

    assert set(by_name) == expected
    assert by_name["doccolab.read_file"].inputSchema["required"] == [
        "project_id",
        "path",
    ]
    assert by_name["doccolab.write_file"].inputSchema["properties"]["content"][
        "type"
    ] == "string"
    role_schema = by_name["doccolab.set_user_role"].inputSchema
    assert role_schema["properties"]["role"]["$ref"] == "#/$defs/Role"
    assert role_schema["$defs"]["Role"]["enum"] == ["viewer", "editor", "owner"]
