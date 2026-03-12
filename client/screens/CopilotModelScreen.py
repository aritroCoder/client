from __future__ import annotations


from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Select,
    Static,
)
from textual import work

from client.api import fetch_provider_models, fetch_public_provider_models


class CopilotModelScreen(Screen[str]):
    def __init__(self, copilot_token: str) -> None:
        super().__init__()
        self.copilot_token = copilot_token

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            yield Static("Select Model", classes="title")
            yield Static("Fetching available models...", id="copilot-model-status")
            yield Select([], prompt="Choose model", id="copilot-model-select")
            yield Button("Next", id="next-btn", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#copilot-model-select", Select).display = False
        self.query_one("#next-btn", Button).display = False
        self.load_models()

    @work(exclusive=True)
    async def load_models(self) -> None:
        status = self.query_one("#copilot-model-status", Static)
        model_select = self.query_one("#copilot-model-select", Select)
        next_btn = self.query_one("#next-btn", Button)

        try:
            models, _ = await fetch_provider_models(
                "github-copilot", self.copilot_token
            )
            if not models:
                models, message = await fetch_public_provider_models("github-copilot")
                if not models:
                    status.update(message)
                    return
                status.update("Using server-supported model list")
            else:
                status.update(f"Found {len(models)} models")
        except Exception:
            models, message = await fetch_public_provider_models("github-copilot")
            if not models:
                status.update(f"Could not fetch models: {message}")
                return
            status.update("Could not fetch live models, using server-supported list")

        model_select.set_options([(m, m) for m in models])
        model_select.display = True
        next_btn.display = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        model = self.query_one("#copilot-model-select", Select).value
        if model == Select.BLANK:
            self.notify("Select a model", severity="error")
            return
        self.dismiss(str(model))

