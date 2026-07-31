from __future__ import annotations

from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build


class GoogleDocsClient:
    """Reads native Google Docs structure for inspection and attribution."""

    def __init__(self, credentials: Credentials, service: Resource | None = None) -> None:
        self.service = service or build(
            "docs",
            "v1",
            credentials=credentials,
            cache_discovery=False,
        )

    def get_document(self, document_id: str) -> dict[str, Any]:
        return self.service.documents().get(documentId=document_id).execute()

    def revision_id(self, document_id: str) -> str | None:
        document = self.get_document(document_id)
        return document.get("revisionId")

    def plain_text(self, document_id: str) -> str:
        document = self.get_document(document_id)
        parts: list[str] = []
        for structural_element in document.get("body", {}).get("content", []):
            paragraph = structural_element.get("paragraph")
            if not paragraph:
                continue
            for element in paragraph.get("elements", []):
                text_run = element.get("textRun")
                if text_run:
                    parts.append(text_run.get("content", ""))
        return "".join(parts)
