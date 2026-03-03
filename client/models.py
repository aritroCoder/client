from __future__ import annotations
from dataclasses import dataclass


PROVIDERS = {
    "openai": ["gpt-4o", "gpt-4o-mini"],
    "anthropic": ["claude-sonnet-4", "claude-3.5-haiku"],
    "gemini": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
}


@dataclass
class ExchangeConfig:
    provider: str
    model: str
    tokens_offered: int
    want_provider: str
    want_model: str
    api_key: str
    proxy_port: int = 9100
    proxy_url: str = ""

    def register_message(self) -> dict:
        return {
            "type": "register",
            "provider": self.provider,
            "model": self.model,
            "tokens_offered": self.tokens_offered,
            "want_provider": self.want_provider,
            "want_model": self.want_model,
            "proxy_url": self.proxy_url,
        }


@dataclass
class PairingInfo:
    offer_id: str
    temp_key: str
    peer_url: str
    peer_provider: str
    peer_model: str
    tokens_granted: int
    tokens_to_serve: int

    @classmethod
    def from_message(cls, msg: dict) -> PairingInfo:
        return cls(
            offer_id=msg["offer_id"],
            temp_key=msg["temp_key"],
            peer_url=msg["peer_url"],
            peer_provider=msg["peer_provider"],
            peer_model=msg["peer_model"],
            tokens_granted=msg["tokens_granted"],
            tokens_to_serve=msg["tokens_to_serve"],
        )
