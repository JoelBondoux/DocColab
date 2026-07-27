from types import SimpleNamespace

from anthropic.types import TextBlock

from agent.ai.claude_client import ClaudeRewriteClient
from agent.ai.openai_client import OpenAIRewriteClient
from agent.ai.pipeline import RewritePipeline
from agent.config import AIConfig


def test_openai_client_uses_responses_api_and_removes_outer_fence() -> None:
    calls = []
    fake = SimpleNamespace(
        responses=SimpleNamespace(
            create=lambda **kwargs: (
                calls.append(kwargs)
                or SimpleNamespace(output_text="```markdown\n# Revised\n```")
            )
        )
    )
    client = OpenAIRewriteClient(
        api_key="test",
        model="gpt-test",
        max_output_tokens=1000,
        client=fake,
    )

    result = client.rewrite("# Draft\n", instructions="Improve it")

    assert result == "# Revised\n"
    assert calls[0]["model"] == "gpt-test"
    assert calls[0]["input"] == "# Draft\n"
    assert calls[0]["max_output_tokens"] == 1000


def test_claude_client_uses_messages_api_without_sampling_parameters() -> None:
    calls = []
    fake = SimpleNamespace(
        messages=SimpleNamespace(
            create=lambda **kwargs: (
                calls.append(kwargs)
                or SimpleNamespace(
                    content=[TextBlock(type="text", text="# Revised")],
                    stop_reason="end_turn",
                )
            )
        )
    )
    client = ClaudeRewriteClient(
        api_key="test",
        model="claude-test",
        max_output_tokens=1000,
        client=fake,
    )

    result = client.rewrite("# Draft\n", instructions="Improve it")

    assert result == "# Revised\n"
    assert calls[0]["model"] == "claude-test"
    assert "temperature" not in calls[0]
    assert calls[0]["system"] == "Improve it"


def test_pipeline_builds_operation_tone_and_style_instructions() -> None:
    captured = {}

    class Provider:
        def rewrite(self, markdown: str, *, instructions: str) -> str:
            captured["markdown"] = markdown
            captured["instructions"] = instructions
            return "# Result\n"

    config = AIConfig(
        operations=["summarize", "improve_clarity"],
        tone="warm",
        style_rules=["Use UK spelling."],
    )

    result = RewritePipeline(Provider(), config).rewrite("# Input\n")

    assert result == "# Result\n"
    assert "Condense the document" in captured["instructions"]
    assert "Improve clarity" in captured["instructions"]
    assert "Use this tone: warm." in captured["instructions"]
    assert "Use UK spelling." in captured["instructions"]
