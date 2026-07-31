from __future__ import annotations

import asyncio

import httpx
import pytest

from agent.sync.provider_events import WebhookVerificationError
from agent.webhook.app import create_webhook_app


class StubManager:
    def __init__(self) -> None:
        self.notified: list[str] = []
        self.reject = False

    def validate_google_notification(self, _: dict[str, str]) -> str | None:
        if self.reject:
            raise WebhookVerificationError("invalid channel")
        return "document"

    async def notify(self, document_id: str) -> None:
        self.notified.append(document_id)


@pytest.mark.asyncio
async def test_webhook_exposes_only_health_and_verified_notification() -> None:
    manager = StubManager()
    app = create_webhook_app(manager)  # type: ignore[arg-type]
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/healthz")).json() == {"status": "ok"}
        assert (await client.get("/status")).status_code == 404
        assert (await client.post("/webhooks/google")).status_code == 204
        await asyncio.sleep(0)
        assert manager.notified == ["document"]

        manager.reject = True
        rejected = await client.post("/webhooks/google")
        assert rejected.status_code == 403
        assert rejected.json()["detail"] == "invalid channel"
