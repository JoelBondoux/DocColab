from __future__ import annotations

from typing import Any

from agent.microsoft.onedrive_client import OneDriveClient, OneDriveMetadata


class WordOnlineClient:
    """Word Online integration through the backing OneDrive driveItem."""

    def __init__(self, onedrive: OneDriveClient) -> None:
        self.onedrive = onedrive

    def download_docx(self, item_id: str, drive_id: str | None = None) -> bytes:
        return self.onedrive.download(item_id, drive_id)

    def replace_docx(
        self,
        item_id: str,
        docx: bytes,
        drive_id: str | None = None,
        *,
        expected_etag: str | None = None,
    ) -> OneDriveMetadata:
        return self.onedrive.replace(
            item_id,
            docx,
            drive_id,
            expected_etag=expected_etag,
        )

    def versions(self, item_id: str, drive_id: str | None = None) -> list[dict[str, Any]]:
        return self.onedrive.list_versions(item_id, drive_id)
