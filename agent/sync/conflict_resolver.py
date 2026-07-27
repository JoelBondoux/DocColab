from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from agent.models import MergeResult


@dataclass(frozen=True, slots=True)
class _Change:
    source: str
    start: int
    end: int
    replacement: tuple[str, ...]


class ConflictResolver:
    """Line-oriented three-way merge that refuses ambiguous overlapping edits."""

    def merge(self, base: str, versions: dict[str, str]) -> MergeResult:
        normalized_base = _normalize(base)
        normalized_versions = {
            source: _normalize(markdown) for source, markdown in versions.items()
        }
        unique_values = set(normalized_versions.values())
        if not unique_values:
            return MergeResult(normalized_base, False)
        if len(unique_values) == 1:
            return MergeResult(next(iter(unique_values)), False)

        changes: list[_Change] = []
        for source, markdown in normalized_versions.items():
            if markdown == normalized_base:
                continue
            changes.extend(_changes(normalized_base, markdown, source))

        deduplicated: list[_Change] = []
        for change in changes:
            equivalent = next(
                (
                    existing
                    for existing in deduplicated
                    if existing.start == change.start
                    and existing.end == change.end
                    and existing.replacement == change.replacement
                ),
                None,
            )
            if equivalent:
                continue
            if any(_overlaps(change, existing) for existing in deduplicated):
                sources = tuple(sorted(normalized_versions))
                return MergeResult(
                    markdown=_conflict_document(normalized_versions),
                    conflicted=True,
                    conflict_sources=sources,
                )
            deduplicated.append(change)

        base_lines = normalized_base.splitlines(keepends=True)
        for change in sorted(deduplicated, key=lambda item: (item.start, item.end), reverse=True):
            base_lines[change.start : change.end] = change.replacement
        return MergeResult(_normalize("".join(base_lines)), False)


def _changes(base: str, changed: str, source: str) -> list[_Change]:
    base_lines = base.splitlines(keepends=True)
    changed_lines = changed.splitlines(keepends=True)
    matcher = SequenceMatcher(a=base_lines, b=changed_lines, autojunk=False)
    return [
        _Change(source, i1, i2, tuple(changed_lines[j1:j2]))
        for tag, i1, i2, j1, j2 in matcher.get_opcodes()
        if tag != "equal"
    ]


def _overlaps(left: _Change, right: _Change) -> bool:
    if left.start == left.end and right.start == right.end:
        return left.start == right.start
    if left.start == left.end:
        return right.start <= left.start < right.end
    if right.start == right.end:
        return left.start <= right.start < left.end
    return max(left.start, right.start) < min(left.end, right.end)


def _conflict_document(versions: dict[str, str]) -> str:
    parts: list[str] = []
    items = list(versions.items())
    first_source, first_value = items[0]
    parts.extend([f"<<<<<<< {first_source.upper()}\n", first_value])
    for source, value in items[1:]:
        parts.extend(["=======\n", f"<!-- {source.upper()} -->\n", value])
    parts.append(">>>>>>> DOCCOLAB CONFLICT\n")
    return _normalize("".join(parts))


def _normalize(markdown: str) -> str:
    value = markdown.replace("\r\n", "\n").replace("\r", "\n").rstrip()
    return value + "\n" if value else ""
