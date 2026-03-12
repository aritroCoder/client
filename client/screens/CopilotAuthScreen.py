from __future__ import annotations

import asyncio
import webbrowser

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Static,
)
from textual import work

from client.providers.github_copilot.provider import github_copilot_provider

class CopilotAuthScreen(Screen[tuple[str, str]]):
    _verification_uri: str = "https://github.com/login/device"

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            yield Static("GitHub Copilot Authentication", classes="title")
            yield Static("", id="copilot-instructions")
            yield Static("", id="copilot-code", classes="copilot-device-code")
            yield Button(
                "Open GitHub in Browser",
                id="open-browser-btn",
                variant="primary",
            )
            yield Static("", id="copilot-status", classes="status-text")
            yield Button("← Back", id="copilot-back-btn", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#copilot-instructions", Static).update(
            "Starting device authorization..."
        )
        self.query_one("#open-browser-btn", Button).display = False
        self.start_device_flow()

    @work(exclusive=True)
    async def start_device_flow(self) -> None:
        try:
            device = await github_copilot_provider.request_device_code()

            instructions = self.query_one("#copilot-instructions", Static)
            code_display = self.query_one("#copilot-code", Static)
            browser_btn = self.query_one("#open-browser-btn", Button)
            status = self.query_one("#copilot-status", Static)

            instructions.update(
                f"Go to [bold]{device.verification_uri}[/bold] and enter this code:"
            )
            code_display.update(f"[bold]{device.user_code}[/bold]")
            browser_btn.display = True
            self._verification_uri = device.verification_uri
            status.update("Waiting for authorization...")

            github_token = await github_copilot_provider.poll_for_access_token(
                device.device_code,
                interval=device.interval,
                expires_in=device.expires_in,
            )

            status.update("Exchanging for Copilot token...")
            copilot = await github_copilot_provider.exchange_for_copilot_token(
                github_token
            )

            status.update("[green]Authenticated![/]")
            await asyncio.sleep(0.5)
            self.dismiss((copilot.copilot_token, copilot.github_token))

        except TimeoutError:
            self.query_one("#copilot-status", Static).update(
                "[red]Device code expired. Please try again.[/]"
            )
        except PermissionError as e:
            self.query_one("#copilot-status", Static).update(f"[red]{e}[/]")
        except Exception as e:
            self.query_one("#copilot-status", Static).update(
                f"[red]Authentication failed: {e}[/]"
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "open-browser-btn":
            uri = getattr(self, "_verification_uri", "https://github.com/login/device")
            webbrowser.open(uri)
        elif event.button.id == "copilot-back-btn":
            self.workers.cancel_all()
            self.dismiss(None)

