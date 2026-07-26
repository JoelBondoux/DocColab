from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress

import keyring
import msal

from agent.config import MicrosoftConfig, require_env


class MicrosoftAuthenticator:
    """Delegated Microsoft Graph auth using device flow and an OS keyring cache."""

    def __init__(self, config: MicrosoftConfig) -> None:
        self.config = config
        self.client_id = require_env(config.client_id_env)
        self.cache = msal.SerializableTokenCache()
        cached = keyring.get_password(
            config.credential_keyring_service,
            config.credential_keyring_user,
        )
        if cached:
            self.cache.deserialize(cached)
        self.app = msal.PublicClientApplication(
            client_id=self.client_id,
            authority=f"https://login.microsoftonline.com/{config.tenant}",
            token_cache=self.cache,
        )

    def access_token(
        self,
        *,
        interactive: bool = False,
        message_callback: Callable[[str], None] = print,
    ) -> str:
        result = None
        accounts = self.app.get_accounts()
        if accounts:
            result = self.app.acquire_token_silent(self.config.scopes, account=accounts[0])
        if not result and interactive:
            flow = self.app.initiate_device_flow(scopes=self.config.scopes)
            if "user_code" not in flow:
                raise RuntimeError(f"Unable to start Microsoft device flow: {flow}")
            message_callback(flow["message"])
            result = self.app.acquire_token_by_device_flow(flow)
        self._persist_cache()
        if result and "access_token" in result:
            return str(result["access_token"])
        if result:
            description = result.get("error_description") or result.get("error") or result
            raise RuntimeError(f"Microsoft authentication failed: {description}")
        raise RuntimeError("Microsoft is not authenticated. Run: doccolab auth-microsoft")

    def authorize(self, message_callback: Callable[[str], None] = print) -> str:
        return self.access_token(interactive=True, message_callback=message_callback)

    def clear(self) -> None:
        with suppress(keyring.errors.PasswordDeleteError):
            keyring.delete_password(
                self.config.credential_keyring_service,
                self.config.credential_keyring_user,
            )

    def _persist_cache(self) -> None:
        if self.cache.has_state_changed:
            keyring.set_password(
                self.config.credential_keyring_service,
                self.config.credential_keyring_user,
                self.cache.serialize(),
            )
