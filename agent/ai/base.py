from __future__ import annotations

from typing import Protocol


class AIProvider(Protocol):
    def rewrite(self, markdown: str, *, instructions: str) -> str:
        """Return rewritten Markdown with no surrounding code fence."""
        ...
