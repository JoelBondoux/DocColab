from __future__ import annotations

from contextvars import ContextVar, Token

from agent.mcp_server.models import UserRecord

_current_user: ContextVar[UserRecord | None] = ContextVar(
    "doccolab_current_user",
    default=None,
)


def current_user() -> UserRecord:
    user = _current_user.get()
    if user is None:
        raise PermissionError("No authenticated MCP user is associated with this request")
    return user


def set_current_user(user: UserRecord) -> Token[UserRecord | None]:
    return _current_user.set(user)


def reset_current_user(token: Token[UserRecord | None]) -> None:
    _current_user.reset(token)
