from pathlib import Path

import httpx
import pytest

from agent.mcp_server.main import create_application
from agent.mcp_server.models import MCPServerConfig, Role
from agent.mcp_server.registry import ProjectRegistry, UserRegistry
from agent.mcp_server.runtime_cache import ProjectRuntimeCache


@pytest.mark.asyncio
async def test_streamable_http_requires_bearer_and_accepts_mcp_initialize(
    tmp_path: Path,
) -> None:
    allowed = tmp_path / "projects-root"
    allowed.mkdir()
    config = MCPServerConfig(
        users_file=tmp_path / "users.json",
        projects_directory=tmp_path / "projects",
        audit_log=tmp_path / "audit.jsonl",
        allowed_project_roots=[allowed],
        run_sync_agents=False,
    )
    users = UserRegistry(config.users_file)
    _, token = users.add("owner@example.com", Role.OWNER)
    projects = ProjectRegistry(config)
    runtimes = ProjectRuntimeCache()
    application = create_application(config, users, projects, runtimes)
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "1.0"},
        },
    }
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }

    inner_app = application.app.app
    async with inner_app.router.lifespan_context(inner_app):
        transport = httpx.ASGITransport(app=application.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://127.0.0.1:8765",
        ) as client:
            unauthorized = await client.post("/mcp", headers=headers, json=request)
            authorized = await client.post(
                "/mcp",
                headers={**headers, "Authorization": f"Bearer {token}"},
                json=request,
            )
            rebound = await client.post(
                "/mcp",
                headers={
                    **headers,
                    "Authorization": f"Bearer {token}",
                    "Host": "attacker.example",
                },
                json=request,
            )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json()["result"]["serverInfo"]["name"] == "DocColab"
    assert rebound.status_code == 421
