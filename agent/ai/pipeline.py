from __future__ import annotations

from collections.abc import Sequence

from agent.ai.base import AIProvider
from agent.ai.prompt import build_rewrite_instructions
from agent.config import AIConfig, RewriteOperation


class RewritePipeline:
    def __init__(self, provider: AIProvider, config: AIConfig) -> None:
        self.provider = provider
        self.config = config

    def rewrite(
        self,
        markdown: str,
        operations: Sequence[RewriteOperation] | None = None,
    ) -> str:
        selected = list(operations or self.config.operations)
        instructions = build_rewrite_instructions(
            selected,
            tone=self.config.tone,
            style_rules=self.config.style_rules,
        )
        return self.provider.rewrite(markdown, instructions=instructions)

    def summarize(self, markdown: str) -> str:
        return self.rewrite(markdown, ["summarize"])

    def improve_clarity(self, markdown: str) -> str:
        return self.rewrite(markdown, ["improve_clarity"])

    def improve_structure(self, markdown: str) -> str:
        return self.rewrite(markdown, ["improve_structure"])

    def expand_sections(self, markdown: str) -> str:
        return self.rewrite(markdown, ["expand_sections"])
