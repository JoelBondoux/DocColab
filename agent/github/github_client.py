from __future__ import annotations

import base64
import difflib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx


@dataclass(frozen=True, slots=True)
class GitHubFile:
    path: str
    content: str
    blob_sha: str
    html_url: str | None


@dataclass(frozen=True, slots=True)
class GitHubCommit:
    commit_sha: str
    blob_sha: str
    html_url: str | None


class GitHubClient:
    def __init__(
        self,
        *,
        token: str,
        owner: str,
        repository: str,
        api_url: str = "https://api.github.com",
        api_version: str = "2026-03-10",
        author_name: str = "DocColab Agent",
        author_email: str = "doccolab-agent@users.noreply.github.com",
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.owner = owner
        self.repository = repository
        self.author_name = author_name
        self.author_email = author_email
        self.client = httpx.Client(
            base_url=api_url,
            timeout=timeout,
            transport=transport,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": api_version,
                "User-Agent": "DocColab-Agent",
            },
        )

    @property
    def repo_path(self) -> str:
        return f"/repos/{quote(self.owner)}/{quote(self.repository)}"

    def get_file(self, path: str, branch: str) -> GitHubFile | None:
        response = self.client.get(
            f"{self.repo_path}/contents/{quote(path, safe='/')}",
            params={"ref": branch},
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        value = response.json()
        if value.get("type") != "file":
            raise RuntimeError(f"GitHub path {path!r} is not a file")
        content = base64.b64decode(value["content"]).decode("utf-8")
        return GitHubFile(
            path=path,
            content=content,
            blob_sha=value["sha"],
            html_url=value.get("html_url"),
        )

    def commit_file(
        self,
        *,
        path: str,
        content: str,
        branch: str,
        message: str,
        expected_blob_sha: str | None,
    ) -> GitHubCommit:
        payload: dict[str, Any] = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": branch,
            "author": {
                "name": self.author_name,
                "email": self.author_email,
                "date": datetime.now(UTC).isoformat(),
            },
        }
        if expected_blob_sha:
            payload["sha"] = expected_blob_sha
        response = self.client.put(
            f"{self.repo_path}/contents/{quote(path, safe='/')}",
            json=payload,
        )
        if response.status_code in (409, 422):
            raise GitHubVersionConflict(
                f"GitHub rejected the update for {path}: {response.text}"
            )
        response.raise_for_status()
        value = response.json()
        return GitHubCommit(
            commit_sha=value["commit"]["sha"],
            blob_sha=value["content"]["sha"],
            html_url=value["commit"].get("html_url"),
        )

    def branch_head(self, branch: str) -> str:
        response = self.client.get(
            f"{self.repo_path}/git/ref/heads/{quote(branch, safe='')}"
        )
        response.raise_for_status()
        return str(response.json()["object"]["sha"])

    def ensure_branch(self, branch: str, from_branch: str) -> str:
        response = self.client.get(
            f"{self.repo_path}/git/ref/heads/{quote(branch, safe='')}"
        )
        if response.status_code == 200:
            return str(response.json()["object"]["sha"])
        if response.status_code != 404:
            response.raise_for_status()
        base_sha = self.branch_head(from_branch)
        created = self.client.post(
            f"{self.repo_path}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": base_sha},
        )
        created.raise_for_status()
        return base_sha

    def create_tag(self, tag: str, commit_sha: str) -> None:
        response = self.client.post(
            f"{self.repo_path}/git/refs",
            json={"ref": f"refs/tags/{tag}", "sha": commit_sha},
        )
        if response.status_code == 422 and "Reference already exists" in response.text:
            return
        response.raise_for_status()

    def create_pull_request(
        self,
        *,
        title: str,
        body: str,
        head: str,
        base: str,
        draft: bool = True,
    ) -> str:
        response = self.client.post(
            f"{self.repo_path}/pulls",
            json={
                "title": title,
                "body": body,
                "head": head,
                "base": base,
                "draft": draft,
            },
        )
        if response.status_code == 422:
            existing = self.client.get(
                f"{self.repo_path}/pulls",
                params={"head": f"{self.owner}:{head}", "base": base, "state": "open"},
            )
            existing.raise_for_status()
            pulls = existing.json()
            if pulls:
                return str(pulls[0]["html_url"])
        response.raise_for_status()
        return str(response.json()["html_url"])

    @staticmethod
    def markdown_diff(before: str, after: str, path: str = "document.md") -> str:
        return "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
        )

    def close(self) -> None:
        self.client.close()


class GitHubVersionConflict(RuntimeError):
    pass
