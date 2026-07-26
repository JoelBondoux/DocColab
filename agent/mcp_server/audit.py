from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("doccolab.audit")


class AuditLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def record(
        self,
        *,
        user_id: str,
        tool: str,
        project_id: str | None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "user_id": user_id,
            "tool": tool,
            "project_id": project_id,
            "detail": detail or {},
        }
        line = json.dumps(event, separators=(",", ":"), default=str)
        with self._lock, self.path.open("a", encoding="utf-8") as output:
            output.write(line + "\n")
        logger.info(
            "user=%s tool=%s project=%s",
            user_id,
            tool,
            project_id or "-",
        )
