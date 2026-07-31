from __future__ import annotations

from dataclasses import dataclass

from agent.ai.base import AIProvider
from agent.ai.claude_client import ClaudeRewriteClient
from agent.ai.openai_client import OpenAIRewriteClient
from agent.ai.pipeline import RewritePipeline
from agent.config import AppConfig, require_env
from agent.conversion.converter import DocumentConverter
from agent.github.github_client import GitHubClient
from agent.google.google_auth import GoogleAuthenticator
from agent.google.google_docs_client import GoogleDocsClient
from agent.google.google_drive_client import GoogleDriveClient
from agent.instance_lock import InstanceLock
from agent.microsoft.graph_client import MicrosoftGraphClient
from agent.microsoft.ms_auth import MicrosoftAuthenticator
from agent.microsoft.onedrive_client import OneDriveClient
from agent.sync.state_store import StateStore
from agent.sync.sync_manager import SyncManager


@dataclass(slots=True)
class Runtime:
    manager: SyncManager
    state: StateStore
    github: GitHubClient
    graph: MicrosoftGraphClient | None
    instance_lock: InstanceLock
    _closed: bool = False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self.graph:
                self.graph.close()
            self.github.close()
            self.state.close()
        finally:
            self.instance_lock.close()


def build_runtime(config: AppConfig) -> Runtime:
    if not config.github.enabled:
        raise RuntimeError("GitHub integration is required")
    instance_lock = InstanceLock.acquire(config.agent.state_database)
    state: StateStore | None = None
    github: GitHubClient | None = None
    graph: MicrosoftGraphClient | None = None
    try:
        state = StateStore(config.agent.state_database)
        converter = DocumentConverter(config.conversion)
        github = GitHubClient(
            token=require_env(config.github.token_env),
            owner=config.github.owner,
            repository=config.github.repository,
            api_url=config.github.api_url,
            api_version=config.github.api_version,
            author_name=config.github.commit_author_name,
            author_email=config.github.commit_author_email,
        )

        google_drive = None
        google_docs = None
        uses_google = any(
            document.google_file_id for document in config.documents if document.enabled
        )
        if config.google.enabled and uses_google:
            credentials = GoogleAuthenticator(config.google).credentials()
            google_drive = GoogleDriveClient(credentials)
            google_docs = GoogleDocsClient(credentials)

        onedrive = None
        uses_microsoft = any(
            document.microsoft_item_id for document in config.documents if document.enabled
        )
        if config.microsoft.enabled and uses_microsoft:
            authenticator = MicrosoftAuthenticator(config.microsoft)
            graph = MicrosoftGraphClient(authenticator.access_token)
            onedrive = OneDriveClient(graph)

        ai_pipeline = None
        if config.ai.enabled:
            provider: AIProvider
            if config.ai.provider == "openai":
                provider = OpenAIRewriteClient(
                    api_key=require_env("OPENAI_API_KEY"),
                    model=config.ai.openai_model,
                    max_output_tokens=config.ai.max_output_tokens,
                )
            else:
                provider = ClaudeRewriteClient(
                    api_key=require_env("ANTHROPIC_API_KEY"),
                    model=config.ai.anthropic_model,
                    max_output_tokens=config.ai.max_output_tokens,
                )
            ai_pipeline = RewritePipeline(provider, config.ai)

        manager = SyncManager(
            config=config,
            state=state,
            converter=converter,
            github=github,
            google_drive=google_drive,
            google_docs=google_docs,
            onedrive=onedrive,
            ai_pipeline=ai_pipeline,
        )
        return Runtime(
            manager=manager,
            state=state,
            github=github,
            graph=graph,
            instance_lock=instance_lock,
        )
    except Exception:
        if graph:
            graph.close()
        if github:
            github.close()
        if state:
            state.close()
        instance_lock.close()
        raise
