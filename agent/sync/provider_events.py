from __future__ import annotations

import hmac
import logging
from collections import defaultdict
from typing import Any

import httpx

from agent.config import AppConfig, DocumentConfig, require_env
from agent.google.google_drive_client import GoogleDriveClient
from agent.microsoft.onedrive_client import OneDriveClient
from agent.sync.state_store import StateStore

logger = logging.getLogger(__name__)


class ProviderEventCoordinator:
    """Webhook/watch validation and provider change-cursor polling."""

    def __init__(
        self,
        *,
        config: AppConfig,
        state: StateStore,
        documents: dict[str, DocumentConfig],
        google_drive: GoogleDriveClient | None,
        onedrive: OneDriveClient | None,
    ) -> None:
        self.config = config
        self.state = state
        self.documents = documents
        self.google_drive = google_drive
        self.onedrive = onedrive

    def validate_google_notification(self, headers: dict[str, str]) -> str | None:
        channel_id = headers.get("x-goog-channel-id")
        verification_token = headers.get("x-goog-channel-token")
        resource_state = headers.get("x-goog-resource-state")
        message_number = headers.get("x-goog-message-number", "")
        if not channel_id or not verification_token:
            raise WebhookVerificationError("Missing Google notification channel headers")
        watch = self.state.google_watch(channel_id)
        if not watch or not hmac.compare_digest(
            str(watch["verification_token"]),
            verification_token,
        ):
            raise WebhookVerificationError("Unknown Google channel or invalid channel token")
        if resource_state == "sync":
            return None
        event_key = f"{channel_id}:{message_number}"
        if not self.state.remember_event(event_key, "google"):
            return None
        return str(watch["document_id"])

    def renew_google_watches(self) -> list[dict[str, Any]]:
        if not self.google_drive:
            raise RuntimeError("Google integration is disabled")
        base_url = self.config.agent.public_webhook_base_url
        if not base_url or not base_url.startswith("https://"):
            raise RuntimeError("agent.public_webhook_base_url must be a public HTTPS URL")
        token = require_env(self.config.google.webhook_token_env)
        if len(token) < 32:
            raise RuntimeError("The Google webhook token must contain at least 32 characters")
        callback_url = f"{base_url.rstrip('/')}/webhooks/google"
        watches = []
        for document in self.documents.values():
            if not document.google_file_id:
                continue
            for previous in self.state.watches_for_document(document.id):
                try:
                    self.google_drive.stop_watch(
                        str(previous["channel_id"]),
                        str(previous["resource_id"]),
                    )
                except Exception:
                    logger.warning(
                        "Unable to stop expired Google watch %s",
                        previous["channel_id"],
                        exc_info=True,
                    )
                self.state.delete_google_watch(str(previous["channel_id"]))
            watch = self.google_drive.watch_file(
                document.google_file_id,
                callback_url,
                token,
                self.config.google.watch_ttl_seconds,
            )
            self.state.save_google_watch(
                channel_id=watch.channel_id,
                resource_id=watch.resource_id,
                document_id=document.id,
                verification_token=token,
                expiration_ms=watch.expiration_ms,
            )
            watches.append(
                {
                    "document_id": document.id,
                    "channel_id": watch.channel_id,
                    "expiration_ms": watch.expiration_ms,
                }
            )
        return watches

    def initialize_microsoft_delta(self) -> None:
        if not self.onedrive:
            return
        for drive_id in self._microsoft_groups():
            scope = drive_id or "me"
            if self.state.get_cursor("microsoft", scope):
                continue
            result = self.onedrive.poll_delta(drive_id=drive_id, latest_only=True)
            self.state.set_cursor("microsoft", scope, result.delta_link)

    def poll_microsoft_delta(self) -> set[str]:
        if not self.onedrive:
            return set()
        changed: set[str] = set()
        for drive_id, documents in self._microsoft_groups().items():
            scope = drive_id or "me"
            cursor = self.state.get_cursor("microsoft", scope)
            try:
                result = self.onedrive.poll_delta(
                    drive_id=drive_id,
                    delta_link=cursor,
                    latest_only=cursor is None,
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 410:
                    raise
                result = self.onedrive.poll_delta(drive_id=drive_id, latest_only=True)
            self.state.set_cursor("microsoft", scope, result.delta_link)
            item_ids = {
                str(item.get("id"))
                for item in result.items
                if "deleted" not in item
            }
            changed.update(
                document.id
                for document in documents
                if document.microsoft_item_id in item_ids
            )
        return changed

    def _microsoft_groups(self) -> dict[str | None, list[DocumentConfig]]:
        groups: dict[str | None, list[DocumentConfig]] = defaultdict(list)
        for document in self.documents.values():
            if document.microsoft_item_id:
                groups[document.microsoft_drive_id].append(document)
        return groups


class WebhookVerificationError(RuntimeError):
    pass
