import httpx

from client.providers.utils import (
    ProviderCfg,
    build_auth_headers,
    fetch_server_supported_models,
    intersect_preserving_order,
)


class AnthropicProvider:
    def __init__(self) -> None:
        self.provider = "anthropic"
        self.PROVIDER_CONFIG: ProviderCfg = {
            "base_url": "https://api.anthropic.com",
            "auth_header": "x-api-key",
            "auth_prefix": "",
            "extra_headers": {"anthropic-version": "2023-06-01"},
        }

    async def fetch_public_provider_models(self) -> tuple[list[str], str]:
        return await fetch_server_supported_models(self.provider)

    async def validate_key(self, api_key: str) -> tuple[bool, str]:
        config = self.PROVIDER_CONFIG
        headers = build_auth_headers(config, api_key)

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(
                    f"{config['base_url']}/v1/messages",
                    headers={**headers, "Content-Type": "application/json"},
                    json={
                        "model": "claude-sonnet-4-6",
                        "max_tokens": 1,
                        "messages": [],
                    },
                )
                if resp.status_code == 401:
                    return False, "Invalid API key"
                return True, "OK"
            except httpx.RequestError as e:
                return False, f"Network error: {e}"

    async def fetch_provider_models(self, api_key: str) -> tuple[list[str], str]:
        config = self.PROVIDER_CONFIG
        headers = build_auth_headers(config, api_key)

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(
                    f"{config['base_url']}/v1/models",
                    headers=headers,
                )
            except httpx.RequestError as e:
                return [], f"Network error: {e}"

        if resp.status_code in {401, 403}:
            return [], "API key rejected"
        if resp.status_code != 200:
            return [], f"Model fetch failed (HTTP {resp.status_code})"

        try:
            payload = resp.json()
        except ValueError:
            return [], "Model fetch failed (invalid JSON response)"

        models: list[str] = []
        seen: set[str] = set()

        for item in payload.get("data", []):
            model_id = item.get("id")
            if isinstance(model_id, str) and model_id and model_id not in seen:
                seen.add(model_id)
                models.append(model_id)

        if not models:
            return [], "No models returned by provider"

        supported_models, supported_status = await fetch_server_supported_models(
            self.provider
        )
        if not supported_models:
            return [], supported_status

        filtered_models = intersect_preserving_order(models, supported_models)
        if not filtered_models:
            return [], "No provider models supported by server"

        return filtered_models, "OK"
