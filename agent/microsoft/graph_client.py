from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

from agent.http_retry import RetryPolicy, request_with_retry


class MicrosoftGraphClient:
    def __init__(
        self,
        token_provider: Callable[[], str],
        *,
        base_url: str = "https://graph.microsoft.com/v1.0",
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
        retry_policy: RetryPolicy | None = None,
        sleep: Callable[[float], object] = time.sleep,
    ) -> None:
        self.token_provider = token_provider
        self.retry_policy = retry_policy or RetryPolicy()
        self.sleep = sleep
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
        response = self._request(method, path_or_url, headers=headers, **kwargs)
        if response.status_code == 401 and retry_auth:
            headers["Authorization"] = f"Bearer {self.token_provider()}"
            response = self._request(method, path_or_url, headers=headers, **kwargs)
        response.raise_for_status()
        return response

    def json(self, method: str, path_or_url: str, **kwargs: Any) -> dict[str, Any]:
        response = self.request(method, path_or_url, **kwargs)
        return dict(response.json())

    def close(self) -> None:
        self.client.close()

    def _request(self, method: str, path_or_url: str, **kwargs: Any) -> httpx.Response:
        return request_with_retry(
            self.client,
            method,
            path_or_url,
            policy=self.retry_policy,
            sleep=self.sleep,
            **kwargs,
        )
