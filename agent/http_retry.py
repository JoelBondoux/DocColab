from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

_RETRYABLE_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})
_IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "PUT", "DELETE"})


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 4
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 10.0
    jitter_seconds: float = 0.25

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if min(
            self.base_delay_seconds,
            self.max_delay_seconds,
            self.jitter_seconds,
        ) < 0:
            raise ValueError("retry delays cannot be negative")


def request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    policy: RetryPolicy,
    sleep: Callable[[float], object] = time.sleep,
    **kwargs: Any,
) -> httpx.Response:
    normalized_method = method.upper()
    for attempt in range(1, policy.max_attempts + 1):
        try:
            response = client.request(normalized_method, url, **kwargs)
        except httpx.TransportError:
            if attempt == policy.max_attempts or normalized_method not in _IDEMPOTENT_METHODS:
                raise
            sleep(_backoff_delay(policy, attempt))
            continue

        if (
            response.status_code not in _RETRYABLE_STATUS_CODES
            or attempt == policy.max_attempts
            or normalized_method not in _IDEMPOTENT_METHODS
        ):
            return response
        retry_after = _retry_after_seconds(response)
        sleep(retry_after if retry_after is not None else _backoff_delay(policy, attempt))

    raise AssertionError("retry loop exhausted without a response")


def _backoff_delay(policy: RetryPolicy, attempt: int) -> float:
    exponential = policy.base_delay_seconds * (2 ** (attempt - 1))
    bounded = min(exponential, policy.max_delay_seconds)
    return bounded + secrets.SystemRandom().uniform(0, policy.jitter_seconds)


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        date_value = response.headers.get("Date")
        now = parsedate_to_datetime(date_value) if date_value else datetime.now(UTC)
        return max(0.0, (retry_at - now).total_seconds())
