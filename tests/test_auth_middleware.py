from pathlib import Path

import httpx
import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from agent.mcp_server.auth_middleware import BearerAuthMiddleware
from agent.mcp_server.identity import current_user
from agent.mcp_server.models import Role
from agent.mcp_server.registry import UserRegistry


@pytest.mark.asyncio
async def test_bearer_auth_rejects_missing_token_and_sets_request_identity(
    tmp_path: Path,
) -> None:
    users = UserRegistry(tmp_path / "users.json")
    _, token = users.add("reader@example.com", Role.VIEWER)

    async def whoami(_: object) -> JSONResponse:
        return JSONResponse({"user_id": current_user().user_id})

    inner = Starlette(routes=[Route("/mcp", whoami)])
    app = BearerAuthMiddleware(inner, users)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        unauthorized = await client.get("/mcp")
        authorized = await client.get(
            "/mcp", headers={"Authorization": f"Bearer {token}"}
        )

    assert unauthorized.status_code == 401
    assert unauthorized.headers["www-authenticate"] == "Bearer"
    assert authorized.status_code == 200
    assert authorized.json() == {"user_id": "reader@example.com"}
