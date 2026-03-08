'''
Utility functions shared across ALL/some provider implementations. For utils specific to
one single provider, put them in that provider's module (e.g. client.providers.openai.utils).
'''
from typing import TypedDict

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