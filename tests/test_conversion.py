from agent.conversion.docx_to_md import docx_to_markdown
from agent.conversion.md_to_docx import markdown_to_docx


def test_markdown_docx_roundtrip_preserves_required_structures() -> None:
    markdown = """# Release plan

This is **important**, *careful*, and [reviewable](https://example.com).

- First item
- Second item

| Owner | Status |
| --- | --- |
| Alex | Ready |
"""

    docx = markdown_to_docx(markdown)
    restored = docx_to_markdown(docx)

    assert docx.startswith(b"PK")
    assert "# Release plan" in restored
    assert "**important**" in restored
    assert "*careful*" in restored
    assert "[reviewable](https://example.com)" in restored
    assert "- First item" in restored
    assert "| **Owner** | **Status** |" in restored
    assert "| Alex | Ready |" in restored
