from __future__ import annotations

import os
from collections.abc import Mapping

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

SERVICE_NAME = "doccolab-secrets"
STANDARD_SECRET_NAMES = (
    "GITHUB_TOKEN",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_WEBHOOK_TOKEN",
)


def require_secret(name: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    try:
        value = keyring.get_password(SERVICE_NAME, name)
    except KeyringError as exc:
        raise RuntimeError(
            f"Required secret {name} is not set in the environment and the OS "
            f"keyring is unavailable: {type(exc).__name__}"
        ) from exc
    if not value:
        raise RuntimeError(
            f"Required secret {name} is not set in the environment or OS keyring"
        )
    return value


def set_secret(name: str, value: str) -> None:
    if not value:
        raise ValueError("Secret value cannot be empty")
    try:
        keyring.set_password(SERVICE_NAME, name, value)
    except KeyringError as exc:
        raise RuntimeError(
            f"Unable to store {name} in the OS keyring: {type(exc).__name__}"
        ) from exc


def delete_secret(name: str) -> bool:
    try:
        keyring.delete_password(SERVICE_NAME, name)
    except PasswordDeleteError:
        return False
    except KeyringError as exc:
        raise RuntimeError(
            f"Unable to remove the {name} keyring entry: {type(exc).__name__}"
        ) from exc
    return True


def save_secrets(values: Mapping[str, str]) -> None:
    pending = {name: value for name, value in values.items() if value}
    if not pending:
        return
    try:
        previous = {
            name: keyring.get_password(SERVICE_NAME, name) for name in pending
        }
    except KeyringError as exc:
        raise RuntimeError(
            f"Unable to read the OS keyring before setup: {type(exc).__name__}"
        ) from exc

    updated: list[str] = []
    try:
        for name, value in pending.items():
            keyring.set_password(SERVICE_NAME, name, value)
            updated.append(name)
    except KeyringError as exc:
        for name in reversed(updated):
            try:
                old_value = previous[name]
                if old_value is None:
                    keyring.delete_password(SERVICE_NAME, name)
                else:
                    keyring.set_password(SERVICE_NAME, name, old_value)
            except KeyringError:
                pass
        raise RuntimeError(
            f"Unable to store setup secrets in the OS keyring: {type(exc).__name__}"
        ) from exc
