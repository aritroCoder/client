import httpx

from client.providers.anthropic.utils import extract_public_anthropic_models
from client.providers.utils import ProviderCfg, build_auth_headers


class AnthropicProvider:
    def __init__(self) -> None:
        self.provider = "anthropic"
        self.PROVIDER_CONFIG: ProviderCfg = {
            "base_url": "https://api.anthropic.com",
            "auth_header": "x-api-key",
            "auth_prefix": "",
            "extra_headers": {"anthropic-version": "2023-06-01"},
        }
        self.PUBLIC_MODELS_URL = (
            "https://docs.anthropic.com/en/docs/about-claude/models/all-models"
        )
        self.PUBLIC_MODEL_PATTERN = (
            r"\bclaude-(?:opus|sonnet|haiku)-[0-9][a-z0-9.\-]*\b"
        )

    async def fetch_public_provider_models(self) -> tuple[list[str], str]:
        if not self.PUBLIC_MODELS_URL:
            return [], "Public model fetch is only available for known providers"

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            try:
                resp = await client.get(
                    self.PUBLIC_MODELS_URL,
                    headers={
                        "Accept": "text/html",
                        "User-Agent": "Mozilla/5.0 (TokenHub)",
                    },
                )
            except httpx.RequestError as e:
                return [], f"Network error: {e}"

        if resp.status_code != 200:
            return [], f"Public model fetch failed (HTTP {resp.status_code})"

        models = extract_public_anthropic_models(resp.text, self.PUBLIC_MODEL_PATTERN)
        if not models:
            return [], "No public models found"
        return models, "OK"

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

        return models, "OK"
