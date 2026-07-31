from __future__ import annotations

from anthropic import Anthropic
from anthropic.types import TextBlock

from agent.ai.openai_client import _strip_outer_fence


class ClaudeRewriteClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        max_output_tokens: int,
        client: Anthropic | None = None,
    ) -> None:
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.client = client or Anthropic(api_key=api_key)

    def rewrite(self, markdown: str, *, instructions: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_output_tokens,
            system=instructions,
            messages=[{"role": "user", "content": markdown}],
        )
        result = "".join(
            block.text for block in response.content if isinstance(block, TextBlock)
        ).strip()
        if not result:
            stop_reason = getattr(response, "stop_reason", None)
            raise RuntimeError(f"Claude returned no text (stop_reason={stop_reason})")
        return _strip_outer_fence(result)
