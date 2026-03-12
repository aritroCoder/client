from __future__ import annotations


from textual.app import App

from client.models.models import (
    ExchangeConfig,
)
from client.logging_config import get_logger

from client.screens.ProviderScreen import ProviderScreen
from client.screens.ExchangeScreen import ExchangeScreen
from client.screens.KeyScreen import KeyScreen
from client.screens.AuthChoiceScreen import AuthChoiceScreen
from client.screens.CopilotAuthScreen import CopilotAuthScreen
from client.screens.StatusScreen import StatusScreen
from client.screens.CopilotModelScreen import CopilotModelScreen

logger = get_logger(__name__)

class TokenHubApp(App[None]):
    CSS_PATH = "app.tcss"
    TITLE = "TokenHub"
    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self) -> None:
        super().__init__()
        self._provider: str = ""
        self._model: str = ""
        self._api_key_prefill: str = ""
        self._tokens: int = 0
        self._want_provider: str = ""
        self._want_model: str = ""
        self._advanced: bool = False
        self._input_tokens: int = 0
        self._output_tokens: int = 0
        self._auth_method: str = "api_key"
        self._copilot_token: str = ""
        self._github_token: str = ""

    def on_mount(self) -> None:
        self.push_screen(AuthChoiceScreen(), callback=self.on_auth_choice)

    def on_auth_choice(self, choice: str | None) -> None:
        if choice is None:
            return
        self._auth_method = choice
        if choice == "copilot":
            self.push_screen(
                CopilotAuthScreen(), callback=self.on_copilot_authenticated
            )
        else:
            self.push_screen(ProviderScreen(), callback=self.on_provider_selected)

    # --- API Key path ---

    def on_provider_selected(self, result: tuple[str, str, str] | None) -> None:
        if result is None:
            return
        self._provider, self._model, self._api_key_prefill = result
        self.push_screen(
            ExchangeScreen(self._provider, self._model),
            callback=self.on_exchange_configured,
        )

    def on_exchange_configured(
        self, result: tuple[int, str, str, bool, int, int] | None
    ) -> None:
        if result is None:
            return
        (
            self._tokens,
            self._want_provider,
            self._want_model,
            self._advanced,
            self._input_tokens,
            self._output_tokens,
        ) = result
        if self._auth_method == "copilot":
            self._start_status(
                api_key=self._copilot_token,
                auth_method="copilot",
                github_token=self._github_token,
            )
        else:
            self.push_screen(
                KeyScreen(self._provider, initial_key=self._api_key_prefill),
                callback=self.on_key_validated,
            )

    def on_key_validated(self, api_key: str | None) -> None:
        if api_key is None:
            return
        self._start_status(api_key=api_key, auth_method="api_key")

    # --- Copilot path ---

    def on_copilot_authenticated(self, result: tuple[str, str] | None) -> None:
        if result is None:
            self.push_screen(AuthChoiceScreen(), callback=self.on_auth_choice)
            return
        self._copilot_token, self._github_token = result
        self._provider = "github-copilot"
        self.push_screen(
            CopilotModelScreen(self._copilot_token),
            callback=self.on_copilot_model_selected,
        )

    def on_copilot_model_selected(self, model: str | None) -> None:
        if model is None:
            return
        self._model = model
        self.push_screen(
            ExchangeScreen(self._provider, self._model),
            callback=self.on_exchange_configured,
        )

    # --- Shared ---

    def _start_status(
        self,
        api_key: str,
        auth_method: str = "api_key",
        github_token: str = "",
    ) -> None:
        config = ExchangeConfig(
            provider=self._provider,
            model=self._model,
            tokens_offered=(
                self._input_tokens + self._output_tokens
                if self._advanced
                else self._tokens
            ),
            want_provider=self._want_provider,
            want_model=self._want_model,
            api_key=api_key,
            auth_method=auth_method,
            github_token=github_token,
            input_tokens_offered=self._input_tokens if self._advanced else 0,
            output_tokens_offered=self._output_tokens if self._advanced else 0,
            advanced=self._advanced,
        )
        self.push_screen(StatusScreen(config))


def main():
    app = TokenHubApp()
    app.run()
