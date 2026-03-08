"""
Utility functions shared across ALL/some provider implementations. For utils specific to
one single provider, put them in that provider's module (e.g. client.providers.openai.utils).
"""

import os
from typing import TypedDict

import httpx


class ProviderCfg(TypedDict):
    base_url: str
    auth_header: str
    auth_prefix: str
    extra_headers: dict[str, str]


def build_auth_headers(provider_config: ProviderCfg, api_key: str) -> dict[str, str]:
    auth_header: str = provider_config["auth_header"]
    auth_prefix: str = provider_config["auth_prefix"]
    extra_headers: dict[str, str] = provider_config["extra_headers"]
    return {
        auth_header: auth_prefix + api_key,
        **extra_headers,
    }


def _server_http_base_url() -> str:
    server_url = os.environ.get("TOKENHUB_SERVER", "ws://localhost:8080").strip()
    if server_url.startswith("ws://"):
        return "http://" + server_url[len("ws://") :].rstrip("/")
    if server_url.startswith("wss://"):
        return "https://" + server_url[len("wss://") :].rstrip("/")
    return server_url.rstrip("/")


async def fetch_server_supported_models(provider: str) -> tuple[list[str], str]:
    if not provider:
        return [], "Provider is required"

    base_url = _server_http_base_url()
    url = f"{base_url}/providers/models"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url, params={"provider": provider})
        except httpx.RequestError as e:
            return [], f"Network error: {e}"

    if resp.status_code != 200:
        return [], f"Server model list fetch failed (HTTP {resp.status_code})"

    try:
        payload = resp.json()
    except ValueError:
        return [], "Server model list fetch failed (invalid JSON response)"

    models = payload.get("models")
    if not isinstance(models, list):
        return [], "Server model list fetch failed (invalid payload)"

    filtered: list[str] = []
    seen: set[str] = set()
    for model in models:
        if isinstance(model, str) and model and model not in seen:
            seen.add(model)
            filtered.append(model)

    if not filtered:
        return [], f"No supported models configured on server for {provider}"

    return filtered, "OK"


def intersect_preserving_order(values: list[str], allowed: list[str]) -> list[str]:
    allowed_set = set(allowed)
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in allowed_set and value not in seen:
            seen.add(value)
            result.append(value)
    return result
