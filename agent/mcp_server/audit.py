from __future__ import annotations

import json
import logging
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("doccolab.audit")


class AuditLogger:
    def __init__(
        self,
        path: Path,
        *,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 10,
    ) -> None:
        self.path = path
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def record(
        self,
        *,
        user_id: str,
        tool: str,
        project_id: str | None,
        outcome: str = "authorized",
        detail: dict[str, Any] | None = None,
    ) -> None:
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "user_id": user_id,
            "tool": tool,
            "project_id": project_id,
            "outcome": outcome,
            "detail": detail or {},
        }
        line = json.dumps(event, separators=(",", ":"), default=str)
        encoded_size = len((line + "\n").encode("utf-8"))
        with self._lock:
            self._rotate_if_needed(encoded_size)
            with self.path.open("a", encoding="utf-8") as output:
                output.write(line + "\n")
            if os.name != "nt":
                self.path.chmod(0o600)
        logger.info(
            "user=%s tool=%s project=%s outcome=%s",
            user_id,
            tool,
            project_id or "-",
            outcome,
        )

    def _rotate_if_needed(self, incoming_bytes: int) -> None:
        if not self.path.exists() or self.path.stat().st_size + incoming_bytes <= self.max_bytes:
            return
        oldest = Path(f"{self.path}.{self.backup_count}")
        if oldest.exists():
            oldest.unlink()
        for index in range(self.backup_count - 1, 0, -1):
            source = Path(f"{self.path}.{index}")
            if source.exists():
                os.replace(source, Path(f"{self.path}.{index + 1}"))
        os.replace(self.path, Path(f"{self.path}.1"))
