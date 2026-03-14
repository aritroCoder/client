from __future__ import annotations

import unittest
from typing import cast

import aiohttp

from client.models.models import ExchangeConfig, PairingInfo
from client.screens.StatusScreen import StatusScreen


class _DummyWS:
    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    async def send_json(self, payload: dict[str, object]) -> None:
        self.sent.append(payload)


class StatusUsageReportTests(unittest.IsolatedAsyncioTestCase):
    async def test_usage_report_sends_delta_not_cumulative(self) -> None:
        config = ExchangeConfig(
            provider="openai",
            model="gpt-4.1-mini",
            tokens_offered=150,
            want_provider="openai",
            want_model="gpt-5-mini",
            api_key="test-key",
        )
        screen = StatusScreen(config)
        screen._update_table = lambda: None
        screen._pairing = PairingInfo(
            {
                "offer_id": "offer-1",
                "temp_key": "temp",
                "proxy_key": "proxy",
                "peer_url": "https://peer.example",
                "peer_provider": "openai",
                "peer_model": "gpt-5-mini",
                "tokens_granted": 133,
                "tokens_to_serve": 150,
            }
        )
        ws = _DummyWS()
        screen._ws = cast(aiohttp.ClientWebSocketResponse, cast(object, ws))

        await screen.on_proxy_tokens_served(21, 0)
        await screen.on_proxy_tokens_served(21, 0)

        self.assertEqual([payload["tokens"] for payload in ws.sent], [21, 21])
        self.assertEqual([payload["input_tokens"] for payload in ws.sent], [21, 21])
        self.assertEqual([payload["output_tokens"] for payload in ws.sent], [0, 0])
        assert screen._pairing is not None
        self.assertEqual(screen._pairing.tokens_to_serve_done, 42)
