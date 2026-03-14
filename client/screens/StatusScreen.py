from __future__ import annotations

import asyncio
import json
import os

import aiohttp
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Static,
    TextArea,
)
from textual import work

from client import app
from client.providers.github_copilot.provider import github_copilot_provider
from client.models.models import (
    ExchangeConfig,
    PairingInfo,
    UsageData,
)
from client.logging_config import get_logger
from client.screens import AuthChoiceScreen
from client.screens.ProviderScreen import ProviderScreen

logger = get_logger()


def _make_snippet(provider: str, model: str, peer_url: str, temp_key: str) -> str:
    if provider == "openai":
        return f"""\
import requests

resp = requests.post(
    "{peer_url}/v1/chat/completions",
    headers={{"Authorization": "Bearer {temp_key}"}},
    json={{
        "model": "{model}",
        "messages": [{{"role": "user", "content": "What is the capital of France?"}}],
    }},
)
print(resp.json()["choices"][0]["message"]["content"])
"""
    elif provider == "anthropic":
        return f"""\
import requests

resp = requests.post(
    "{peer_url}/v1/messages",
    headers={{"x-api-key": "{temp_key}", "content-type": "application/json"}},
    json={{
        "model": "{model}",
        "max_tokens": 256,
        "messages": [{{"role": "user", "content": "What is the capital of France?"}}],
    }},
)
print(resp.json()["content"][0]["text"])
"""
    elif provider == "gemini":
        return f"""\
import requests

resp = requests.post(
    "{peer_url}/v1beta/models/{model}:generateContent",
    headers={{"x-goog-api-key": "{temp_key}"}},
    json={{
        "contents": [{{"parts": [{{"text": "What is the capital of France?"}}]}}],
    }},
)
print(resp.json()["candidates"][0]["content"]["parts"][0]["text"])
"""
    elif provider == "github-copilot":
        return f"""\
import requests

resp = requests.post(
    "{peer_url}/chat/completions",
    headers={{"Authorization": "Bearer {temp_key}"}},
    json={{
        "model": "{model}",
        "messages": [{{"role": "user", "content": "What is the capital of France?"}}],
    }},
)
print(resp.json()["choices"][0]["message"]["content"])
"""
    return "# Unknown provider"


class StatusScreen(Screen[None]):
    BINDINGS = [("q", "app.quit", "Quit")]

    status_text: reactive[str] = reactive("Connecting...")
    tokens_served: reactive[int] = reactive(0)
    tokens_used: reactive[int] = reactive(0)
    input_tokens_served: reactive[int] = reactive(0)
    output_tokens_served: reactive[int] = reactive(0)
    input_tokens_used: reactive[int] = reactive(0)
    output_tokens_used: reactive[int] = reactive(0)
    tokens_serve_limit: reactive[int] = reactive(0)
    tokens_use_limit: reactive[int] = reactive(0)

    def __init__(self, config: ExchangeConfig) -> None:
        super().__init__()
        self.config = config
        self._pairing: PairingInfo | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._pairing_transition_in_progress = False
        self._return_to_provider_selection = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="status-layout"):
            with Vertical(id="left-pane"):
                yield Static("TokenHub - Active", classes="title")
                yield Static(self.status_text, id="status", classes="status-text")
                yield DataTable(id="info-table")
                with Horizontal(id="copy-buttons"):
                    yield Button("Copy Peer URL", id="copy-url-btn", variant="primary")
                    yield Button("Copy Temp Key", id="copy-key-btn", variant="primary")
            with Vertical(id="right-pane"):
                yield Static("Quick Start", classes="title")
                yield TextArea(
                    "# Waiting for pairing...",
                    language="python",
                    theme="monokai",
                    read_only=True,
                    show_line_numbers=False,
                    id="code-snippet",
                )
                yield Button("Copy Code", id="copy-code-btn", variant="success")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#info-table", DataTable)
        table.add_columns("Metric", "Value")
        table.add_rows(
            [
                ("Offering", f"{self.config.provider}/{self.config.model}"),
                ("Tokens offered", str(self.config.tokens_offered)),
                ("Wanting", f"{self.config.want_provider}/{self.config.want_model}"),
                ("Served / Limit", "0 / -"),
                ("Used / Limit", "0 / -"),
                ("Peer", "-"),
                ("Peer URL", "-"),
                ("Temp Key", "-"),
            ]
        )
        self.query_one("#copy-buttons", Horizontal).display = False
        self.query_one("#right-pane", Vertical).display = False
        self.connect_and_run()

    def _update_table(self) -> None:
        table = self.query_one("#info-table", DataTable)
        table.clear()
        peer_url = self._pairing.peer_url if self._pairing else "-"
        temp_key = self._pairing.temp_key if self._pairing else "-"
        pair_served = self.tokens_served
        pair_used = self.tokens_used
        pair_input_served = self.input_tokens_served
        pair_output_served = self.output_tokens_served
        pair_input_used = self.input_tokens_used
        pair_output_used = self.output_tokens_used
        rows: list[tuple[str, str]] = [
            ("Offering", f"{self.config.provider}/{self.config.model}"),
            ("Tokens offered", str(self.config.tokens_offered)),
            ("Wanting", f"{self.config.want_provider}/{self.config.want_model}"),
        ]
        if self._pairing and self._pairing.advanced:
            rows.extend(
                [
                    (
                        "Input Served / Limit",
                        f"{pair_input_served} / {self._pairing.input_tokens_to_serve or '-'}",
                    ),
                    (
                        "Output Served / Limit",
                        f"{pair_output_served} / {self._pairing.output_tokens_to_serve or '-'}",
                    ),
                    (
                        "Input Used / Limit",
                        f"{pair_input_used} / {self._pairing.input_tokens_granted or '-'}",
                    ),
                    (
                        "Output Used / Limit",
                        f"{pair_output_used} / {self._pairing.output_tokens_granted or '-'}",
                    ),
                ]
            )
        else:
            rows.extend(
                [
                    (
                        "Served / Limit",
                        f"{pair_served} / {self.tokens_serve_limit or '-'}",
                    ),
                    (
                        "Used / Limit",
                        f"{pair_used} / {self.tokens_use_limit or '-'}",
                    ),
                ]
            )
        rows.extend(
            [
                (
                    "Peer",
                    (
                        f"{self._pairing.peer_provider}/{self._pairing.peer_model}"
                        if self._pairing
                        else "-"
                    ),
                ),
                ("Peer URL", peer_url),
                ("Temp Key", temp_key),
            ]
        )
        table.add_rows(rows)
        if self._pairing:
            self.query_one("#copy-buttons", Horizontal).display = True
            self.query_one("#right-pane", Vertical).display = True
            snippet = _make_snippet(
                self._pairing.peer_provider,
                self._pairing.peer_model,
                self._pairing.peer_url,
                self._pairing.temp_key,
            )
            code_area = self.query_one("#code-snippet", TextArea)
            code_area.load_text(snippet)

    def watch_status_text(self) -> None:
        try:
            self.query_one("#status", Static).update(self.status_text)
        except Exception:
            pass

    def watch_tokens_served(self) -> None:
        self._update_table()

    def watch_tokens_used(self) -> None:
        self._update_table()

    def watch_input_tokens_served(self) -> None:
        self._update_table()

    def watch_output_tokens_served(self) -> None:
        self._update_table()

    def watch_input_tokens_used(self) -> None:
        self._update_table()

    def watch_output_tokens_used(self) -> None:
        self._update_table()

    async def on_proxy_tokens_served(self, input_count: int, output_count: int) -> None:
        if not self._pairing:
            return
        self._pairing.update_usage(
            UsageData(
                tokens_granted_upd=0,
                tokens_to_serve_upd=input_count + output_count,
                input_tokens_granted_upd=0,
                output_tokens_granted_upd=0,
                input_tokens_to_serve_upd=input_count,
                output_tokens_to_serve_upd=output_count,
            )
        )
        # Assign reactive fields to trigger watchers
        self.tokens_served = self._pairing.tokens_to_serve_done
        self.input_tokens_served = self._pairing.input_tokens_to_serve_done
        self.output_tokens_served = self._pairing.output_tokens_to_serve_done
        if self._pairing and self._ws:
            try:
                await self._ws.send_json(
                    {
                        "type": "usage_report",
                        "offer_id": self._pairing.offer_id,
                        "tokens": input_count + output_count,
                        "input_tokens": input_count,
                        "output_tokens": output_count,
                    }
                )
            except Exception:
                pass

        if self._pairing and self._pairing.is_fulfilled():
            await self._end_current_pairing("Pairing done as all tokens exchanged")

    def _build_register_message_with_remaining_offer(self) -> dict[str, str | int]:
        if not self._pairing:
            # first connect
            return self.config.register_message()
        offer_dict = self._pairing.remaining_offer()
        message: dict[str, str | int] = {
            "type": "register",
            "provider": self.config.provider,
            "model": self.config.model,
            "tokens_offered": offer_dict.get("tokens_to_serve_rem", 0),
            "want_provider": self.config.want_provider,
            "want_model": self.config.want_model,
            "proxy_url": self.config.proxy_url,
        }
        if self.config.advanced:
            message["input_tokens_offered"] = offer_dict.get(
                "input_tokens_to_serve_rem", 0
            )
            message["output_tokens_offered"] = offer_dict.get(
                "output_tokens_to_serve_rem", 0
            )
        return message

    async def _end_current_pairing(self, reason: str) -> None:
        """
        Handles cleanup and state reset when a pairing ends, whether due to limits being reached or peer disconnection.
        """
        if self._pairing_transition_in_progress:
            return
        if not self._pairing:
            return

        self._pairing_transition_in_progress = True
        self.tokens_serve_limit = 0
        self.tokens_use_limit = 0
        self.tokens_served = 0
        self.tokens_used = 0
        self.input_tokens_served = 0
        self.output_tokens_served = 0
        self.input_tokens_used = 0
        self.output_tokens_used = 0
        self._update_table()

        offer_dict = self._pairing.remaining_offer()
        logger.debug(f"Ending pairing due to {reason}. Remaining offer: {offer_dict}")
        self._pairing = None

        try:
            if offer_dict.get("tokens_to_serve_rem", 0) <= 0:
                self._return_to_provider_selection = True
                self.status_text = (
                    "[yellow]All tokens served. Returning to provider selection...[/]"
                )
                if self._ws:
                    await self._ws.close()
                return

            detail = (
                "pairing completed"
                if reason == "local_limits_reached"
                else "peer disconnected"
            )
            self.status_text = f"[yellow]{detail}; re-entering pairing mode with {offer_dict.get('tokens_to_serve_rem', 0)} tokens remaining...[/]"

            if self._ws:
                await self._ws.send_json(
                    self._build_register_message_with_remaining_offer()
                )
                self.status_text = "Registered. Waiting for match..."
        finally:
            self._pairing_transition_in_progress = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if not self._pairing:
            return
        if event.button.id == "copy-url-btn":
            self.app.copy_to_clipboard(self._pairing.peer_url)
            self.notify("Peer URL copied!")
        elif event.button.id == "copy-key-btn":
            self.app.copy_to_clipboard(self._pairing.temp_key)
            self.notify("Temp key copied!")
        elif event.button.id == "copy-code-btn":
            snippet = _make_snippet(
                self._pairing.peer_provider,
                self._pairing.peer_model,
                self._pairing.peer_url,
                self._pairing.temp_key,
            )
            self.app.copy_to_clipboard(snippet)
            self.notify("Code copied!")

    @work(exclusive=True)
    async def connect_and_run(self) -> None:
        from client.proxy import ProxyServer

        server_url = os.environ.get("TOKENHUB_SERVER", "ws://localhost:8080") + "/ws"

        proxy = ProxyServer(
            provider=self.config.provider,
            model=self.config.model,
            api_key=self.config.api_key,
            temp_key="",
            token_budget=0,
            input_budget=0,
            output_budget=0,
            on_tokens_served=self.on_proxy_tokens_served,
        )

        refresh_task: asyncio.Task[None] | None = None

        try:
            self.status_text = "Starting proxy and ngrok tunnel..."
            tunnel_url = await proxy.start("127.0.0.1", self.config.proxy_port)
            self.config.proxy_url = tunnel_url

            if self.config.auth_method == "copilot":
                refresh_task = asyncio.create_task(self._refresh_copilot_loop(proxy))

            async with aiohttp.ClientSession() as session:
                while True:
                    self.status_text = "Connecting to server..."
                    reconnect_for_pairing = False

                    async with session.ws_connect(server_url) as ws:
                        self._ws = ws
                        await ws.send_json(
                            self._build_register_message_with_remaining_offer()
                        )

                        async for msg in ws:
                            logger.debug(
                                f"Received message: {msg.type} - {msg.data if msg.type == aiohttp.WSMsgType.TEXT else ''}"
                            )
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)
                                msg_type = str(data.get("type", ""))

                                if msg_type == "ack":
                                    self.status_text = (
                                        "Registered. Waiting for match..."
                                    )

                                elif msg_type == "paired":
                                    self._pairing = PairingInfo(data)
                                    self.tokens_serve_limit = (
                                        self._pairing.tokens_to_serve
                                        or (
                                            self._pairing.input_tokens_to_serve
                                            + self._pairing.output_tokens_to_serve
                                        )
                                    )
                                    self.tokens_use_limit = (
                                        self._pairing.tokens_granted
                                        or (
                                            self._pairing.input_tokens_granted
                                            + self._pairing.output_tokens_granted
                                        )
                                    )
                                    self.tokens_served = 0
                                    self.tokens_used = 0
                                    self.input_tokens_served = 0
                                    self.output_tokens_served = 0
                                    self.input_tokens_used = 0
                                    self.output_tokens_used = 0

                                    proxy._temp_key = self._pairing.proxy_key
                                    proxy._total_budget = self.tokens_serve_limit
                                    proxy._input_budget = (
                                        self._pairing.input_tokens_to_serve
                                    )
                                    proxy._output_budget = (
                                        self._pairing.output_tokens_to_serve
                                    )
                                    proxy._advanced = self._pairing.advanced

                                    self.status_text = (
                                        f"[green]Paired! Proxy: {tunnel_url}[/]"
                                    )
                                    self._update_table()

                                elif msg_type == "error":
                                    message = str(data.get("message", "Unknown error"))
                                    self.status_text = f"[red]Error: {message}[/]"
                                    lowered = message.lower()
                                    if self._pairing and (
                                        "disconnect" in lowered
                                        or "peer" in lowered
                                        or "terminated" in lowered
                                    ):
                                        await self._end_current_pairing(
                                            "peer_disconnected"
                                        )
                                        reconnect_for_pairing = (
                                            not self._return_to_provider_selection
                                        )

                                elif msg_type == "usage_report":
                                    if not self._pairing:
                                        continue
                                    logger.debug(f"Updating usage with report: {data}")
                                    self._pairing.update_usage(
                                        UsageData(
                                            tokens_granted_upd=int(
                                                data.get("tokens", 0)
                                            ),
                                            input_tokens_granted_upd=int(
                                                data.get("input_tokens", 0)
                                            ),
                                            output_tokens_granted_upd=int(
                                                data.get("output_tokens", 0)
                                            ),
                                            tokens_to_serve_upd=0,
                                            input_tokens_to_serve_upd=0,
                                            output_tokens_to_serve_upd=0,
                                        )
                                    )
                                    self.tokens_used = self._pairing.tokens_granted_done
                                    self.input_tokens_used = (
                                        self._pairing.input_tokens_granted_done
                                    )
                                    self.output_tokens_used = (
                                        self._pairing.output_tokens_granted_done
                                    )
                                    if self._pairing and self._pairing.is_fulfilled():
                                        await self._end_current_pairing(
                                            "local_limits_reached"
                                        )

                                elif msg_type == "unpaired":
                                    await self._end_current_pairing("peer_disconnected")
                                    reconnect_for_pairing = (
                                        not self._return_to_provider_selection
                                    )

                            elif msg.type in (
                                aiohttp.WSMsgType.CLOSE,
                                aiohttp.WSMsgType.CLOSING,
                                aiohttp.WSMsgType.ERROR,
                            ):
                                break

                            if self._return_to_provider_selection:
                                break

                        self._ws = None

                        if self._return_to_provider_selection:
                            break

                        if self._pairing is not None:
                            await self._end_current_pairing("peer_disconnected")
                            reconnect_for_pairing = True

                    if self._return_to_provider_selection:
                        break

                    if not reconnect_for_pairing:
                        break

                    self.status_text = "Reconnecting and waiting for a new match..."
                    await asyncio.sleep(0.4)

            self.status_text = "Disconnected"
            self._ws = None
        except Exception as e:
            self.status_text = f"[red]Connection failed: {e}[/]"
        finally:
            if refresh_task:
                refresh_task.cancel()
            await proxy.stop()
            if self._return_to_provider_selection:
                app = self.app
                # Reset ALL state for a clean slate
                app._provider = ""
                app._model = ""
                app._want_provider = ""
                app._want_model = ""
                app._tokens = 0
                # Go back to auth choice (start fresh)
                app.push_screen(AuthChoiceScreen(), callback=app.on_auth_choice)

    async def _refresh_copilot_loop(self, proxy: object) -> None:
        from client.proxy import ProxyServer

        if not isinstance(proxy, ProxyServer):
            return
        while True:
            await asyncio.sleep(25 * 60)
            if not self.config.github_token:
                break
            try:
                copilot = await github_copilot_provider.refresh_copilot_token(
                    self.config.github_token
                )
                proxy._api_key = copilot.copilot_token
                self.config.api_key = copilot.copilot_token
            except Exception:
                pass
