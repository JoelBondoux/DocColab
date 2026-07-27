from __future__ import annotations

from pathlib import Path

import pytest

from agent.config import AppConfig, DocumentConfig, GitHubConfig
from agent.github.github_client import GitHubCommit, GitHubFile
from agent.google.google_drive_client import GoogleFileMetadata
from agent.models import Source, SyncStatus
from agent.sync.state_store import StateStore
from agent.sync.sync_manager import SyncManager


class FakeConverter:
    def docx_to_markdown(self, content: bytes) -> str:
        return content.decode()

    def markdown_to_docx(self, markdown: str) -> bytes:
        return markdown.encode()


class FakeGoogleDrive:
    def __init__(self, markdown: str) -> None:
        self.markdown = markdown
        self.version = "1"
        self.replacements: list[bytes] = []

    def metadata(self, _: str) -> GoogleFileMetadata:
        return GoogleFileMetadata(
            file_id="google-id",
            name="Document",
            mime_type="application/vnd.google-apps.document",
            version=self.version,
            modified_time="now",
            head_revision_id="revision",
        )

    def export_docx(self, _: str) -> bytes:
        return self.markdown.encode()

    def replace_google_doc(
        self,
        _: str,
        docx: bytes,
        *,
        expected_version: str | None = None,
    ) -> GoogleFileMetadata:
        assert expected_version == self.version
        self.replacements.append(docx)
        self.markdown = docx.decode()
        self.version = str(int(self.version) + 1)
        return self.metadata("google-id")


class FakeGoogleDocs:
    def get_document(self, _: str) -> dict[str, str]:
        return {"revisionId": "revision"}


class FakeGitHub:
    def __init__(self) -> None:
        self.file: GitHubFile | None = None
        self.commits: list[str] = []
        self.tags: list[tuple[str, str]] = []

    def get_file(self, path: str, _: str) -> GitHubFile | None:
        if not self.file:
            return None
        return GitHubFile(path, self.file.content, self.file.blob_sha, self.file.html_url)

    def commit_file(
        self,
        *,
        path: str,
        content: str,
        branch: str,
        message: str,
        expected_blob_sha: str | None,
    ) -> GitHubCommit:
        assert expected_blob_sha == (self.file.blob_sha if self.file else None)
        self.commits.append(message)
        number = len(self.commits)
        self.file = GitHubFile(path, content, f"blob-{number}", None)
        return GitHubCommit(f"commit-{number}", f"blob-{number}", None)

    def branch_head(self, _: str) -> str:
        return f"commit-{len(self.commits)}"

    def create_tag(self, tag: str, commit_sha: str) -> None:
        self.tags.append((tag, commit_sha))


class FakeAI:
    def rewrite(self, _: str) -> str:
        return "# AI revision\n"


def _config() -> AppConfig:
    return AppConfig(
        google={
            "enabled": True,
            "acknowledge_broad_access": True,
            "write_mode": "replace",
            "acknowledge_non_atomic_replacement": True,
        },
        github=GitHubConfig(owner="owner", repository="repo"),
        ai={
            "enabled": True,
            "provider": "openai",
            "operations": ["improve_clarity"],
            "auto_rewrite_human_changes": True,
        },
        documents=[
            DocumentConfig(
                id="document",
                title="Document",
                markdown_path="documents/document.md",
                google_file_id="google-id",
            )
        ],
    )


@pytest.mark.asyncio
async def test_google_to_github_to_ai_to_google_is_two_commits_and_one_revision(
    tmp_path: Path,
) -> None:
    config = _config()
    state = StateStore(tmp_path / "state.db")
    google = FakeGoogleDrive("# Human revision\n")
    github = FakeGitHub()
    manager = SyncManager(
        config=config,
        state=state,
        converter=FakeConverter(),
        github=github,
        google_drive=google,
        google_docs=FakeGoogleDocs(),
        ai_pipeline=FakeAI(),
    )

    result = await manager.sync_document("document")
    saved = state.get_document("document")
    state.close()

    assert result.status == SyncStatus.READY
    assert result.source == Source.AI
    assert github.commits == [
        "sync(document): import google changes",
        "ai(document): rewrite document",
    ]
    assert google.replacements == [b"# AI revision\n"]
    assert saved.base_markdown == "# AI revision\n"
    assert saved.google_version == "2"
    assert saved.pending_markdown is None
    assert github.tags == [("doc/document/v0.1.1", "commit-2")]
