import httpx

from client.providers.gemini.utils import extract_gemini_models_from_payload
from client.providers.utils import (
    ProviderCfg,
    build_auth_headers,
    fetch_server_supported_models,
    intersect_preserving_order,
)


class GeminiProvider:
    def __init__(self) -> None:
        self.provider = "gemini"
        self.PROVIDER_CONFIG: ProviderCfg = {
            "base_url": "https://generativelanguage.googleapis.com",
            "auth_header": "x-goog-api-key",
            "auth_prefix": "",
            "extra_headers": {},
        }

    async def fetch_public_provider_models(self) -> tuple[list[str], str]:
        return await fetch_server_supported_models(self.provider)

    async def validate_key(self, api_key: str) -> tuple[bool, str]:
        config = self.PROVIDER_CONFIG
        headers = build_auth_headers(config, api_key)

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    f"{config['base_url']}/v1beta/models",
                    headers=headers,
                )
                if resp.status_code == 200:
                    return True, "OK"
                return False, f"Validation failed (HTTP {resp.status_code})"
            except httpx.RequestError as e:
                return False, f"Network error: {e}"

    async def fetch_provider_models(self, api_key: str) -> tuple[list[str], str]:
        config = self.PROVIDER_CONFIG
        headers = build_auth_headers(config, api_key)

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(
                    f"{config['base_url']}/v1beta/models",
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

        models = extract_gemini_models_from_payload(payload)
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
