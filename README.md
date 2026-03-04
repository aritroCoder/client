# TokenHub Client

A Python Textual TUI app for exchanging LLM API tokens across providers.

## Overview

The client allows users to share a portion of their LLM API budget in exchange for access to a different provider's model. It runs a local aiohttp proxy and ngrok tunnel to securely relay requests from a matched peer.

### Features
- TUI-based provider and model selection.
- Automated API key validation.
- Secure local proxy for peer access.
- Auto-generated usage snippets for peer models.
- Automatic budget enforcement and 429 status on exhaustion.

## Requirements

- Python 3.11+
- textual, httpx, aiohttp, pyngrok

## Installation

```bash
pip install -e .
```

## Running the Client

Start the application with:
```bash
tokenhub
```

Or run the module directly:
```bash
python -m client.app
```

## Configuration

Control the client via environment variables:

- `TOKENHUB_SERVER`: Server WebSocket URL (default: `ws://localhost:8080`)
- `NGROK_AUTHTOKEN`: Optional ngrok auth token for longer sessions.

## Advanced Token Mode

Use the "Advanced" toggle to specify separate budgets for input and output tokens. This allows more precise exchange rates based on the specific cost structures of different models (e.g., cheap input, expensive output). If your peer also supports advanced mode, pricing is split accordingly. Otherwise, the exchange falls back to a simple total token count.

## How the Exchange Works

1. Select your model and what you want in return.
2. Enter your token budget and API key.
3. The app connects to the TokenHub server and waits for a peer.
4. Once paired, the app provides a URL, a temporary key, and a code snippet to access the peer's model through their local proxy.
