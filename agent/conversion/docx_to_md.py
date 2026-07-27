from __future__ import annotations

import io
import re
from collections.abc import Iterator
from typing import Any

from docx import Document
from docx.document import Document as DocumentObject
from docx.oxml.ns import qn
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph
from docx.text.run import Run


def docx_to_markdown(docx: bytes) -> str:
    """Pure-Python DOCX fallback preserving common document structures."""
    document = Document(io.BytesIO(docx))
    output: list[str] = []
    for block in _iter_blocks(document):
        if isinstance(block, Paragraph):
            value = _paragraph_to_markdown(block)
            if value:
                output.append(value)
        else:
            output.append(_table_to_markdown(block))
    return "\n\n".join(part.rstrip() for part in output if part.strip()).strip() + "\n"


def _iter_blocks(parent: DocumentObject | _Cell) -> Iterator[Paragraph | Table]:
    parent_element = parent.element.body if isinstance(parent, DocumentObject) else parent._tc
    for child in parent_element.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, parent)
        elif child.tag == qn("w:tbl"):
            yield Table(child, parent)


def _paragraph_to_markdown(paragraph: Paragraph) -> str:
    content = _paragraph_inline(paragraph).strip()
    if not content:
        return ""
    style = (paragraph.style.name if paragraph.style else "").lower()
    if style.startswith("heading"):
        match = re.search(r"(\d+)", style)
        level = min(int(match.group(1)), 6) if match else 1
        return f"{'#' * level} {content}"
    if "list bullet" in style or _numbering_format(paragraph) == "bullet":
        return f"- {content}"
    if "list number" in style or _numbering_format(paragraph) == "number":
        return f"1. {content}"
    if "quote" in style:
        return "\n".join(f"> {line}" for line in content.splitlines())
    return content


def _paragraph_inline(paragraph: Paragraph) -> str:
    parts: list[str] = []
    for child in paragraph._p.iterchildren():
        if child.tag == qn("w:r"):
            parts.append(_run_markdown(Run(child, paragraph)))
        elif child.tag == qn("w:hyperlink"):
            text = "".join(_run_markdown(Run(run, paragraph)) for run in child.findall(qn("w:r")))
            relationship_id = child.get(qn("r:id"))
            anchor = child.get(qn("w:anchor"))
            target = ""
            if relationship_id and relationship_id in paragraph.part.rels:
                target = paragraph.part.rels[relationship_id].target_ref
            elif anchor:
                target = f"#{anchor}"
            parts.append(f"[{text}]({target})" if target else text)
    return "".join(parts)


def _run_markdown(run: Run) -> str:
    text = run.text.replace("\\", "\\\\").replace("*", "\\*").replace("_", "\\_")
    if not text:
        return ""
    if run.bold:
        text = f"**{text}**"
    if run.italic:
        text = f"*{text}*"
    if run.style and "code" in run.style.name.lower():
        text = f"`{text}`"
    return text


def _numbering_format(paragraph: Paragraph) -> str | None:
    properties = paragraph._p.pPr
    if properties is None:
        return None
    numbering_properties = properties.find(qn("w:numPr"))
    if numbering_properties is None:
        return None
    num_id_element = numbering_properties.find(qn("w:numId"))
    if num_id_element is None:
        return None
    num_id = num_id_element.get(qn("w:val"))
    if num_id is None:
        return None
    try:
        part: Any = paragraph.part
        numbering = part.numbering_part.element
        abstract_id = numbering.xpath(
            f"./w:num[@w:numId='{num_id}']/w:abstractNumId/@w:val"
        )
        if not abstract_id:
            return "number"
        formats = numbering.xpath(
            f"./w:abstractNum[@w:abstractNumId='{abstract_id[0]}']/w:lvl/w:numFmt/@w:val"
        )
        return "bullet" if "bullet" in formats else "number"
    except (AttributeError, IndexError):
        return "number"


def _table_to_markdown(table: Table) -> str:
    rows: list[list[str]] = []
    for row in table.rows:
        values = [
            "<br>".join(
                _paragraph_inline(paragraph).strip().replace("|", "\\|")
                for paragraph in cell.paragraphs
                if _paragraph_inline(paragraph).strip()
            )
            for cell in row.cells
        ]
        rows.append(values)
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    lines = ["| " + " | ".join(normalized[0]) + " |"]
    lines.append("| " + " | ".join("---" for _ in range(width)) + " |")
    lines.extend("| " + " | ".join(row) + " |" for row in normalized[1:])
    return "\n".join(lines)
