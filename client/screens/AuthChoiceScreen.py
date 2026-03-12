from __future__ import annotations


from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Static,
)

class AuthChoiceScreen(Screen[str]):
    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            yield Static("TokenHub", classes="title")
            yield Static("How would you like to authenticate?")
            yield Button(
                "GitHub Copilot",
                id="auth-copilot-btn",
                variant="success",
            )
            yield Button(
                "Use your API Key",
                id="auth-apikey-btn",
                variant="primary",
            )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "auth-apikey-btn":
            self.dismiss("api_key")
        elif event.button.id == "auth-copilot-btn":
            self.dismiss("copilot")

