from __future__ import annotations

import httpx

from client.proxy import ProxyServer


class _RequestStub:
    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers


def test_response_headers_strip_content_encoding_after_decode() -> None:
    response = httpx.Response(
        200,
        headers={
            "Content-Encoding": "gzip",
            "Content-Type": "application/json",
        },
    )

    forwarded = ProxyServer._response_headers(response)

    lowered_map = {key.lower(): value for key, value in forwarded.items()}
    assert "content-encoding" not in lowered_map
    assert lowered_map.get("content-type") == "application/json"


def test_response_headers_still_forward_regular_headers() -> None:
    response = httpx.Response(
        200,
        headers={
            "X-Request-Id": "req_123",
            "Cache-Control": "no-cache",
        },
    )

    forwarded = ProxyServer._response_headers(response)

    lowered_map = {key.lower(): value for key, value in forwarded.items()}
    assert lowered_map["x-request-id"] == "req_123"
    assert lowered_map["cache-control"] == "no-cache"


def test_upstream_headers_force_identity_encoding() -> None:
    proxy = ProxyServer(
        provider="openai",
        model="gpt-4.1-nano",
        api_key="real_key",
        temp_key="temp_key",
        token_budget=100,
    )

    request = _RequestStub(
        {
            "Authorization": "Bearer temp_key",
            "accept-encoding": "br, gzip",
            "X-Custom": "value",
        }
    )

    headers = proxy._build_upstream_headers(request)
    lowered_map = {key.lower(): value for key, value in headers.items()}

    assert lowered_map["authorization"] == "Bearer real_key"
    assert lowered_map["accept-encoding"] == "identity"
    assert lowered_map["x-custom"] == "value"
