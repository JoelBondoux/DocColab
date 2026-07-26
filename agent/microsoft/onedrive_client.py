from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from agent.microsoft.graph_client import MicrosoftGraphClient

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@dataclass(frozen=True, slots=True)
class OneDriveMetadata:
    item_id: str
    drive_id: str
    name: str
    etag: str
    ctag: str | None
    modified_time: str
    size: int


@dataclass(frozen=True, slots=True)
class DeltaResult:
    items: tuple[dict[str, Any], ...]
    delta_link: str


class OneDriveClient:
    def __init__(self, graph: MicrosoftGraphClient) -> None:
        self.graph = graph

    def metadata(self, item_id: str, drive_id: str | None = None) -> OneDriveMetadata:
        value = self.graph.json(
            "GET",
            self._item_path(item_id, drive_id),
            params={
                "$select": "id,name,eTag,cTag,lastModifiedDateTime,size,parentReference,file"
            },
        )
        resolved_drive = value.get("parentReference", {}).get("driveId") or drive_id or "me"
        return OneDriveMetadata(
            item_id=value["id"],
            drive_id=resolved_drive,
            name=value["name"],
            etag=value.get("eTag", ""),
            ctag=value.get("cTag"),
            modified_time=value.get("lastModifiedDateTime", ""),
            size=int(value.get("size", 0)),
        )

    def download(self, item_id: str, drive_id: str | None = None) -> bytes:
        response = self.graph.request("GET", f"{self._item_path(item_id, drive_id)}/content")
        return response.content

    def replace(
        self,
        item_id: str,
        content: bytes,
        drive_id: str | None = None,
        *,
        expected_etag: str | None = None,
    ) -> OneDriveMetadata:
        headers = {"Content-Type": DOCX_MIME}
        if expected_etag:
            headers["If-Match"] = expected_etag
        try:
            self.graph.request(
                "PUT",
                f"{self._item_path(item_id, drive_id)}/content",
                headers=headers,
                content=content,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 412:
                raise OneDriveVersionConflict(
                    f"OneDrive item {item_id} changed after it was read"
                ) from exc
            raise
        return self.metadata(item_id, drive_id)

    def list_versions(
        self, item_id: str, drive_id: str | None = None
    ) -> list[dict[str, Any]]:
        value = self.graph.json(
            "GET",
            f"{self._item_path(item_id, drive_id)}/versions",
        )
        return list(value.get("value", []))

    def poll_delta(
        self,
        *,
        drive_id: str | None = None,
        delta_link: str | None = None,
        latest_only: bool = False,
    ) -> DeltaResult:
        if delta_link:
            next_url = delta_link
        else:
            root = f"/drives/{quote(drive_id)}/root/delta" if drive_id else "/me/drive/root/delta"
            next_url = f"{root}?token=latest" if latest_only else root
        items: list[dict[str, Any]] = []
        while next_url:
            response = self.graph.request("GET", next_url)
            payload = response.json()
            items.extend(payload.get("value", []))
            next_url = payload.get("@odata.nextLink")
            if not next_url:
                delta_link = payload.get("@odata.deltaLink")
        if not delta_link:
            raise RuntimeError("Microsoft Graph delta response did not contain @odata.deltaLink")
        return DeltaResult(items=tuple(items), delta_link=delta_link)

    @staticmethod
    def _item_path(item_id: str, drive_id: str | None) -> str:
        encoded_item = quote(item_id, safe="")
        if drive_id:
            return f"/drives/{quote(drive_id, safe='')}/items/{encoded_item}"
        return f"/me/drive/items/{encoded_item}"


class OneDriveVersionConflict(RuntimeError):
    pass
