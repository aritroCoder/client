from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import httpx

from client.providers.github_copilot.utils import extract_public_copilot_models
from client.providers.utils import ProviderCfg, build_auth_headers


@dataclass
class DeviceCode:
    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int


@dataclass
class CopilotToken:
    github_token: str
    copilot_token: str
    expires_at: float


class GitHubCopilotProvider:
    def __init__(self) -> None:
        self.provider = "github-copilot"
        self.PROVIDER_CONFIG: ProviderCfg = {
            "base_url": "https://api.githubcopilot.com",
            "auth_header": "Authorization",
            "auth_prefix": "Bearer ",
            "extra_headers": {
                "Editor-Version": "vscode/1.95.0",
                "Editor-Plugin-Version": "copilot/1.250.0",
                "User-Agent": "GithubCopilot/1.250.0",
                "Copilot-Integration-Id": "vscode-chat",
                "Openai-Organization": "github-copilot",
            },
        }
        self.github_client_id = "Iv1.b507a08c87ecfe98"
        self.github_device_code_url = "https://github.com/login/device/code"
        self.github_access_token_url = "https://github.com/login/oauth/access_token"
        self.github_copilot_token_url = (
            "https://api.github.com/copilot_internal/v2/token"
        )
        self.public_models_url = (
            "https://docs.github.com/en/copilot/reference/ai-models/supported-models"
        )
        self.user_agent = "GithubCopilot/1.250.0"
        self.editor_version = "vscode/1.95.0"
        self.editor_plugin_version = "copilot/1.250.0"

    async def request_device_code(self) -> DeviceCode:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                self.github_device_code_url,
                data={
                    "client_id": self.github_client_id,
                    "scope": "read:user",
                },
                headers={
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return DeviceCode(
                device_code=data["device_code"],
                user_code=data["user_code"],
                verification_uri=data["verification_uri"],
                expires_in=data["expires_in"],
                interval=data.get("interval", 5),
            )

    async def poll_for_access_token(
        self,
        device_code: str,
        interval: int = 5,
        expires_in: int = 900,
    ) -> str:
        deadline = time.monotonic() + expires_in
        poll_interval = interval

        async with httpx.AsyncClient(timeout=10.0) as client:
            while time.monotonic() < deadline:
                await asyncio.sleep(poll_interval)

                resp = await client.post(
                    self.github_access_token_url,
                    data={
                        "client_id": self.github_client_id,
                        "device_code": device_code,
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    },
                    headers={
                        "Accept": "application/json",
                    },
                )
                data = resp.json()

                if "access_token" in data and data["access_token"]:
                    return data["access_token"]

                error = data.get("error", "")
                if error == "authorization_pending":
                    continue
                if error == "slow_down":
                    poll_interval += 5
                    continue
                if error == "expired_token":
                    raise TimeoutError("Device code expired. Please try again.")
                if error == "access_denied":
                    raise PermissionError("Authorization denied by user.")
                if error:
                    raise RuntimeError(
                        f"OAuth error: {error} - {data.get('error_description', '')}"
                    )

        raise TimeoutError("Device code expired before authorization completed.")

    async def exchange_for_copilot_token(self, github_token: str) -> CopilotToken:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                self.github_copilot_token_url,
                headers={
                    "Authorization": f"token {github_token}",
                    "Accept": "application/json",
                    "User-Agent": self.user_agent,
                    "Editor-Version": self.editor_version,
                    "Editor-Plugin-Version": self.editor_plugin_version,
                },
            )
            if resp.status_code == 401:
                raise PermissionError(
                    "GitHub token invalid or expired. Please re-authenticate."
                )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"Copilot token exchange failed (HTTP {resp.status_code}): {resp.text}"
                )

            data = resp.json()
            token = data.get("token")
            if not token:
                raise RuntimeError("Copilot token response missing 'token' field")

            expires_at = self._parse_token_expiry(token)

            return CopilotToken(
                github_token=github_token,
                copilot_token=token,
                expires_at=expires_at,
            )

    async def refresh_copilot_token(self, github_token: str) -> CopilotToken:
        return await self.exchange_for_copilot_token(github_token)

    async def fetch_copilot_models(self, copilot_token: str) -> list[str]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{self.PROVIDER_CONFIG['base_url']}/models",
                headers={
                    **self.PROVIDER_CONFIG["extra_headers"],
                    "Authorization": f"Bearer {copilot_token}",
                    "Accept": "application/json",
                    "User-Agent": self.user_agent,
                    "Editor-Version": self.editor_version,
                    "Editor-Plugin-Version": self.editor_plugin_version,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            models: list[str] = []
            for model in data.get("data", []):
                capabilities = model.get("capabilities", {})
                if capabilities.get("type") != "chat":
                    continue
                model_id = model.get("id")
                if model_id:
                    models.append(model_id)
            return models

    async def fetch_provider_models(self, api_key: str) -> tuple[list[str], str]:
        try:
            models = await self.fetch_copilot_models(api_key)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in {401, 403}:
                return [], "API key rejected"
            return [], f"Model fetch failed (HTTP {e.response.status_code})"
        except httpx.RequestError as e:
            return [], f"Network error: {e}"

        if not models:
            return [], "No models returned by provider"
        return models, "OK"

    async def fetch_public_provider_models(self) -> tuple[list[str], str]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(
                    self.public_models_url,
                    headers={
                        "Accept": "text/html",
                        "User-Agent": self.user_agent,
                    },
                )
                resp.raise_for_status()
            except httpx.RequestError as e:
                return [], f"Network error: {e}"
            except httpx.HTTPStatusError as e:
                return [], f"Public model fetch failed (HTTP {e.response.status_code})"

        models = extract_public_copilot_models(resp.text)
        if not models:
            return [], "No public models found"
        return models, "OK"

    async def fetch_public_copilot_models(self) -> list[str]:
        models, _ = await self.fetch_public_provider_models()
        return models

    async def validate_key(self, api_key: str) -> tuple[bool, str]:
        config = self.PROVIDER_CONFIG
        headers = build_auth_headers(config, api_key)
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    f"{config['base_url']}/models",
                    headers=headers,
                )
                if resp.status_code == 200:
                    return True, "OK"
                return False, f"Validation failed (HTTP {resp.status_code})"
            except httpx.RequestError as e:
                return False, f"Network error: {e}"

    @staticmethod
    def _parse_token_expiry(token: str) -> float:
        import re

        match = re.search(r"exp=(\d+)", token)
        if match:
            return float(match.group(1))
        return time.time() + 1800


github_copilot_provider = GitHubCopilotProvider()
