from __future__ import annotations

from openai import OpenAI


class OpenAIRewriteClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        max_output_tokens: int,
        client: OpenAI | None = None,
    ) -> None:
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.client = client or OpenAI(api_key=api_key)

    def rewrite(self, markdown: str, *, instructions: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            instructions=instructions,
            input=markdown,
            max_output_tokens=self.max_output_tokens,
        )
        result = response.output_text.strip()
        if not result:
            raise RuntimeError("OpenAI returned an empty document")
        return _strip_outer_fence(result)


def _strip_outer_fence(value: str) -> str:
    lines = value.splitlines()
    if len(lines) >= 2 and lines[0].strip().startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip() + "\n"
    return value.strip() + "\n"
