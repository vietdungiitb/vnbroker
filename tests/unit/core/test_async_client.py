"""Tests for async HTTP client diagnostics."""

import asyncio

import httpx

from vnbroker.core.utils.async_client import (
    async_send_request,
    fetch_multiple_requests,
    get_async_request_stats,
    reset_async_request_stats,
)


class DummyResponse:
    def __init__(self, status_code: int, payload=None):
        self.status_code = status_code
        self._payload = payload or {"ok": True}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://example.com")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=request,
                response=response,
            )


class SequenceClient:
    def __init__(self, responses):
        self._responses = list(responses)

    async def request(self, method, url, **kwargs):
        result = self._responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def test_async_send_request_collects_success_stats(monkeypatch):
    reset_async_request_stats()

    async def fake_get_client(proxy_url=None):
        return SequenceClient([DummyResponse(200, {"value": 1})])

    monkeypatch.setattr(
        "vnbroker.core.utils.async_client.async_client_mgr.get_client",
        fake_get_client,
    )

    result = asyncio.run(
        async_send_request(
            url="https://example.com",
            headers={"accept": "application/json"},
            proxy_list=["http://127.0.0.1:8080"],
        )
    )

    stats = get_async_request_stats()
    assert result == {"value": 1}
    assert stats["total_requests"] == 1
    assert stats["successful_requests"] == 1
    assert stats["failed_requests"] == 0
    assert stats["total_attempts"] == 1
    assert stats["retry_attempts"] == 0
    assert stats["proxied_requests"] == 1
    assert stats["status_counts"][200] == 1


def test_async_send_request_collects_retry_stats(monkeypatch):
    reset_async_request_stats()

    async def fake_get_client(proxy_url=None):
        return SequenceClient([
            DummyResponse(429),
            DummyResponse(200, {"value": 2}),
        ])

    monkeypatch.setattr(
        "vnbroker.core.utils.async_client.async_client_mgr.get_client",
        fake_get_client,
    )

    result = asyncio.run(
        async_send_request(
            url="https://example.com",
            headers={"accept": "application/json"},
            retry_backoff_seconds=0,
        )
    )

    stats = get_async_request_stats()
    assert result == {"value": 2}
    assert stats["successful_requests"] == 1
    assert stats["failed_requests"] == 0
    assert stats["total_attempts"] == 2
    assert stats["retry_attempts"] == 1
    assert stats["throttled_responses"] == 1
    assert stats["status_counts"][429] == 1
    assert stats["status_counts"][200] == 1


def test_async_send_request_collects_timeout_stats(monkeypatch):
    reset_async_request_stats()

    async def fake_get_client(proxy_url=None):
        return SequenceClient([
            httpx.ReadTimeout("timed out"),
        ])

    monkeypatch.setattr(
        "vnbroker.core.utils.async_client.async_client_mgr.get_client",
        fake_get_client,
    )

    try:
        asyncio.run(
            async_send_request(
                url="https://example.com",
                headers={"accept": "application/json"},
                max_retries=0,
            )
        )
    except ConnectionError:
        pass
    else:
        raise AssertionError("Expected ConnectionError")

    stats = get_async_request_stats()
    assert stats["successful_requests"] == 0
    assert stats["failed_requests"] == 1
    assert stats["timeout_errors"] == 1
    assert stats["total_attempts"] == 1


def test_async_send_request_does_not_retry_non_transient_http_error(monkeypatch):
    reset_async_request_stats()

    async def fake_get_client(proxy_url=None):
        return SequenceClient([
            DummyResponse(404),
        ])

    monkeypatch.setattr(
        "vnbroker.core.utils.async_client.async_client_mgr.get_client",
        fake_get_client,
    )

    try:
        asyncio.run(
            async_send_request(
                url="https://example.com",
                headers={"accept": "application/json"},
                max_retries=3,
                retry_backoff_seconds=0,
            )
        )
    except ConnectionError:
        pass
    else:
        raise AssertionError("Expected ConnectionError")

    stats = get_async_request_stats()
    assert stats["total_attempts"] == 1
    assert stats["retry_attempts"] == 0
    assert stats["status_counts"][404] == 1
    assert stats["failed_requests"] == 1


def test_fetch_multiple_requests_preserves_input_order(monkeypatch):
    async def fake_async_send_request(**kwargs):
        idx = kwargs["proxy_idx"]
        return {"idx": idx, "url": kwargs["url"]}

    monkeypatch.setattr(
        "vnbroker.core.utils.async_client.async_send_request",
        fake_async_send_request,
    )

    requests_list = [
        {"url": "https://example.com/2", "headers": {}, "proxy_idx": 2},
        {"url": "https://example.com/0", "headers": {}, "proxy_idx": 0},
        {"url": "https://example.com/1", "headers": {}, "proxy_idx": 1},
    ]

    result = asyncio.run(fetch_multiple_requests(requests_list, max_concurrency=2))

    assert [item["idx"] for item in result] == [2, 0, 1]


def test_fetch_multiple_requests_honors_max_concurrency(monkeypatch):
    state = {"active": 0, "peak": 0}

    async def fake_async_send_request(**kwargs):
        state["active"] += 1
        state["peak"] = max(state["peak"], state["active"])
        await asyncio.sleep(0.01)
        state["active"] -= 1
        return {"ok": True}

    monkeypatch.setattr(
        "vnbroker.core.utils.async_client.async_send_request",
        fake_async_send_request,
    )

    requests_list = [
        {"url": f"https://example.com/{i}", "headers": {}}
        for i in range(8)
    ]

    result = asyncio.run(fetch_multiple_requests(requests_list, max_concurrency=3))

    assert len(result) == 8
    assert all(item == {"ok": True} for item in result)
    assert state["peak"] <= 3


def test_rate_limiter_survives_sequential_event_loops():
    """BL-1 fail-before: contention in loop 1 binds a module-scope lock; loop 2 contends too."""
    from vnbroker.core.utils.async_client import TokenBucketRateLimiter

    limiter = TokenBucketRateLimiter(rpm=600)

    async def hammer(n):
        async def one():
            async with limiter:
                return True

        return await asyncio.gather(*[one() for _ in range(n)])

    assert asyncio.run(hammer(610)) == [True] * 610
    assert asyncio.run(hammer(10)) == [True] * 10


def test_client_manager_isolates_clients_per_event_loop():
    """BL-1: sharing one httpx client across loops is unsupported; each loop gets its own."""
    from vnbroker.core.utils.async_client import AsyncClientManager

    mgr = AsyncClientManager()

    async def get_one():
        return await mgr.get_client(None)

    async def shutdown():
        await mgr.close()

    c1 = asyncio.run(get_one())
    c2 = asyncio.run(get_one())
    try:
        assert c1 is not c2
    finally:
        asyncio.run(shutdown())


def test_import_creates_no_loop_bound_lock():
    """Guard: importing the module must not create any asyncio.Lock object."""
    import asyncio as _asyncio

    from vnbroker.core.utils import async_client as _ac

    for obj in (_ac.RATE_LIMITER, _ac.async_client_mgr):
        for value in vars(obj).values():
            assert not isinstance(value, _asyncio.Lock), (
                "module-scope object holds a loop-bound asyncio.Lock"
            )