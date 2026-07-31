from __future__ import annotations

import sqlite3
import threading
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent.models import DocumentState, SyncStatus, utc_now


class StateStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.RLock()
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        with self.connection:
            self.connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    base_markdown TEXT NOT NULL DEFAULT '',
                    canonical_hash TEXT NOT NULL DEFAULT '',
                    google_version TEXT,
                    microsoft_version TEXT,
                    github_blob_sha TEXT,
                    version INTEGER NOT NULL DEFAULT 0,
                    last_writer TEXT,
                    status TEXT NOT NULL DEFAULT 'ready',
                    last_error TEXT,
                    updated_at TEXT,
                    pending_markdown TEXT,
                    pending_blob_sha TEXT,
                    pending_commit_sha TEXT,
                    pending_source TEXT,
                    pending_version INTEGER,
                    pending_surfaces TEXT
                );

                CREATE TABLE IF NOT EXISTS cursors (
                    provider TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    cursor TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (provider, scope)
                );

                CREATE TABLE IF NOT EXISTS google_watches (
                    channel_id TEXT PRIMARY KEY,
                    resource_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    verification_token TEXT NOT NULL,
                    expiration_ms INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    event_key TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    received_at TEXT NOT NULL
                );
                """
            )
            self._add_missing_document_columns()

    def _add_missing_document_columns(self) -> None:
        existing = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(documents)").fetchall()
        }
        additions = {
            "pending_markdown": "TEXT",
            "pending_blob_sha": "TEXT",
            "pending_commit_sha": "TEXT",
            "pending_source": "TEXT",
            "pending_version": "INTEGER",
            "pending_surfaces": "TEXT",
        }
        for column, data_type in additions.items():
            if column not in existing:
                self.connection.execute(
                    f"ALTER TABLE documents ADD COLUMN {column} {data_type}"
                )

    def ensure_document(self, document_id: str) -> DocumentState:
        with self._lock, self.connection:
            self.connection.execute(
                "INSERT OR IGNORE INTO documents (document_id) VALUES (?)",
                (document_id,),
            )
        return self.get_document(document_id)

    def get_document(self, document_id: str) -> DocumentState:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM documents WHERE document_id = ?",
                (document_id,),
            ).fetchone()
        if row is None:
            raise KeyError(document_id)
        return DocumentState(**dict(row))

    def save_document(self, state: DocumentState) -> None:
        values = asdict(state)
        parameters = [
            values["base_markdown"],
            values["canonical_hash"],
            values["google_version"],
            values["microsoft_version"],
            values["github_blob_sha"],
            values["version"],
            values["last_writer"],
            values["status"],
            values["last_error"],
            values["updated_at"],
            values["pending_markdown"],
            values["pending_blob_sha"],
            values["pending_commit_sha"],
            values["pending_source"],
            values["pending_version"],
            values["pending_surfaces"],
            state.document_id,
        ]
        with self._lock, self.connection:
            self.connection.execute(
                """
                UPDATE documents SET
                    base_markdown = ?,
                    canonical_hash = ?,
                    google_version = ?,
                    microsoft_version = ?,
                    github_blob_sha = ?,
                    version = ?,
                    last_writer = ?,
                    status = ?,
                    last_error = ?,
                    updated_at = ?,
                    pending_markdown = ?,
                    pending_blob_sha = ?,
                    pending_commit_sha = ?,
                    pending_source = ?,
                    pending_version = ?,
                    pending_surfaces = ?
                WHERE document_id = ?
                """,
                parameters,
            )

    def mark_error(self, document_id: str, error: str) -> None:
        state = self.ensure_document(document_id)
        self.save_document(
            DocumentState(
                **{
                    **asdict(state),
                    "status": SyncStatus.ERROR,
                    "last_error": error,
                    "updated_at": utc_now(),
                }
            )
        )

    def get_cursor(self, provider: str, scope: str) -> str | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT cursor FROM cursors WHERE provider = ? AND scope = ?",
                (provider, scope),
            ).fetchone()
        return str(row["cursor"]) if row else None

    def set_cursor(self, provider: str, scope: str, cursor: str) -> None:
        with self._lock, self.connection:
            self.connection.execute(
                """
                INSERT INTO cursors (provider, scope, cursor, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(provider, scope) DO UPDATE SET
                    cursor = excluded.cursor,
                    updated_at = excluded.updated_at
                """,
                (provider, scope, cursor, utc_now()),
            )

    def save_google_watch(
        self,
        *,
        channel_id: str,
        resource_id: str,
        document_id: str,
        verification_token: str,
        expiration_ms: int,
    ) -> None:
        with self._lock, self.connection:
            self.connection.execute(
                """
                INSERT INTO google_watches (
                    channel_id, resource_id, document_id, verification_token,
                    expiration_ms, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(channel_id) DO UPDATE SET
                    resource_id = excluded.resource_id,
                    document_id = excluded.document_id,
                    verification_token = excluded.verification_token,
                    expiration_ms = excluded.expiration_ms,
                    updated_at = excluded.updated_at
                """,
                (
                    channel_id,
                    resource_id,
                    document_id,
                    verification_token,
                    expiration_ms,
                    utc_now(),
                ),
            )

    def google_watch(self, channel_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM google_watches WHERE channel_id = ?",
                (channel_id,),
            ).fetchone()
        return dict(row) if row else None

    def watches_for_document(self, document_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT * FROM google_watches WHERE document_id = ?",
                (document_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_google_watch(self, channel_id: str) -> None:
        with self._lock, self.connection:
            self.connection.execute(
                "DELETE FROM google_watches WHERE channel_id = ?",
                (channel_id,),
            )

    def remember_event(self, event_key: str, provider: str) -> bool:
        try:
            with self._lock, self.connection:
                self.connection.execute(
                    "INSERT INTO events (event_key, provider, received_at) VALUES (?, ?, ?)",
                    (event_key, provider, utc_now()),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def prune_events(self, older_than: datetime) -> int:
        if older_than.tzinfo is None:
            raise ValueError("older_than must be timezone-aware")
        cutoff = older_than.astimezone(UTC).isoformat()
        with self._lock, self.connection:
            cursor = self.connection.execute(
                "DELETE FROM events WHERE received_at < ?",
                (cutoff,),
            )
        return max(0, cursor.rowcount)

    def backup(self, destination: Path) -> None:
        destination = destination.resolve()
        if destination == self.path.resolve():
            raise ValueError("Backup destination must differ from the active database")
        if destination.exists():
            raise FileExistsError(f"Backup already exists: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        backup_connection = sqlite3.connect(destination)
        try:
            with self._lock:
                self.connection.backup(backup_connection)
        finally:
            backup_connection.close()

    def integrity_check(self) -> str:
        with self._lock:
            row = self.connection.execute("PRAGMA integrity_check").fetchone()
        return str(row[0]) if row else "no result"

    def close(self) -> None:
        self.connection.close()
