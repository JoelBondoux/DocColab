from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import replace
from datetime import UTC, datetime

from agent.ai.pipeline import RewritePipeline
from agent.config import AppConfig, DocumentConfig
from agent.conversion.converter import DocumentConverter
from agent.github.github_client import GitHubClient, GitHubFile
from agent.google.google_docs_client import GoogleDocsClient
from agent.google.google_drive_client import GoogleDriveClient, GoogleFileMetadata
from agent.microsoft.onedrive_client import OneDriveClient, OneDriveMetadata
from agent.models import DocumentState, Source, SyncResult, SyncStatus, utc_now
from agent.sync.conflict_resolver import ConflictResolver
from agent.sync.provider_events import ProviderEventCoordinator
from agent.sync.state_store import StateStore

logger = logging.getLogger(__name__)


class SyncManager:
    def __init__(
        self,
        *,
        config: AppConfig,
        state: StateStore,
        converter: DocumentConverter,
        github: GitHubClient,
        google_drive: GoogleDriveClient | None = None,
        google_docs: GoogleDocsClient | None = None,
        onedrive: OneDriveClient | None = None,
        ai_pipeline: RewritePipeline | None = None,
    ) -> None:
        self.config = config
        self.state = state
        self.converter = converter
        self.github = github
        self.google_drive = google_drive
        self.google_docs = google_docs
        self.onedrive = onedrive
        self.ai_pipeline = ai_pipeline
        self.conflicts = ConflictResolver()
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.stop_event = asyncio.Event()
        self.documents = {
            document.id: document for document in config.documents if document.enabled
        }
        self.events = ProviderEventCoordinator(
            config=config,
            state=state,
            documents=self.documents,
            google_drive=google_drive,
            onedrive=onedrive,
        )
        self._locks = {document_id: asyncio.Lock() for document_id in self.documents}
        for document_id in self.documents:
            self.state.ensure_document(document_id)

    async def run_forever(self) -> None:
        await self.sync_all()
        await asyncio.to_thread(self.events.initialize_microsoft_delta)
        while not self.stop_event.is_set():
            try:
                document_id = await asyncio.wait_for(
                    self.queue.get(),
                    timeout=self.config.agent.poll_interval_seconds,
                )
            except TimeoutError:
                changed = await asyncio.to_thread(self.events.poll_microsoft_delta)
                for changed_document_id in changed:
                    await self.sync_document(changed_document_id)
                for document_id in self.documents:
                    if document_id not in changed:
                        await self.sync_document(document_id)
            else:
                if document_id in self.documents:
                    await self.sync_document(document_id)

    async def sync_all(self) -> list[SyncResult]:
        results = []
        for document_id in self.documents:
            results.append(await self.sync_document(document_id))
        return results

    async def sync_document(self, document_id: str) -> SyncResult:
        document = self.documents[document_id]
        async with self._locks[document_id]:
            try:
                return await asyncio.to_thread(self._sync_document, document)
            except Exception as exc:
                logger.exception("Sync failed for %s", document_id)
                self.state.mark_error(document_id, str(exc))
                return SyncResult(
                    document_id=document_id,
                    status=SyncStatus.ERROR,
                    source=None,
                    version=None,
                    detail=str(exc),
                )

    async def notify(self, document_id: str) -> None:
        if document_id in self.documents:
            await self.queue.put(document_id)

    def stop(self) -> None:
        self.stop_event.set()

    def validate_google_notification(self, headers: dict[str, str]) -> str | None:
        return self.events.validate_google_notification(headers)

    def renew_google_watches(self) -> list[dict[str, object]]:
        return self.events.renew_google_watches()

    def _sync_document(self, document: DocumentConfig) -> SyncResult:
        state = self.state.ensure_document(document.id)
        if state.pending_markdown:
            return self._publish_pending(document, state)

        google_metadata = self.google_metadata(document)
        microsoft_metadata = self.microsoft_metadata(document)
        branch = document.github_branch or self.config.github.branch
        github_file = self.github.get_file(document.markdown_path, branch)

        google_changed = bool(
            google_metadata and google_metadata.version != state.google_version
        )
        microsoft_changed = bool(
            microsoft_metadata and microsoft_metadata.etag != state.microsoft_version
        )
        github_changed = bool(
            github_file and github_file.blob_sha != state.github_blob_sha
        )
        if not any((google_changed, microsoft_changed, github_changed)):
            status = SyncStatus(state.status)
            return SyncResult(
                document_id=document.id,
                status=status,
                source=None,
                version=self._version_label(state.version) if state.version else None,
                detail="No changes detected",
            )

        candidates: dict[Source, str] = {}
        if google_changed:
            candidates[Source.GOOGLE] = self.google_markdown(document)
        if microsoft_changed:
            candidates[Source.MICROSOFT] = self.microsoft_markdown(document)
        if github_changed and github_file:
            candidates[Source.GITHUB] = _normalize(github_file.content)

        merge = self.conflicts.merge(
            state.base_markdown,
            {source.value: markdown for source, markdown in candidates.items()},
        )
        if merge.conflicted:
            return self._publish_conflict(
                document,
                state,
                merge.markdown,
                google_metadata,
                microsoft_metadata,
                github_file,
                tuple(source.value for source in candidates),
            )

        source = next(iter(candidates)) if len(candidates) == 1 else Source.MERGE
        source_markdown = _normalize(merge.markdown)
        surface_hashes = {
            Source.GOOGLE: (
                _content_hash(candidates[Source.GOOGLE])
                if Source.GOOGLE in candidates
                else state.canonical_hash
            ),
            Source.MICROSOFT: (
                _content_hash(candidates[Source.MICROSOFT])
                if Source.MICROSOFT in candidates
                else state.canonical_hash
            ),
        }

        current_content = _normalize(github_file.content) if github_file else ""
        current_blob = github_file.blob_sha if github_file else None
        commit_sha: str | None = None
        if current_content != source_markdown:
            commit = self.github.commit_file(
                path=document.markdown_path,
                content=source_markdown,
                branch=branch,
                message=f"sync({document.id}): import {source.value} changes",
                expected_blob_sha=current_blob,
            )
            current_content = source_markdown
            current_blob = commit.blob_sha
            commit_sha = commit.commit_sha

        final_markdown = source_markdown
        final_source = source
        pipeline = self.ai_pipeline
        should_rewrite = (
            pipeline is not None
            and self.config.ai.enabled
            and self.config.ai.auto_rewrite_human_changes
            and source in {Source.GOOGLE, Source.MICROSOFT, Source.MERGE}
        )
        if should_rewrite and pipeline:
            rewritten = _normalize(pipeline.rewrite(source_markdown))
            if rewritten != source_markdown:
                commit = self.github.commit_file(
                    path=document.markdown_path,
                    content=rewritten,
                    branch=branch,
                    message=f"ai({document.id}): rewrite document",
                    expected_blob_sha=current_blob,
                )
                final_markdown = rewritten
                current_blob = commit.blob_sha
                commit_sha = commit.commit_sha
                final_source = Source.AI

        if commit_sha is None:
            commit_sha = self.github.branch_head(branch)
        if current_blob is None:
            raise RuntimeError("GitHub did not return a blob SHA for the canonical document")

        target_hash = _content_hash(final_markdown)
        pending_surfaces: list[str] = []
        if (
            document.google_file_id
            and self.config.google.write_mode == "replace"
            and surface_hashes[Source.GOOGLE] != target_hash
        ):
            pending_surfaces.append(Source.GOOGLE.value)
        if document.microsoft_item_id and surface_hashes[Source.MICROSOFT] != target_hash:
            pending_surfaces.append(Source.MICROSOFT.value)

        pending = replace(
            state,
            google_version=google_metadata.version if google_metadata else None,
            microsoft_version=microsoft_metadata.etag if microsoft_metadata else None,
            github_blob_sha=current_blob,
            last_writer=final_source.value,
            status=SyncStatus.SYNCING,
            last_error=None,
            updated_at=utc_now(),
            pending_markdown=final_markdown,
            pending_blob_sha=current_blob,
            pending_commit_sha=commit_sha,
            pending_source=final_source.value,
            pending_version=state.version + 1,
            pending_surfaces=",".join(pending_surfaces),
        )
        self.state.save_document(pending)
        return self._publish_pending(document, pending)

    def _publish_pending(
        self,
        document: DocumentConfig,
        state: DocumentState,
    ) -> SyncResult:
        if not state.pending_markdown or not state.pending_blob_sha or not state.pending_commit_sha:
            raise RuntimeError("Incomplete pending synchronization state")
        branch = document.github_branch or self.config.github.branch
        github_file = self.github.get_file(document.markdown_path, branch)
        if not github_file:
            raise RuntimeError("The pending canonical Markdown file disappeared from GitHub")
        if (
            github_file.blob_sha != state.pending_blob_sha
            and _normalize(github_file.content) != _normalize(state.pending_markdown)
        ):
            google_metadata = self.google_metadata(document)
            microsoft_metadata = self.microsoft_metadata(document)
            conflict = self.conflicts.merge(
                "",
                {
                    "pending": state.pending_markdown,
                    "github": github_file.content,
                },
            )
            return self._publish_conflict(
                document,
                state,
                conflict.markdown,
                google_metadata,
                microsoft_metadata,
                github_file,
                ("pending", "github"),
            )

        target_hash = _content_hash(state.pending_markdown)
        surfaces = set(filter(None, (state.pending_surfaces or "").split(",")))
        docx = self.converter.markdown_to_docx(state.pending_markdown) if surfaces else b""
        google_metadata = self.google_metadata(document)
        microsoft_metadata = self.microsoft_metadata(document)

        if Source.GOOGLE.value in surfaces and google_metadata and document.google_file_id:
            google_drive = self.google_drive
            if not google_drive:
                raise RuntimeError("Google client is unavailable during pending publish")
            if google_metadata.version != state.google_version:
                current = self.google_markdown(document)
                if _content_hash(current) != target_hash:
                    conflict = self.conflicts.merge(
                        "",
                        {"pending": state.pending_markdown, "google": current},
                    )
                    return self._publish_conflict(
                        document,
                        state,
                        conflict.markdown,
                        google_metadata,
                        microsoft_metadata,
                        github_file,
                        ("pending", "google"),
                    )
            else:
                google_metadata = self.replace_google_document(
                    document,
                    docx,
                    expected_version=state.google_version,
                )

        if (
            Source.MICROSOFT.value in surfaces
            and microsoft_metadata
            and document.microsoft_item_id
        ):
            onedrive = self.onedrive
            if not onedrive:
                raise RuntimeError("OneDrive client is unavailable during pending publish")
            if microsoft_metadata.etag != state.microsoft_version:
                current = self.microsoft_markdown(document)
                if _content_hash(current) != target_hash:
                    conflict = self.conflicts.merge(
                        "",
                        {"pending": state.pending_markdown, "microsoft": current},
                    )
                    return self._publish_conflict(
                        document,
                        state,
                        conflict.markdown,
                        google_metadata,
                        microsoft_metadata,
                        github_file,
                        ("pending", "microsoft"),
                    )
            else:
                microsoft_metadata = self.replace_microsoft_document(
                    document,
                    docx,
                    expected_etag=state.microsoft_version,
                )

        version_number = state.pending_version or (state.version + 1)
        if self.config.versioning.create_tags:
            tag = (
                f"{self.config.github.tag_prefix}/{document.id}/"
                f"{self._version_label(version_number)}"
            )
            self.github.create_tag(tag, state.pending_commit_sha)

        completed = replace(
            state,
            base_markdown=_normalize(state.pending_markdown),
            canonical_hash=target_hash,
            google_version=google_metadata.version if google_metadata else None,
            microsoft_version=microsoft_metadata.etag if microsoft_metadata else None,
            github_blob_sha=github_file.blob_sha,
            version=version_number,
            last_writer=state.pending_source,
            status=SyncStatus.READY,
            last_error=None,
            updated_at=utc_now(),
            pending_markdown=None,
            pending_blob_sha=None,
            pending_commit_sha=None,
            pending_source=None,
            pending_version=None,
            pending_surfaces=None,
        )
        self.state.save_document(completed)
        return SyncResult(
            document_id=document.id,
            status=SyncStatus.READY,
            source=Source(completed.last_writer) if completed.last_writer else None,
            version=self._version_label(version_number),
            detail=f"Synchronized {document.title}",
        )

    def _publish_conflict(
        self,
        document: DocumentConfig,
        state: DocumentState,
        conflict_markdown: str,
        google_metadata: GoogleFileMetadata | None,
        microsoft_metadata: OneDriveMetadata | None,
        github_file: GitHubFile | None,
        sources: tuple[str, ...],
    ) -> SyncResult:
        base_branch = document.github_branch or self.config.github.branch
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        conflict_branch = f"conflicts/{document.id}/{timestamp}"
        self.github.ensure_branch(conflict_branch, base_branch)
        branch_file = self.github.get_file(document.markdown_path, conflict_branch)
        commit = self.github.commit_file(
            path=document.markdown_path,
            content=_normalize(conflict_markdown),
            branch=conflict_branch,
            message=f"conflict({document.id}): preserve concurrent edits",
            expected_blob_sha=branch_file.blob_sha if branch_file else None,
        )
        pull_request = self.github.create_pull_request(
            title=f"Resolve document conflict: {document.title}",
            body=(
                "DocColab detected concurrent edits that could not be merged safely.\n\n"
                f"Sources: {', '.join(sources)}\n\n"
                "Resolve the conflict markers in the Markdown file, then merge this pull "
                "request. No Google Docs or Word Online content was overwritten."
            ),
            head=conflict_branch,
            base=base_branch,
            draft=True,
        )
        conflicted = replace(
            state,
            google_version=google_metadata.version if google_metadata else None,
            microsoft_version=microsoft_metadata.etag if microsoft_metadata else None,
            github_blob_sha=github_file.blob_sha if github_file else state.github_blob_sha,
            status=SyncStatus.CONFLICT,
            last_error=f"Conflict PR: {pull_request}",
            updated_at=utc_now(),
            pending_markdown=None,
            pending_blob_sha=None,
            pending_commit_sha=None,
            pending_source=None,
            pending_version=None,
            pending_surfaces=None,
        )
        self.state.save_document(conflicted)
        logger.warning("Conflict for %s preserved in %s", document.id, commit.html_url)
        return SyncResult(
            document_id=document.id,
            status=SyncStatus.CONFLICT,
            source=None,
            version=None,
            detail=pull_request,
        )

    def google_metadata(self, document: DocumentConfig) -> GoogleFileMetadata | None:
        if not document.google_file_id:
            return None
        if not self.google_drive:
            raise RuntimeError("Document uses Google Docs but Google integration is disabled")
        return self.google_drive.metadata(document.google_file_id)

    def microsoft_metadata(self, document: DocumentConfig) -> OneDriveMetadata | None:
        if not document.microsoft_item_id:
            return None
        if not self.onedrive:
            raise RuntimeError("Document uses OneDrive but Microsoft integration is disabled")
        return self.onedrive.metadata(
            document.microsoft_item_id,
            document.microsoft_drive_id,
        )

    def google_markdown(self, document: DocumentConfig) -> str:
        if not self.google_drive or not document.google_file_id:
            raise RuntimeError("Google document client is unavailable")
        if self.google_docs:
            structure = self.google_docs.get_document(document.google_file_id)
            logger.debug(
                "Fetched Google Docs structure for %s at revision %s",
                document.id,
                structure.get("revisionId"),
            )
        return _normalize(
            self.converter.docx_to_markdown(
                self.google_drive.export_docx(document.google_file_id)
            )
        )

    def microsoft_markdown(self, document: DocumentConfig) -> str:
        if not self.onedrive or not document.microsoft_item_id:
            raise RuntimeError("OneDrive client is unavailable")
        return _normalize(
            self.converter.docx_to_markdown(
                self.onedrive.download(
                    document.microsoft_item_id,
                    document.microsoft_drive_id,
                )
            )
        )

    def replace_google_document(
        self,
        document: DocumentConfig,
        docx: bytes,
        *,
        expected_version: str | None,
    ) -> GoogleFileMetadata:
        if self.config.google.write_mode != "replace":
            raise PermissionError(
                "Google integration is read-only; set google.write_mode to 'replace' "
                "only after accepting the documented concurrency limitation"
            )
        if not self.google_drive or not document.google_file_id:
            raise RuntimeError("Google document is not configured")
        return self.google_drive.replace_google_doc(
            document.google_file_id,
            docx,
            expected_version=expected_version,
        )

    def replace_microsoft_document(
        self,
        document: DocumentConfig,
        docx: bytes,
        *,
        expected_etag: str | None,
    ) -> OneDriveMetadata:
        if not self.onedrive or not document.microsoft_item_id:
            raise RuntimeError("OneDrive document is not configured")
        return self.onedrive.replace(
            document.microsoft_item_id,
            docx,
            document.microsoft_drive_id,
            expected_etag=expected_etag,
        )

    def _version_label(self, version: int) -> str:
        return (
            f"v{self.config.versioning.major}."
            f"{self.config.versioning.minor}.{version}"
        )


def _normalize(markdown: str) -> str:
    value = markdown.replace("\r\n", "\n").replace("\r", "\n").rstrip()
    return value + "\n" if value else ""


def _content_hash(markdown: str) -> str:
    return hashlib.sha256(_normalize(markdown).encode("utf-8")).hexdigest()
