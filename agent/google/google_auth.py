from __future__ import annotations

import json
from collections.abc import Sequence
from contextlib import suppress

import keyring
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from agent.config import GoogleConfig

GOOGLE_SCOPES = (
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
)


class GoogleAuthenticator:
    """OAuth for an installed local application with OS keyring token storage."""

    def __init__(
        self,
        config: GoogleConfig,
        scopes: Sequence[str] = GOOGLE_SCOPES,
    ) -> None:
        self.config = config
        self.scopes = tuple(scopes)

    def authorize(self) -> Credentials:
        if not self.config.client_secrets_file.exists():
            raise FileNotFoundError(
                f"Google OAuth client file not found: {self.config.client_secrets_file}"
            )
        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.config.client_secrets_file),
            scopes=self.scopes,
        )
        credentials = flow.run_local_server(port=0, access_type="offline", prompt="consent")
        self._save(credentials)
        return credentials

    def credentials(self, *, interactive: bool = False) -> Credentials:
        payload = keyring.get_password(
            self.config.credential_keyring_service,
            self.config.credential_keyring_user,
        )
        credentials: Credentials | None = None
        if payload:
            credentials = Credentials.from_authorized_user_info(json.loads(payload), self.scopes)
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            self._save(credentials)
        if credentials and credentials.valid:
            return credentials
        if interactive:
            return self.authorize()
        raise RuntimeError("Google is not authenticated. Run: doccolab auth-google")

    def clear(self) -> None:
        with suppress(keyring.errors.PasswordDeleteError):
            keyring.delete_password(
                self.config.credential_keyring_service,
                self.config.credential_keyring_user,
            )

    def _save(self, credentials: Credentials) -> None:
        keyring.set_password(
            self.config.credential_keyring_service,
            self.config.credential_keyring_user,
            credentials.to_json(),
        )
