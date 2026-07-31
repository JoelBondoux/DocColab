from __future__ import annotations

import pytest

from agent.mcp_server.tools import _invoke, _invoke_async


class OutcomeService:
    def __init__(self) -> None:
        self.outcomes: list[tuple[str, str | None, str | None]] = []

    def record_outcome(
        self,
        tool: str,
        project_id: str | None,
        error: Exception | None = None,
    ) -> None:
        self.outcomes.append(
            (tool, project_id, type(error).__name__ if error else None)
        )


def test_sync_tool_wrapper_records_success_and_failure() -> None:
    service = OutcomeService()
    assert _invoke(service, "tool", "project", lambda: 7) == 7  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        _invoke(
            service,  # type: ignore[arg-type]
            "tool",
            "project",
            lambda: (_ for _ in ()).throw(ValueError("bad")),
        )
    assert service.outcomes == [
        ("tool", "project", None),
        ("tool", "project", "ValueError"),
    ]


@pytest.mark.asyncio
async def test_async_tool_wrapper_records_success_and_failure() -> None:
    service = OutcomeService()

    async def success() -> int:
        return 9

    async def failure() -> int:
        raise RuntimeError("bad")

    assert await _invoke_async(service, "async", None, success) == 9  # type: ignore[arg-type]
    with pytest.raises(RuntimeError):
        await _invoke_async(service, "async", None, failure)  # type: ignore[arg-type]
    assert service.outcomes == [
        ("async", None, None),
        ("async", None, "RuntimeError"),
    ]
