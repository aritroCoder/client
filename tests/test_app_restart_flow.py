from __future__ import annotations

import unittest
from unittest.mock import patch

from client.app import TokenHubApp
from client.screens.AuthChoiceScreen import AuthChoiceScreen


class AppRestartFlowTests(unittest.TestCase):
    def test_restart_from_auth_choice_pops_then_pushes_and_resets_state(self) -> None:
        app = TokenHubApp()
        app._provider = "openai"
        app._model = "gpt-4.1-mini"
        app._api_key_prefill = "prefill"
        app._tokens = 123
        app._want_provider = "anthropic"
        app._want_model = "claude-3-5-haiku"
        app._advanced = True
        app._input_tokens = 70
        app._output_tokens = 53
        app._auth_method = "copilot"
        app._copilot_token = "copilot-token"
        app._github_token = "github-token"

        events: list[str] = []
        with (
            patch.object(app, "pop_screen") as pop_screen,
            patch.object(app, "push_screen") as push_screen,
        ):
            pop_screen.side_effect = lambda *a, **k: events.append("pop")
            push_screen.side_effect = lambda *a, **k: events.append("push")

            app.restart_from_auth_choice()

        self.assertEqual(events, ["pop", "push"])
        pop_screen.assert_called_once_with()
        push_screen.assert_called_once()

        pushed_screen = push_screen.call_args.args[0]
        pushed_callback = push_screen.call_args.kwargs.get("callback")
        self.assertIsInstance(pushed_screen, AuthChoiceScreen)
        self.assertEqual(pushed_callback, app.on_auth_choice)

        self.assertEqual(app._provider, "")
        self.assertEqual(app._model, "")
        self.assertEqual(app._api_key_prefill, "")
        self.assertEqual(app._tokens, 0)
        self.assertEqual(app._want_provider, "")
        self.assertEqual(app._want_model, "")
        self.assertFalse(app._advanced)
        self.assertEqual(app._input_tokens, 0)
        self.assertEqual(app._output_tokens, 0)
        self.assertEqual(app._auth_method, "api_key")
        self.assertEqual(app._copilot_token, "")
        self.assertEqual(app._github_token, "")
