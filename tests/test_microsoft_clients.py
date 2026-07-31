from __future__ import annotations

from typing import Any

import httpx
import pytest

from agent.microsoft.onedrive_client import OneDriveClient, OneDriveVersionConflict
from agent.microsoft.word_online_client import WordOnlineClient


class FakeGraph:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict[str, Any]]] = []
        self.fail_precondition = False
        self.delta_page = 0

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        self.requests.append((method, path, kwargs))
        if self.fail_precondition:
            request = httpx.Request(method, f"https://graph.example{path}")
            response = httpx.Response(412, request=request)
            raise httpx.HTTPStatusError("precondition", request=request, response=response)
        if "delta" in path or path.startswith("https://next"):
            self.delta_page += 1
            payload = (
                {"value": [{"id": "one"}], "@odata.nextLink": "https://next/page"}
                if self.delta_page == 1
                else {"value": [{"id": "two"}], "@odata.deltaLink": "https://delta/final"}
            )
            return httpx.Response(200, json=payload)
        return httpx.Response(200, content=b"docx")

    def json(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        self.requests.append((method, path, kwargs))
        if path.endswith("/versions"):
            return {"value": [{"id": "1"}]}
        return {
            "id": "item",
            "name": "Document.docx",
            "eTag": '"etag-2"',
            "cTag": "ctag",
            "lastModifiedDateTime": "now",
            "size": 4,
            "parentReference": {"driveId": "drive"},
        }


def test_onedrive_and_word_clients_preserve_etag_contract() -> None:
    graph = FakeGraph()
    onedrive = OneDriveClient(graph)  # type: ignore[arg-type]
    word = WordOnlineClient(onedrive)

    assert word.download_docx("item", "drive") == b"docx"
    updated = word.replace_docx("item", b"new", "drive", expected_etag='"etag-1"')
    assert updated.etag == '"etag-2"'
    assert graph.requests[1][2]["headers"]["If-Match"] == '"etag-1"'
    assert word.versions("item", "drive") == [{"id": "1"}]

    delta = onedrive.poll_delta(drive_id="drive")
    assert [item["id"] for item in delta.items] == ["one", "two"]
    assert delta.delta_link == "https://delta/final"


def test_onedrive_maps_precondition_failure_to_domain_conflict() -> None:
    graph = FakeGraph()
    graph.fail_precondition = True
    onedrive = OneDriveClient(graph)  # type: ignore[arg-type]

    with pytest.raises(OneDriveVersionConflict, match="changed after"):
        onedrive.replace("item", b"new", expected_etag='"old"')
