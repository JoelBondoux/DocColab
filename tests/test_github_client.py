import base64
import json

import httpx
import pytest

from agent.github.github_client import GitHubClient, GitHubVersionConflict


def test_github_contents_api_reads_and_commits_with_optimistic_blob_sha() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "type": "file",
                    "sha": "old-blob",
                    "content": base64.b64encode(b"# Existing\n").decode(),
                    "html_url": "https://github.example/file",
                },
            )
        payload = json.loads(request.content)
        assert payload["sha"] == "old-blob"
        assert base64.b64decode(payload["content"]) == b"# Updated\n"
        return httpx.Response(
            200,
            json={
                "content": {"sha": "new-blob"},
                "commit": {"sha": "new-commit", "html_url": "https://github.example/commit"},
            },
        )

    client = GitHubClient(
        token="token",
        owner="owner",
        repository="repo",
        transport=httpx.MockTransport(handler),
    )

    existing = client.get_file("documents/a.md", "main")
    committed = client.commit_file(
        path="documents/a.md",
        content="# Updated\n",
        branch="main",
        message="update",
        expected_blob_sha=existing.blob_sha,
    )
    client.close()

    assert existing.content == "# Existing\n"
    assert committed.commit_sha == "new-commit"
    assert requests[0].headers["authorization"] == "Bearer token"


def test_github_version_conflict_is_explicit() -> None:
    client = GitHubClient(
        token="token",
        owner="owner",
        repository="repo",
        transport=httpx.MockTransport(lambda _: httpx.Response(409, text="branch moved")),
    )

    with pytest.raises(GitHubVersionConflict, match="branch moved"):
        client.commit_file(
            path="document.md",
            content="new",
            branch="main",
            message="update",
            expected_blob_sha="old",
        )
    client.close()
