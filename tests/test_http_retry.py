from __future__ import annotations

import httpx

from agent.github.github_client import GitHubClient
from agent.http_retry import RetryPolicy, request_with_retry
from agent.microsoft.graph_client import MicrosoftGraphClient


def _immediate_retry_policy() -> RetryPolicy:
    return RetryPolicy(
        max_attempts=3,
        base_delay_seconds=0,
        max_delay_seconds=0,
        jitter_seconds=0,
    )


def test_github_retries_transient_server_response() -> None:
    attempts = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, headers={"Retry-After": "0"})
        return httpx.Response(
            200,
            json={
                "type": "file",
                "sha": "blob",
                "content": "IyBSZWFkeQo=",
                "html_url": None,
            },
        )

    client = GitHubClient(
        token="token",
        owner="owner",
        repository="repo",
        transport=httpx.MockTransport(handler),
        retry_policy=_immediate_retry_policy(),
    )

    result = client.get_file("document.md", "main")
    client.close()

    assert result and result.content == "# Ready\n"
    assert attempts == 2


def test_graph_honors_retry_after_for_rate_limit() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(200, json={"value": []})

    graph = MicrosoftGraphClient(
        lambda: "token",
        base_url="https://graph.example",
        transport=httpx.MockTransport(handler),
        retry_policy=_immediate_retry_policy(),
        sleep=delays.append,
    )

    response = graph.request("GET", "/me")
    graph.close()

    assert response.status_code == 200
    assert attempts == 2
    assert delays == [2.0]


def test_non_idempotent_post_is_not_retried_after_server_error() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    response = request_with_retry(
        client,
        "POST",
        "https://example.test/resource",
        policy=RetryPolicy(max_attempts=4),
        sleep=lambda _: None,
    )
    client.close()

    assert response.status_code == 503
    assert calls == 1
