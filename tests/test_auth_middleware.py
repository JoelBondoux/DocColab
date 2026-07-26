from pathlib import Path

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from agent.mcp_server.auth_middleware import BearerAuthMiddleware
from agent.mcp_server.identity import current_user
from agent.mcp_server.models import Role
from agent.mcp_server.registry import UserRegistry


def test_bearer_auth_rejects_missing_token_and_sets_request_identity(
    tmp_path: Path,
) -> None:
    users = UserRegistry(tmp_path / "users.json")
    _, token = users.add("reader@example.com", Role.VIEWER)

    async def whoami(_: object) -> JSONResponse:
        return JSONResponse({"user_id": current_user().user_id})

    inner = Starlette(routes=[Route("/mcp", whoami)])
    app = BearerAuthMiddleware(inner, users)
    client = TestClient(app)

    unauthorized = client.get("/mcp")
    authorized = client.get("/mcp", headers={"Authorization": f"Bearer {token}"})

    assert unauthorized.status_code == 401
    assert unauthorized.headers["www-authenticate"] == "Bearer"
    assert authorized.status_code == 200
    assert authorized.json() == {"user_id": "reader@example.com"}
