from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx


class MicrosoftGraphClient:
    def __init__(
        self,
        token_provider: Callable[[], str],
        *,
        base_url: str = "https://graph.microsoft.com/v1.0",
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.token_provider = token_provider
        self.client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
        )

    def request(
        self,
        method: str,
        path_or_url: str,
        *,
        retry_auth: bool = True,
        **kwargs: Any,
    ) -> httpx.Response:
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {self.token_provider()}"
        headers.setdefault("Accept", "application/json")
        response = self.client.request(method, path_or_url, headers=headers, **kwargs)
        if response.status_code == 401 and retry_auth:
            headers["Authorization"] = f"Bearer {self.token_provider()}"
            response = self.client.request(method, path_or_url, headers=headers, **kwargs)
        response.raise_for_status()
        return response

    def json(self, method: str, path_or_url: str, **kwargs: Any) -> dict[str, Any]:
        response = self.request(method, path_or_url, **kwargs)
        return dict(response.json())

    def close(self) -> None:
        self.client.close()
