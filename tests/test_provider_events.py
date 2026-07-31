from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from agent.config import AppConfig, DocumentConfig, GitHubConfig
from agent.microsoft.onedrive_client import DeltaResult
from agent.sync.provider_events import ProviderEventCoordinator, WebhookVerificationError
from agent.sync.state_store import StateStore


def _config() -> AppConfig:
    return AppConfig(
        github=GitHubConfig(owner="owner", repository="repo"),
        documents=[
            DocumentConfig(
                id="document",
                title="Document",
                markdown_path="documents/document.md",
                google_file_id="google-id",
                microsoft_item_id="item-id",
            )
        ],
    )


class ResettingOneDrive:
    def __init__(self) -> None:
        self.calls: list[tuple[str | None, bool]] = []

    def poll_delta(
        self,
        *,
        drive_id: str | None = None,
        delta_link: str | None = None,
        latest_only: bool = False,
    ) -> DeltaResult:
        self.calls.append((delta_link, latest_only))
        if delta_link:
            request = httpx.Request("GET", delta_link)
            response = httpx.Response(410, request=request)
            raise httpx.HTTPStatusError("cursor expired", request=request, response=response)
        return DeltaResult(items=({"id": "item-id"},), delta_link="fresh-cursor")


def test_google_notification_requires_known_token_and_deduplicates(
    tmp_path: Path,
) -> None:
    state = StateStore(tmp_path / "state.db")
    state.save_google_watch(
        channel_id="channel",
        resource_id="resource",
        document_id="document",
        verification_token="secret",
        expiration_ms=123,
    )
    events = ProviderEventCoordinator(
        config=_config(),
        state=state,
        documents={document.id: document for document in _config().documents},
        google_drive=None,
        onedrive=None,
    )
    headers = {
        "x-goog-channel-id": "channel",
        "x-goog-channel-token": "secret",
        "x-goog-resource-state": "update",
        "x-goog-message-number": "7",
    }

    assert events.validate_google_notification(headers) == "document"
    assert events.validate_google_notification(headers) is None
    with pytest.raises(WebhookVerificationError, match="invalid channel token"):
        events.validate_google_notification(
            {**headers, "x-goog-channel-token": "incorrect"}
        )
    state.close()


def test_microsoft_expired_delta_cursor_is_reinitialized(tmp_path: Path) -> None:
    state = StateStore(tmp_path / "state.db")
    state.set_cursor("microsoft", "me", "https://graph.invalid/expired")
    onedrive = ResettingOneDrive()
    config = _config()
    events = ProviderEventCoordinator(
        config=config,
        state=state,
        documents={document.id: document for document in config.documents},
        google_drive=None,
        onedrive=onedrive,  # type: ignore[arg-type]
    )

    assert events.poll_microsoft_delta() == {"document"}
    assert onedrive.calls == [
        ("https://graph.invalid/expired", False),
        (None, True),
    ]
    assert state.get_cursor("microsoft", "me") == "fresh-cursor"
    state.close()
