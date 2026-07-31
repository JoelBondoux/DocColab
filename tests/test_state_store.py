from datetime import UTC, datetime, timedelta
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


def test_backup_is_consistent_and_events_can_be_pruned(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    backup_path = tmp_path / "backups" / "state.db"
    store = StateStore(path)
    store.ensure_document("document")
    assert store.remember_event("old-event", "google")

    removed = store.prune_events(datetime.now(UTC) + timedelta(seconds=1))
    store.backup(backup_path)
    store.close()

    backup = StateStore(backup_path)
    assert backup.integrity_check() == "ok"
    assert backup.get_document("document").document_id == "document"
    backup.close()

    assert removed == 1

    reopened = StateStore(path)
    assert reopened.remember_event("old-event", "google")
    reopened.close()
