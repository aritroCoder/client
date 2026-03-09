from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from urllib.parse import urlencode

import httpx
from aiohttp import web
from pyngrok import ngrok

from client.api import PROVIDER_CONFIG


class ProxyServer:
    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str,
        temp_key: str,
        token_budget: int,
        input_budget: int = 0,
        output_budget: int = 0,
        on_tokens_served: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> None:
        self._provider = provider
        self._model = model
        self._api_key = api_key
        self._temp_key = temp_key
        self._input_budget = input_budget
        self._output_budget = output_budget
        self._total_budget = token_budget
        self._input_served = 0
        self._output_served = 0
        self._total_served = 0
        self._advanced = input_budget > 0 or output_budget > 0
        self._on_tokens_served = on_tokens_served
        self._runner: web.AppRunner | None = None
        self._tunnel_url: str | None = None

    _HOP_BY_HOP_HEADERS = {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",
        "content-length",
    }

    _INCOMING_AUTH_HEADERS = {
        "authorization",
        "x-api-key",
        "x-goog-api-key",
    }

    def _verify_auth(self, request: web.Request) -> bool:
        if self._provider == "openai":
            auth = request.headers.get("Authorization", "")
            return auth.removeprefix("Bearer ") == self._temp_key
        elif self._provider == "anthropic":
            return request.headers.get("x-api-key", "") == self._temp_key
        elif self._provider == "gemini":
            return request.headers.get("x-goog-api-key", "") == self._temp_key
        elif self._provider == "github-copilot":
            auth = request.headers.get("Authorization", "")
            return auth.removeprefix("Bearer ") == self._temp_key
        return False

    def _budget_exceeded(self) -> bool:
        if self._advanced:
            return (
                self._input_served >= self._input_budget
                and self._output_served >= self._output_budget
            )
        return self._total_served >= self._total_budget

    def _verify_model(self, body: bytes) -> bool:
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            return True
        model = data.get("model", self._model)
        return model == self._model

    def _cap_output_tokens(self, body: bytes) -> bytes:
        if self._advanced:
            remaining = self._output_budget - self._output_served
        else:
            remaining = self._total_budget - self._total_served
        if remaining < 0:
            remaining = 0
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            return body

        if self._provider == "openai":
            user_max = data.get("max_completion_tokens") or data.get("max_tokens")
            cap = min(user_max, remaining) if user_max else remaining
            data.pop("max_tokens", None)
            data["max_completion_tokens"] = cap
        elif self._provider == "anthropic":
            user_max = data.get("max_tokens")
            data["max_tokens"] = min(user_max, remaining) if user_max else remaining
        elif self._provider == "gemini":
            gen_config = data.setdefault("generationConfig", {})
            user_max = gen_config.get("maxOutputTokens")
            gen_config["maxOutputTokens"] = (
                min(user_max, remaining) if user_max else remaining
            )
        elif self._provider == "github-copilot":
            user_max = data.get("max_completion_tokens") or data.get("max_tokens")
            cap = min(user_max, remaining) if user_max else remaining
            data.pop("max_tokens", None)
            data["max_completion_tokens"] = cap

        return json.dumps(data).encode()

    @staticmethod
    def _with_query_params(url: str, request: web.Request) -> str:
        if not request.query:
            return url
        query = urlencode(list(request.query.items()), doseq=True)
        if not query:
            return url
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}{query}"

    def _build_upstream_headers(
        self,
        request: web.Request,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        headers: dict[str, str] = {}

        for key, value in request.headers.items():
            lower = key.lower()
            if (
                lower in self._HOP_BY_HOP_HEADERS
                or lower in self._INCOMING_AUTH_HEADERS
            ):
                continue
            headers[key] = value

        config = PROVIDER_CONFIG[self._provider]
        auth_header = str(config["auth_header"])
        auth_prefix = str(config["auth_prefix"])
        headers[auth_header] = auth_prefix + self._api_key

        provider_headers = config["extra_headers"]
        if isinstance(provider_headers, dict):
            for key, value in provider_headers.items():
                if isinstance(key, str) and isinstance(value, str):
                    headers[key] = value

        if extra_headers:
            headers.update(extra_headers)

        if "Content-Type" not in headers and "content-type" not in {
            key.lower() for key in headers
        }:
            headers["Content-Type"] = "application/json"

        return headers

    @staticmethod
    def _response_headers(resp: httpx.Response) -> dict[str, str]:
        headers: dict[str, str] = {}
        for key, value in resp.headers.items():
            lower = key.lower()
            if lower in ProxyServer._HOP_BY_HOP_HEADERS:
                continue
            headers[key] = value
        return headers

    async def _record_usage(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        input_count, output_count = self._extract_tokens(payload, self._provider)
        if input_count <= 0 and output_count <= 0:
            return

        if self._advanced:
            self._input_served += input_count
            self._output_served += output_count
        else:
            self._total_served += input_count + output_count

        if self._on_tokens_served:
            await self._on_tokens_served(input_count, output_count)

    async def _stream_response(
        self,
        request: web.Request,
        url: str,
        body: bytes,
        headers: dict[str, str],
    ) -> web.StreamResponse:
        usage_input_total = 0
        usage_output_total = 0
        usage_buffer = bytearray()

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST", url, content=body, headers=headers
            ) as resp:
                response_headers = self._response_headers(resp)
                content_type = response_headers.get("Content-Type", "")
                if content_type.startswith("text/event-stream"):
                    response_headers.setdefault("Cache-Control", "no-cache")
                    response_headers.setdefault("Connection", "keep-alive")
                    response_headers.setdefault("X-Accel-Buffering", "no")

                stream_resp = web.StreamResponse(
                    status=resp.status_code,
                    headers=response_headers,
                )
                await stream_resp.prepare(request)

                async for chunk in resp.aiter_bytes():
                    await stream_resp.write(chunk)
                    usage_buffer.extend(chunk)

                    while b"\n\n" in usage_buffer:
                        raw_event, _, remaining = usage_buffer.partition(b"\n\n")
                        usage_buffer = bytearray(remaining)
                        for line in raw_event.splitlines():
                            line = line.strip()
                            if not line.startswith(b"data:"):
                                continue
                            payload = line[len(b"data:") :].strip()
                            if payload == b"[DONE]":
                                continue
                            try:
                                event_json = json.loads(payload.decode("utf-8"))
                            except (
                                UnicodeDecodeError,
                                json.JSONDecodeError,
                                ValueError,
                            ):
                                continue
                            in_count, out_count = self._extract_tokens(
                                event_json, self._provider
                            )
                            usage_input_total += in_count
                            usage_output_total += out_count

                await stream_resp.write_eof()

        if usage_input_total > 0 or usage_output_total > 0:
            await self._record_usage(
                {
                    "usage": {
                        "prompt_tokens": usage_input_total,
                        "completion_tokens": usage_output_total,
                        "input_tokens": usage_input_total,
                        "output_tokens": usage_output_total,
                    },
                    "usageMetadata": {
                        "promptTokenCount": usage_input_total,
                        "candidatesTokenCount": usage_output_total,
                    },
                }
            )

        return stream_resp

    async def _forward_and_track(
        self,
        request: web.Request,
        url: str,
        extra_headers: dict[str, str] | None = None,
    ) -> web.StreamResponse:
        if not self._verify_auth(request):
            return web.json_response({"error": "Unauthorized"}, status=401)
        if self._budget_exceeded():
            return web.json_response({"error": "Token budget exhausted"}, status=429)

        body = await request.read()
        if not self._verify_model(body):
            return web.json_response(
                {"error": f"Only model '{self._model}' is available on this proxy"},
                status=400,
            )
        body = self._cap_output_tokens(body)
        upstream_url = self._with_query_params(url, request)
        headers = self._build_upstream_headers(request, extra_headers)

        wants_stream = False
        try:
            body_json = json.loads(body)
            wants_stream = bool(
                isinstance(body_json, dict) and body_json.get("stream") is True
            )
        except (json.JSONDecodeError, ValueError, TypeError):
            wants_stream = False

        if wants_stream:
            stream_response = await self._stream_response(
                request=request,
                url=upstream_url,
                body=body,
                headers=headers,
            )
            return stream_response

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(upstream_url, content=body, headers=headers)

        try:
            resp_data = resp.json()
        except ValueError:
            resp_data = None

        if resp_data is not None:
            await self._record_usage(resp_data)

        return web.Response(
            body=resp.content,
            status=resp.status_code,
            headers=self._response_headers(resp),
        )

    async def _handle_models(self, request: web.Request) -> web.Response:
        if not self._verify_auth(request):
            return web.json_response({"error": "Unauthorized"}, status=401)
        return web.json_response(
            {
                "object": "list",
                "data": [
                    {
                        "id": self._model,
                        "object": "model",
                        "owned_by": "tokenhub",
                    }
                ],
            }
        )

    @staticmethod
    def _extract_tokens(data: dict[str, object], provider: str) -> tuple[int, int]:
        def _to_int(value: object) -> int:
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                return int(value)
            if isinstance(value, str):
                try:
                    return int(value)
                except ValueError:
                    return 0
            return 0

        try:
            if provider == "openai" or provider == "github-copilot":
                usage = data.get("usage", {})
                if not isinstance(usage, dict):
                    return (0, 0)
                return (
                    _to_int(usage.get("prompt_tokens", 0)),
                    _to_int(usage.get("completion_tokens", 0)),
                )
            elif provider == "anthropic":
                usage = data.get("usage", {})
                if not isinstance(usage, dict):
                    return (0, 0)
                return (
                    _to_int(usage.get("input_tokens", 0)),
                    _to_int(usage.get("output_tokens", 0)),
                )
            elif provider == "gemini":
                usage = data.get("usageMetadata", {})
                if not isinstance(usage, dict):
                    return (0, 0)
                return (
                    _to_int(usage.get("promptTokenCount", 0)),
                    _to_int(usage.get("candidatesTokenCount", 0)),
                )
        except (AttributeError, TypeError):
            pass
        return (0, 0)

    async def _handle_openai(self, request: web.Request) -> web.StreamResponse:
        url = f"{PROVIDER_CONFIG['openai']['base_url']}/v1/chat/completions"
        return await self._forward_and_track(request, url)

    async def _handle_anthropic(self, request: web.Request) -> web.StreamResponse:
        url = f"{PROVIDER_CONFIG['anthropic']['base_url']}/v1/messages"
        return await self._forward_and_track(request, url)

    async def _handle_gemini(self, request: web.Request) -> web.StreamResponse:
        model = request.match_info.get("model", self._model)
        if model != self._model:
            return web.json_response(
                {"error": f"Only model '{self._model}' is available on this proxy"},
                status=400,
            )
        url = (
            f"{PROVIDER_CONFIG['gemini']['base_url']}"
            f"/v1beta/models/{self._model}:generateContent"
        )
        return await self._forward_and_track(request, url)

    async def _handle_copilot(self, request: web.Request) -> web.StreamResponse:
        url = f"{PROVIDER_CONFIG['github-copilot']['base_url']}/chat/completions"
        return await self._forward_and_track(request, url)

    def _create_app(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/v1/models", self._handle_models)
        app.router.add_get("/models", self._handle_models)
        if self._provider == "openai":
            app.router.add_post("/v1/chat/completions", self._handle_openai)
            app.router.add_post("/chat/completions", self._handle_openai)
        elif self._provider == "anthropic":
            app.router.add_post("/v1/messages", self._handle_anthropic)
            app.router.add_post("/messages", self._handle_anthropic)
        elif self._provider == "gemini":
            app.router.add_post(
                "/v1beta/models/{model}:generateContent", self._handle_gemini
            )
        elif self._provider == "github-copilot":
            app.router.add_post("/chat/completions", self._handle_copilot)
            app.router.add_post("/v1/chat/completions", self._handle_copilot)
        return app

    async def start(
        self, host: str = "127.0.0.1", port: int = 9100, max_attempts: int = 10
    ) -> str:
        self._runner = web.AppRunner(self._create_app())
        await self._runner.setup()

        for attempt in range(max_attempts):
            try:
                site = web.TCPSite(self._runner, host, port + attempt)
                await site.start()
                break
            except OSError:
                if attempt == max_attempts - 1:
                    raise
        else:
            raise OSError(f"Could not bind to ports {port}-{port + max_attempts - 1}")

        bound_port = port + attempt
        self._tunnel_url = await asyncio.to_thread(self._create_tunnel, bound_port)
        return self._tunnel_url

    @staticmethod
    def _create_tunnel(port: int) -> str:
        auth_token = os.environ.get("NGROK_AUTHTOKEN", "")
        if auth_token:
            ngrok.set_auth_token(auth_token)
        tunnel = ngrok.connect(str(port), "http")
        if tunnel.public_url is None:
            raise RuntimeError("ngrok tunnel did not return a public URL")
        return tunnel.public_url

    async def stop(self) -> None:
        if self._tunnel_url:
            await asyncio.to_thread(self._disconnect_tunnel, self._tunnel_url)
            self._tunnel_url = None
        if self._runner:
            await self._runner.cleanup()

    @staticmethod
    def _disconnect_tunnel(url: str) -> None:
        from pyngrok import ngrok

        try:
            ngrok.disconnect(url)
        except Exception:
            pass
