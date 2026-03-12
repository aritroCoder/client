from __future__ import annotations


from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Select,
    Static,
)
from textual import work

from client.api import fetch_provider_models, fetch_public_provider_models
from client.models.models import (
    PROVIDERS,
)
from client.logging_config import get_logger

logger = get_logger(__name__)

class ProviderScreen(Screen[tuple[str, str, str]]):
    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            yield Static("TokenHub", classes="title")
            yield Static("Select Provider")
            yield Select(
                [(p.capitalize(), p) for p in PROVIDERS],
                prompt="Choose provider",
                id="provider-select",
            )
            yield Static("API key (optional, for live model list)")
            yield Input(
                placeholder="Paste API key", password=True, id="provider-key-input"
            )
            yield Button("Fetch Latest Models", id="fetch-models-btn")
            yield Static("", id="provider-model-status", classes="status-text")
            yield Static("Select Model")
            yield Select([], prompt="Choose model", id="model-select")
            yield Button("Next", id="next-btn", variant="primary")
        yield Footer()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "provider-select" and event.value != Select.BLANK:
            provider = str(event.value)
            model_select = self.query_one("#model-select", Select)
            model_select.set_options(
                [("Loading supported models...", "__provider_models_loading__")]
            )
            model_select.clear()
            self.query_one("#provider-model-status", Static).update(
                "Loading server-supported models..."
            )
            self._load_supported_provider_models(provider)

    @work(exclusive=True)
    async def _load_supported_provider_models(self, provider: str) -> None:
        provider_select = self.query_one("#provider-select", Select)
        model_select = self.query_one("#model-select", Select)
        status = self.query_one("#provider-model-status", Static)

        models, message = await fetch_public_provider_models(provider)

        current_provider = provider_select.value
        if current_provider == Select.BLANK or str(current_provider) != provider:
            return

        if not models:
            model_select.set_options([])
            model_select.clear()
            status.update(message)
            self.notify(
                f"Could not load server-supported models for {provider}: {message}",
                severity="error",
            )
            return

        model_select.set_options([(m, m) for m in models])
        model_select.clear()
        status.update(f"Loaded {len(models)} server-supported models")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "fetch-models-btn":
            self.fetch_latest_models()
            return

        provider = self.query_one("#provider-select", Select).value
        model = self.query_one("#model-select", Select).value
        if provider == Select.BLANK or model == Select.BLANK:
            self.notify("Select both provider and model", severity="error")
            return
        if model == "__provider_models_loading__":
            self.notify("Provider models are still loading", severity="error")
            return
        provider_key = self.query_one("#provider-key-input", Input).value.strip()
        self.dismiss((str(provider), str(model), provider_key))

    @work(exclusive=True)
    async def fetch_latest_models(self) -> None:
        provider = self.query_one("#provider-select", Select).value
        key = self.query_one("#provider-key-input", Input).value.strip()
        status = self.query_one("#provider-model-status", Static)
        model_select = self.query_one("#model-select", Select)
        fetch_btn = self.query_one("#fetch-models-btn", Button)

        if provider == Select.BLANK:
            self.notify("Choose a provider first", severity="error")
            return
        if not key:
            self.notify("Enter API key to fetch live models", severity="error")
            return

        provider_name = str(provider)
        fetch_btn.disabled = True
        status.update("Fetching latest models...")
        try:
            models, message = await fetch_provider_models(provider_name, key)
        finally:
            fetch_btn.disabled = False

        if models:
            model_select.set_options([(m, m) for m in models])
            model_select.clear()
            status.update(f"Loaded {len(models)} live models")
            return

        fallback, fallback_status = await fetch_public_provider_models(provider_name)
        if fallback:
            model_select.set_options([(m, m) for m in fallback])
            model_select.clear()
            status.update(
                f"{message}. Using server-supported model list ({len(fallback)} models)."
            )
            return

        model_select.set_options([])
        model_select.clear()
        status.update(
            f"{message}. Could not load server-supported model list ({fallback_status})."
        )