from __future__ import annotations

from client.providers.github_copilot.provider import (
    CopilotToken,
    DeviceCode,
    github_copilot_provider,
)


async def request_device_code() -> DeviceCode:
    return await github_copilot_provider.request_device_code()


async def poll_for_access_token(
    device_code: str,
    interval: int = 5,
    expires_in: int = 900,
) -> str:
    return await github_copilot_provider.poll_for_access_token(
        device_code,
        interval=interval,
        expires_in=expires_in,
    )


async def exchange_for_copilot_token(github_token: str) -> CopilotToken:
    return await github_copilot_provider.exchange_for_copilot_token(github_token)


async def refresh_copilot_token(github_token: str) -> CopilotToken:
    return await github_copilot_provider.refresh_copilot_token(github_token)


async def fetch_copilot_models(copilot_token: str) -> list[str]:
    return await github_copilot_provider.fetch_copilot_models(copilot_token)


async def fetch_public_copilot_models() -> list[str]:
    return await github_copilot_provider.fetch_public_copilot_models()
