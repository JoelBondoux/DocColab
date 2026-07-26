from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class Source(StrEnum):
    GOOGLE = "google"
    MICROSOFT = "microsoft"
    GITHUB = "github"
    MERGE = "merge"
    AI = "ai"


class SyncStatus(StrEnum):
    READY = "ready"
    SYNCING = "syncing"
    CONFLICT = "conflict"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class SurfaceVersion:
    identifier: str | None
    modified_at: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentState:
    document_id: str
    base_markdown: str = ""
    canonical_hash: str = ""
    google_version: str | None = None
    microsoft_version: str | None = None
    github_blob_sha: str | None = None
    version: int = 0
    last_writer: str | None = None
    status: str = SyncStatus.READY
    last_error: str | None = None
    updated_at: str | None = None
    pending_markdown: str | None = None
    pending_blob_sha: str | None = None
    pending_commit_sha: str | None = None
    pending_source: str | None = None
    pending_version: int | None = None
    pending_surfaces: str | None = None


@dataclass(frozen=True, slots=True)
class MergeResult:
    markdown: str
    conflicted: bool
    conflict_sources: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SyncResult:
    document_id: str
    status: SyncStatus
    source: Source | None
    version: str | None
    detail: str


def utc_now() -> str:
    return datetime.now(UTC).isoformat()
