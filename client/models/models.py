from __future__ import annotations
from dataclasses import dataclass
from typing import TypedDict

from client.models.utils import to_int


# Providers list for share and want provider dropdowns
PROVIDERS = [
    "openai",
    "anthropic",
    "gemini",
    "github-copilot",
]

class UsageData(TypedDict):
    tokens_granted_upd: int
    tokens_to_serve_upd: int
    input_tokens_granted_upd: int
    output_tokens_granted_upd: int
    input_tokens_to_serve_upd: int
    output_tokens_to_serve_upd: int

@dataclass
class ExchangeConfig:
    provider: str
    model: str
    tokens_offered: int
    want_provider: str
    want_model: str
    api_key: str
    auth_method: str = "api_key"  # "api_key" or "copilot"
    github_token: str = ""  # GitHub OAuth token (for copilot token refresh)
    input_tokens_offered: int = 0
    output_tokens_offered: int = 0
    advanced: bool = False
    proxy_port: int = 9100
    proxy_url: str = ""

    def register_message(self) -> dict[str, str | int]:
        tokens_offered = self.tokens_offered
        if self.advanced:
            tokens_offered = self.input_tokens_offered + self.output_tokens_offered

        message = {
            "type": "register",
            "provider": self.provider,
            "model": self.model,
            "tokens_offered": tokens_offered,
            "want_provider": self.want_provider,
            "want_model": self.want_model,
            "proxy_url": self.proxy_url,
        }
        if self.advanced:
            message["input_tokens_offered"] = self.input_tokens_offered
            message["output_tokens_offered"] = self.output_tokens_offered
        return message

class PairingInfo:
    # meta
    offer_id: str
    temp_key: str
    proxy_key: str
    peer_url: str
    peer_provider: str
    peer_model: str

    # offers and wants
    tokens_granted: int
    tokens_to_serve: int
    # offer and wants (advanced)
    input_tokens_granted: int = 0
    output_tokens_granted: int = 0
    input_tokens_to_serve: int = 0
    output_tokens_to_serve: int = 0
    advanced: bool = False

    # current exchange status
    tokens_granted_done: int = 0
    tokens_to_serve_done: int = 0
    # current exchange status (advanced)
    input_tokens_granted_done: int = 0
    output_tokens_granted_done: int = 0
    input_tokens_to_serve_done: int = 0
    output_tokens_to_serve_done: int = 0


    def __init__(self, msg: dict[str, object]) -> None:
        self.offer_id = str(msg.get("offer_id", ""))
        self.temp_key = str(msg.get("temp_key", ""))
        self.proxy_key = str(msg.get("proxy_key", ""))
        self.peer_url = str(msg.get("peer_url", ""))
        self.peer_provider = str(msg.get("peer_provider", ""))
        self.peer_model = str(msg.get("peer_model", ""))
        self.tokens_granted = to_int(msg.get("tokens_granted", 0))
        self.tokens_to_serve = to_int(msg.get("tokens_to_serve", 0))
        self.input_tokens_granted = to_int(msg.get("input_tokens_granted", 0))
        self.output_tokens_granted = to_int(msg.get("output_tokens_granted", 0))
        self.input_tokens_to_serve = to_int(msg.get("input_tokens_to_serve", 0))
        self.output_tokens_to_serve = to_int(msg.get("output_tokens_to_serve", 0))
        self.advanced = (
            self.input_tokens_granted > 0
            or self.output_tokens_granted > 0
            or self.input_tokens_to_serve > 0
            or self.output_tokens_to_serve > 0
        )
    
    def update_usage(self, msg: UsageData) -> None:
        """
        Update the usage info based on a status message from the peer.
        
        Args:
            msg: Status message containing:
                - tokens_granted_upd (int): Total tokens granted that have been used
                - tokens_to_serve_upd (int): Total tokens to serve that have been used
                - input_tokens_granted_upd (int): Input tokens granted that have been used
                - output_tokens_granted_upd (int): Output tokens granted that have been used
                - input_tokens_to_serve_upd (int): Input tokens to serve that have been used
                - output_tokens_to_serve_upd (int): Output tokens to serve that have been used
        """
        if not self.advanced:
            self.tokens_granted_done += to_int(msg.get("tokens_granted_upd", 0))
            self.tokens_to_serve_done += to_int(msg.get("tokens_to_serve_upd", 0))
        else:
            self.input_tokens_granted_done += to_int(msg.get("input_tokens_granted_upd", 0))
            self.output_tokens_granted_done += to_int(msg.get("output_tokens_granted_upd", 0))
            self.input_tokens_to_serve_done += to_int(msg.get("input_tokens_to_serve_upd", 0))
            self.output_tokens_to_serve_done += to_int(msg.get("output_tokens_to_serve_upd", 0))
    
    def is_fulfilled(self) -> bool:
        if not self.advanced:
            return self.tokens_granted_done >= self.tokens_granted and self.tokens_to_serve_done >= self.tokens_to_serve
        else:
            return (
                self.input_tokens_granted_done >= self.input_tokens_granted and
                self.output_tokens_granted_done >= self.output_tokens_granted and
                self.input_tokens_to_serve_done >= self.input_tokens_to_serve and
                self.output_tokens_to_serve_done >= self.output_tokens_to_serve
            )
    
    def remaining_offer(self):
        if not self.advanced:
            return {
                "tokens_granted_rem": max(self.tokens_granted - self.tokens_granted_done, 0),
                "tokens_to_serve_rem": max(self.tokens_to_serve - self.tokens_to_serve_done, 0),
            }
        else:
            return {
                "tokens_granted_rem": max(self.input_tokens_granted + self.output_tokens_granted - self.input_tokens_granted_done - self.output_tokens_granted_done, 0),
                "tokens_to_serve_rem": max(self.input_tokens_to_serve + self.output_tokens_to_serve - self.input_tokens_to_serve_done - self.output_tokens_to_serve_done, 0),
                "input_tokens_granted_rem": max(self.input_tokens_granted - self.input_tokens_granted_done, 0),
                "output_tokens_granted_rem": max(self.output_tokens_granted - self.output_tokens_granted_done, 0),
                "input_tokens_to_serve_rem": max(self.input_tokens_to_serve - self.input_tokens_to_serve_done, 0),
                "output_tokens_to_serve_rem": max(self.output_tokens_to_serve - self.output_tokens_to_serve_done, 0),
            }