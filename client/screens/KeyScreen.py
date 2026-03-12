from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Static,
)
from textual import work

from client.api import validate_key

class KeyScreen(Screen[str]):
    def __init__(self, provider: str, initial_key: str = "") -> None:
        super().__init__()
        self.provider = provider
        self.initial_key = initial_key

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            yield Static(f"Enter {self.provider.capitalize()} API Key", classes="title")
            yield Input(
                placeholder="API key",
                password=True,
                id="key-input",
                value=self.initial_key,
            )
            yield Button("Validate & Connect", id="validate-btn", variant="primary")
            yield Static("", id="key-status", classes="status-text")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        key = self.query_one("#key-input", Input).value
        if not key.strip():
            self.notify("Enter an API key", severity="error")
            return
        self.query_one("#key-status", Static).update("Validating...")
        self.query_one("#validate-btn", Button).disabled = True
        self.do_validate(key.strip())

    @work(exclusive=True)
    async def do_validate(self, key: str) -> None:
        valid, message = await validate_key(self.provider, key)
        status = self.query_one("#key-status", Static)
        btn = self.query_one("#validate-btn", Button)
        if valid:
            status.update("[green]Key valid![/]")
            await asyncio.sleep(0.5)
            self.dismiss(key)
        else:
            status.update(f"[red]{message}[/]")
            btn.disabled = False
