from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Literal, cast

AIProvider = Literal["openai", "anthropic", "none"]
InputFunction = Callable[[str], str]
OutputFunction = Callable[[str], None]


def ask(
    label: str,
    *,
    input_fn: InputFunction,
    default: str | None = None,
    required: bool = True,
    validator: Callable[[str], bool] | None = None,
    error: str = "Please enter a valid value.",
) -> str:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        value = input_fn(f"{label}{suffix}: ").strip()
        if not value and default is not None:
            value = default
        if not value and not required:
            return ""
        if value and (validator is None or validator(value)):
            return value
        print(error)


def yes_no(label: str, default: bool, input_fn: InputFunction) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        value = input_fn(f"{label} [{suffix}]: ").strip().lower()
        if not value:
            return default
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        print("Enter yes or no.")


def choice(
    label: str,
    choices: tuple[AIProvider, ...],
    default: AIProvider,
    input_fn: InputFunction,
) -> AIProvider:
    rendered = "/".join(choices)
    while True:
        value = input_fn(f"{label} ({rendered}) [{default}]: ").strip().lower()
        selected = value or default
        if selected in choices:
            return cast(AIProvider, selected)
        print(f"Choose one of: {', '.join(choices)}.")


def valid_project_id(value: str) -> bool:
    return re.fullmatch(r"[a-z0-9][a-z0-9-]*", value) is not None


def valid_hostname(value: str) -> bool:
    return (
        len(value) <= 253
        and re.fullmatch(
            r"(?=.{1,253}\Z)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*"
            r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?",
            value,
        )
        is not None
    )


def valid_exposed_input(value: str) -> bool:
    folders = tuple(
        part.strip().replace("\\", "/") for part in value.split(",") if part.strip()
    )
    if "documents" not in folders:
        return False
    return all(
        not Path(folder).is_absolute()
        and ".." not in Path(folder).parts
        and bool(Path(folder).parts)
        for folder in folders
    )


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "project"
