import httpx
from typing import Protocol

from client.providers.anthropic.provider import AnthropicProvider
from client.providers.gemini.provider import GeminiProvider
from client.providers.github_copilot.provider import github_copilot_provider
from client.providers.openai.provider import OpenAIProvider
from client.providers.utils import ProviderCfg, build_auth_headers

_OPENAI_PROVIDER = OpenAIProvider()
_ANTHROPIC_PROVIDER = AnthropicProvider()
_GEMINI_PROVIDER = GeminiProvider()


class _ApiKeyProvider(Protocol):
    PROVIDER_CONFIG: ProviderCfg

    async def fetch_public_provider_models(self) -> tuple[list[str], str]: ...

    async def validate_key(self, api_key: str) -> tuple[bool, str]: ...

    async def fetch_provider_models(self, api_key: str) -> tuple[list[str], str]: ...


_API_KEY_PROVIDER_IMPLS: dict[str, _ApiKeyProvider] = {
    "openai": _OPENAI_PROVIDER,
    "anthropic": _ANTHROPIC_PROVIDER,
    "gemini": _GEMINI_PROVIDER,
}

PROVIDER_CONFIG: dict[str, ProviderCfg] = {
    "openai": _OPENAI_PROVIDER.PROVIDER_CONFIG,
    "anthropic": _ANTHROPIC_PROVIDER.PROVIDER_CONFIG,
    "gemini": _GEMINI_PROVIDER.PROVIDER_CONFIG,
    "github-copilot": github_copilot_provider.PROVIDER_CONFIG,
}


async def fetch_public_provider_models(provider: str) -> tuple[list[str], str]:
    impl = _API_KEY_PROVIDER_IMPLS.get(provider)
    if impl is None:
        return [], "Public model fetch is only available for known providers"
    return await impl.fetch_public_provider_models()


async def validate_key(provider: str, api_key: str) -> tuple[bool, str]:
    if provider == "github-copilot":
        return await github_copilot_provider.validate_key(api_key)

    impl = _API_KEY_PROVIDER_IMPLS.get(provider)
    if impl is None:
        return False, f"Validation failed (unknown provider: {provider})"
    return await impl.validate_key(api_key)


async def fetch_provider_models(provider: str, api_key: str) -> tuple[list[str], str]:
    impl = _API_KEY_PROVIDER_IMPLS.get(provider)
    if impl is None:
        return [], "Live model fetch is only available for API key providers"
    return await impl.fetch_provider_models(api_key)
