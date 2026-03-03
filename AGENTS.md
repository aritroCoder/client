# PROJECT KNOWLEDGE BASE

**Generated:** 2026-03-03
**Commit:** 9058d38
**Branch:** master

## OVERVIEW

TokenHub client — Python Textual TUI that pairs users to exchange LLM API tokens across providers. Runs a local proxy (aiohttp + ngrok) to forward requests using the real API key, metered by a token budget.

## STRUCTURE

```
.
├── client/           # Python package (all app code lives here)
│   ├── app.py        # TUI entry: TokenHubApp + 4 Screens (provider→exchange→key→status)
│   ├── api.py        # Provider config (base URLs, auth headers) + key validation
│   ├── models.py     # Dataclasses: ExchangeConfig, PairingInfo; PROVIDERS dict
│   ├── proxy.py      # Local aiohttp proxy server + ngrok tunnel + token budget tracking
│   ├── app.tcss      # Textual CSS (layout/styling)
│   └── __init__.py   # Package marker (empty)
├── pyproject.toml    # PEP 621 metadata, deps, entry point
└── .gitignore
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Add/change LLM provider | `client/models.py` (PROVIDERS dict) + `client/api.py` (PROVIDER_CONFIG, validate_key) + `client/proxy.py` (handler + auth + token extraction) | All three must stay in sync |
| Change TUI screens/flow | `client/app.py` | Screen stack: Provider→Exchange→Key→Status. Navigation via push_screen callbacks |
| Change proxy behavior | `client/proxy.py` | Auth verification, budget enforcement, request forwarding |
| Change styling | `client/app.tcss` | Textual CSS |
| Change deps/entry point | `pyproject.toml` | Entry: `tokenhub = "client.app:main"` |

## CONVENTIONS

- **Python ≥3.11** required (`from __future__ import annotations` used throughout)
- No linter/formatter configured — no black, ruff, flake8, mypy sections in pyproject.toml
- No tests exist
- No CI/CD, Dockerfile, or Makefile
- Textual `@work(exclusive=True)` decorator for async operations in screens
- Provider-specific logic uses if/elif chains (not registry/dispatch pattern)

## ANTI-PATTERNS (THIS PROJECT)

- **Broad except swallowing**: `except Exception: pass` in `app.py:watch_status_text` and `proxy.py:_disconnect_tunnel` — hides real errors
- **Silent token miscount**: `proxy.py:_extract_tokens` returns 0 on parse failure — budget tracking can undercount
- **No input validation on pairing messages**: `PairingInfo.from_message` trusts all fields exist with correct types

## ENVIRONMENT VARIABLES

| Variable | Default | Used in |
|----------|---------|---------|
| `TOKENHUB_SERVER` | `ws://localhost:8080` | `app.py` — WebSocket server URL (app appends `/ws`) |
| `NGROK_AUTHTOKEN` | `""` (empty) | `proxy.py` — ngrok auth; tunnel works without it but with limits |

## RUNTIME DETAILS

- Default proxy port: **9100** (defined in `ExchangeConfig.proxy_port`)
- Proxy exposes a single provider-specific endpoint (e.g., `/v1/chat/completions` for OpenAI)
- Incoming proxy requests authenticated via temp_key in provider-appropriate header
- Token budget: hard cut at `_used >= _budget` → returns HTTP 429
- ngrok tunnel created at proxy start, disconnected at stop

## COMMANDS

```bash
# Install (editable)
pip install -e .

# Run
tokenhub
# or
python -m client.app

# No test/lint/build commands configured
```

## NOTES

- The `client/` package dir lives inside a project dir also called `client` — path is `client/client/`. Watch for confusion.
- Adding a new provider requires changes in 3 files (models, api, proxy) — keep them in sync.
- WebSocket protocol: client sends `register` message, server responds with `ack` then `paired` (with temp_key, peer info, token grants).
- `.env` is gitignored — secrets expected there or in environment.
