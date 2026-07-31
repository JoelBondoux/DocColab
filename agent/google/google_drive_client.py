from __future__ import annotations

import io
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
GOOGLE_DOC_MIME = "application/vnd.google-apps.document"


@dataclass(frozen=True, slots=True)
class GoogleFileMetadata:
    file_id: str
    name: str
    mime_type: str
    version: str
    modified_time: str
    head_revision_id: str | None


@dataclass(frozen=True, slots=True)
class GoogleWatch:
    channel_id: str
    resource_id: str
    expiration_ms: int


class GoogleDriveClient:
    def __init__(self, credentials: Credentials, service: Resource | None = None) -> None:
        self.service = service or build(
            "drive",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )

    def metadata(self, file_id: str) -> GoogleFileMetadata:
        value = (
            self.service.files()
            .get(
                fileId=file_id,
                fields="id,name,mimeType,version,modifiedTime,headRevisionId",
                supportsAllDrives=True,
            )
            .execute()
        )
        return GoogleFileMetadata(
            file_id=value["id"],
            name=value["name"],
            mime_type=value["mimeType"],
            version=str(value.get("version", "")),
            modified_time=value.get("modifiedTime", ""),
            head_revision_id=value.get("headRevisionId"),
        )

    def export_docx(self, file_id: str) -> bytes:
        request = self.service.files().export_media(fileId=file_id, mimeType=DOCX_MIME)
        output = io.BytesIO()
        downloader = MediaIoBaseDownload(output, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return output.getvalue()

    def replace_google_doc(
        self,
        file_id: str,
        docx: bytes,
        *,
        expected_version: str | None = None,
    ) -> GoogleFileMetadata:
        if expected_version is not None:
            current = self.metadata(file_id)
            if current.version != expected_version:
                raise GoogleVersionConflict(
                    f"Google file {file_id} changed from version "
                    f"{expected_version} to {current.version}"
                )
        media = MediaIoBaseUpload(io.BytesIO(docx), mimetype=DOCX_MIME, resumable=True)
        (
            self.service.files()
            .update(
                fileId=file_id,
                media_body=media,
                fields="id,name,mimeType,version,modifiedTime,headRevisionId",
                supportsAllDrives=True,
            )
            .execute()
        )
        return self.metadata(file_id)

    def watch_file(
        self,
        file_id: str,
        callback_url: str,
        verification_token: str,
        ttl_seconds: int,
    ) -> GoogleWatch:
        channel_id = str(uuid.uuid4())
        expiration_ms = int((time.time() + ttl_seconds) * 1000)
        body: dict[str, Any] = {
            "id": channel_id,
            "type": "web_hook",
            "address": callback_url,
            "token": verification_token,
            "expiration": expiration_ms,
        }
        value = self.service.files().watch(fileId=file_id, body=body).execute()
        return GoogleWatch(
            channel_id=value["id"],
            resource_id=value["resourceId"],
            expiration_ms=int(value.get("expiration", expiration_ms)),
        )

    def stop_watch(self, channel_id: str, resource_id: str) -> None:
        self.service.channels().stop(
            body={"id": channel_id, "resourceId": resource_id}
        ).execute()

    def list_revisions(self, file_id: str) -> list[dict[str, Any]]:
        value = (
            self.service.revisions()
            .list(
                fileId=file_id,
                pageSize=1000,
                fields="revisions(id,modifiedTime,keepForever,published)",
            )
            .execute()
        )
        return list(value.get("revisions", []))

    @staticmethod
    def expiration_iso(expiration_ms: int) -> str:
        return datetime.fromtimestamp(expiration_ms / 1000, tz=UTC).isoformat()


class GoogleVersionConflict(RuntimeError):
    pass
