from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

from agent.mcp_server.identity import reset_current_user, set_current_user
from agent.mcp_server.registry import UserRegistry


class BearerAuthMiddleware:
    """Minimal ASGI bearer authentication layered inside the Tailscale boundary."""

    def __init__(
        self,
        app: Any,
        users: UserRegistry,
        *,
        public_paths: tuple[str, ...] = ("/healthz", "/readyz"),
    ) -> None:
        self.app = app
        self.users = users
        self.public_paths = public_paths

    async def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: Any,
        send: Any,
    ) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        path = str(scope.get("path", ""))
        if path in self.public_paths:
            await self.app(scope, receive, send)
            return
        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        authorization = headers.get("authorization", "")
        scheme, _, bearer = authorization.partition(" ")
        user = (
            self.users.authenticate(bearer)
            if scheme.lower() == "bearer" and bearer
            else None
        )
        if user is None:
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"www-authenticate", b"Bearer"),
                    ],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b'{"error":"unauthorized"}',
                }
            )
            return
        context_token = set_current_user(user)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_current_user(context_token)
