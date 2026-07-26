from __future__ import annotations

from collections.abc import Sequence

from agent.config import RewriteOperation

OPERATION_RULES: dict[RewriteOperation, str] = {
    "summarize": (
        "Condense the document while retaining its decisions, key evidence, caveats, "
        "and action items."
    ),
    "improve_clarity": (
        "Improve clarity, precision, transitions, and readability without changing meaning."
    ),
    "improve_structure": (
        "Improve section order, headings, paragraph grouping, and list structure."
    ),
    "expand_sections": (
        "Expand sections that are incomplete, using only information supported by the document. "
        "Mark genuinely missing facts with an explicit TODO instead of inventing them."
    ),
}


def build_rewrite_instructions(
    operations: Sequence[RewriteOperation],
    *,
    tone: str | None,
    style_rules: Sequence[str],
) -> str:
    tasks = "\n".join(f"- {OPERATION_RULES[operation]}" for operation in operations)
    rules = [
        "Return only the complete rewritten Markdown document.",
        "Do not wrap the result in a Markdown code fence.",
        "Preserve links, tables, list semantics, emphasis, and intentional formatting.",
        "Preserve front matter and stable identifiers exactly when present.",
        "Do not add claims, citations, names, dates, or numbers not supported by the input.",
    ]
    if tone:
        rules.append(f"Use this tone: {tone}.")
    rules.extend(style_rules)
    formatted_rules = "\n".join(f"- {rule}" for rule in rules)
    return (
        "You are the DocColab document rewriting engine.\n\n"
        "Apply these operations:\n"
        f"{tasks}\n\n"
        "Constraints:\n"
        f"{formatted_rules}"
    )
