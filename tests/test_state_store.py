from pathlib import Path

from agent.models import DocumentState, SyncStatus
from agent.sync.state_store import StateStore


def test_pending_sync_state_survives_store_reopen(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    store = StateStore(path)
    store.ensure_document("document")
    store.save_document(
        DocumentState(
            document_id="document",
            status=SyncStatus.SYNCING,
            pending_markdown="# Pending\n",
            pending_blob_sha="blob",
            pending_commit_sha="commit",
            pending_source="ai",
            pending_version=3,
            pending_surfaces="google,microsoft",
        )
    )
    store.close()

    reopened = StateStore(path)
    state = reopened.get_document("document")
    reopened.close()

    assert state.status == SyncStatus.SYNCING
    assert state.pending_markdown == "# Pending\n"
    assert state.pending_surfaces == "google,microsoft"
