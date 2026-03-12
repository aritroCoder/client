from __future__ import annotations


from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Select,
    Static,
    Switch,
)
from textual import work

from client.api import fetch_provider_models, fetch_public_provider_models
from client.providers.github_copilot.provider import github_copilot_provider
from client.models.models import (
    PROVIDERS,
)

class ExchangeScreen(Screen[tuple[int, str, str, bool, int, int]]):
    def __init__(self, provider: str, model: str) -> None:
        super().__init__()
        self.provider = provider
        self.model = model

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            yield Static(f"Offering: {self.provider}/{self.model}", classes="title")
            yield Static("Tokens to share", id="tokens-label")
            yield Input(placeholder="e.g. 1000", id="tokens-input", type="integer")
            with Horizontal(id="advanced-toggle-row"):
                yield Static("Advanced", id="advanced-label")
                yield Switch(id="advanced-switch")
            yield Static("Input tokens to share", id="input-tokens-label")
            yield Input(
                placeholder="e.g. 700",
                id="input-tokens-input",
                type="integer",
            )
            yield Static("Output tokens to share", id="output-tokens-label")
            yield Input(
                placeholder="e.g. 300",
                id="output-tokens-input",
                type="integer",
            )
            yield Static("Want provider")
            yield Select(
                [(p.capitalize(), p) for p in PROVIDERS],
                prompt="Choose provider",
                id="want-provider-select",
            )
            yield Static("Want model")
            yield Select([], prompt="Choose model", id="want-model-select")
            yield Button("Next", id="next-btn", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        self._set_advanced_mode(False)

    def _set_advanced_mode(self, advanced: bool) -> None:
        self.query_one("#tokens-label", Static).display = not advanced
        self.query_one("#tokens-input", Input).display = not advanced
        self.query_one("#input-tokens-label", Static).display = advanced
        self.query_one("#input-tokens-input", Input).display = advanced
        self.query_one("#output-tokens-label", Static).display = advanced
        self.query_one("#output-tokens-input", Input).display = advanced

    @staticmethod
    def _parse_positive_int(value: str) -> int | None:
        try:
            parsed = int(value)
        except ValueError:
            return None
        if parsed <= 0:
            return None
        return parsed

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "want-provider-select" and event.value != Select.BLANK:
            provider = str(event.value)
            model_select = self.query_one("#want-model-select", Select)

            if provider == "github-copilot":
                model_select.set_options(
                    [("Loading Copilot models...", "__copilot_models_loading__")]
                )
                model_select.clear()
                self._load_copilot_want_models()
                return

            model_select.set_options(
                [("Loading public models...", "__want_models_loading__")]
            )
            model_select.clear()
            self._load_public_want_models(provider)

    @work(exclusive=True)
    async def _load_public_want_models(self, provider: str) -> None:
        provider_select = self.query_one("#want-provider-select", Select)
        model_select = self.query_one("#want-model-select", Select)

        try:
            models, status = await fetch_public_provider_models(provider)
        except Exception:
            models = []
            status = "Public model fetch failed"

        current_provider = provider_select.value
        if current_provider == Select.BLANK or str(current_provider) != provider:
            return

        if not models:
            self.notify(
                f"Could not load server-supported model list for {provider}: {status}",
                severity="error",
            )
            model_select.set_options([])
            model_select.clear()
            return

        self.notify(
            f"Loaded {len(models)} server-supported {provider} models",
            severity="information",
        )

        if provider == self.provider:
            models = [m for m in models if m != self.model]

        model_select.set_options([(m, m) for m in models])
        model_select.clear()

    @work(exclusive=True)
    async def _load_copilot_want_models(self) -> None:
        provider_select = self.query_one("#want-provider-select", Select)
        model_select = self.query_one("#want-model-select", Select)

        try:
            models = await self._fetch_live_copilot_models_for_want()
        except Exception:
            models = []

        current_provider = provider_select.value
        if (
            current_provider == Select.BLANK
            or str(current_provider) != "github-copilot"
        ):
            return

        if models:
            model_select.set_options([(m, m) for m in models])
            model_select.clear()
            self.notify(
                f"Loaded {len(models)} Copilot models",
                severity="information",
            )
            return

        model_select.set_options([])
        model_select.clear()
        self.notify(
            "Could not load supported Copilot models",
            severity="error",
        )

    async def _fetch_live_copilot_models_for_want(self) -> list[str]:
        app = self.app
        copilot_token = getattr(app, "_copilot_token", "")
        github_token = getattr(app, "_github_token", "")

        if copilot_token:
            try:
                models, _ = await fetch_provider_models("github-copilot", copilot_token)
                if models:
                    return models
            except Exception as e:
                self.log(f"Copilot model fetch with cached token failed: {e}")

        if github_token:
            try:
                refreshed = await github_copilot_provider.refresh_copilot_token(
                    github_token
                )
                setattr(app, "_copilot_token", refreshed.copilot_token)
                setattr(app, "_github_token", refreshed.github_token)
                models, _ = await fetch_provider_models(
                    "github-copilot", refreshed.copilot_token
                )
                if models:
                    return models
            except Exception as e:
                self.log(f"Copilot model fetch after refresh failed: {e}")

        public_models = await github_copilot_provider.fetch_public_copilot_models()
        if public_models:
            return public_models

        return []

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id == "advanced-switch":
            self._set_advanced_mode(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        tokens_str = self.query_one("#tokens-input", Input).value
        input_tokens_str = self.query_one("#input-tokens-input", Input).value
        output_tokens_str = self.query_one("#output-tokens-input", Input).value
        advanced = self.query_one("#advanced-switch", Switch).value
        want_provider = self.query_one("#want-provider-select", Select).value
        want_model = self.query_one("#want-model-select", Select).value

        if want_provider == Select.BLANK or want_model == Select.BLANK:
            self.notify("Select wanted provider and model", severity="error")
            return
        if want_model == "__copilot_models_loading__":
            self.notify("Copilot models are still loading", severity="error")
            return
        if want_model == "__want_models_loading__":
            self.notify("Provider models are still loading", severity="error")
            return
        want_provider_str = str(want_provider)
        want_model_str = str(want_model)

        if advanced:
            input_tokens = self._parse_positive_int(input_tokens_str)
            output_tokens = self._parse_positive_int(output_tokens_str)
            if input_tokens is None or output_tokens is None:
                self.notify(
                    "Enter positive input and output token amounts",
                    severity="error",
                )
                return
            self.dismiss(
                (
                    0,
                    want_provider_str,
                    want_model_str,
                    True,
                    input_tokens,
                    output_tokens,
                )
            )
            return

        tokens = self._parse_positive_int(tokens_str)
        if tokens is None:
            self.notify("Enter a positive number of tokens", severity="error")
            return

        self.dismiss((tokens, want_provider_str, want_model_str, False, 0, 0))