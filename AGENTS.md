# PROJECT KNOWLEDGE BASE

**Generated:** 2026-03-13
**Commit:** 53ea955
**Branch:** fix/sse-token-overflow

## OVERVIEW

TokenHub client is a Python 3.11+ Textual TUI for pairing users who want to exchange LLM access across providers. It runs a local aiohttp proxy and an ngrok tunnel so a peer can call your real provider key through a budget-limited temporary endpoint.

## STRUCTURE

```
.
├── client/                     # Python package; app, proxy, providers, screens, models
│   ├── app.py                  # Textual app entry; screen orchestration and shared state
│   ├── api.py                  # Provider dispatch layer for validation and model fetches
│   ├── proxy.py                # aiohttp proxy + SSE token tracking + ngrok lifecycle
│   ├── copilot_auth.py         # Thin wrappers around GitHub Copilot auth helpers
│   ├── logging_config.py       # File logger setup; optional stderr mirroring
│   ├── app.tcss                # Shared Textual stylesheet
│   ├── models/
│   │   ├── models.py           # ExchangeConfig, PairingInfo, UsageData, PROVIDERS
│   │   └── utils.py            # Integer coercion helper used by models/proxy
│   ├── providers/
│   │   ├── utils.py            # Shared provider config + server-supported model helpers
│   │   ├── openai/provider.py
│   │   ├── anthropic/provider.py
│   │   ├── gemini/provider.py
│   │   └── github_copilot/provider.py
│   └── screens/
│       ├── AuthChoiceScreen.py
│       ├── ProviderScreen.py
│       ├── ExchangeScreen.py
│       ├── KeyScreen.py
│       ├── CopilotAuthScreen.py
│       ├── CopilotModelScreen.py
│       └── StatusScreen.py
├── tests/
│   └── test_proxy_headers.py   # Header forwarding / content-encoding regression tests
├── pyproject.toml              # Minimal project metadata + `tokenhub` entry point
├── README.md
├── .env.example
└── uv.lock
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Start app / change flow | `client/app.py` | `TokenHubApp` owns screen transitions and shared session state |
| Change Textual UI | `client/screens/*.py` | Each screen is a separate module; async UI work uses `@work(exclusive=True)` |
| Change styling | `client/app.tcss` | Loaded via `TokenHubApp.CSS_PATH` |
| Add/change provider | `client/providers/*/provider.py` + `client/api.py` + `client/proxy.py` + `client/models/models.py` | Provider list, dispatch wiring, proxy auth/routes, and UI-visible provider names must stay aligned |
| Change provider model fetching | `client/providers/utils.py` + provider modules | Server-supported model list comes from `TOKENHUB_SERVER` `/providers/models` |
| Change exchange payloads / pairing state | `client/models/models.py` | `ExchangeConfig.register_message()` and `PairingInfo` shape the websocket protocol |
| Change proxy behavior | `client/proxy.py` | Budget enforcement, upstream header rewriting, SSE usage extraction, ngrok lifecycle |
| Change Copilot auth flow | `client/providers/github_copilot/provider.py` + `client/copilot_auth.py` + `client/screens/CopilotAuthScreen.py` | Device code, GitHub token exchange, token refresh loop |
| Change logging behavior | `client/logging_config.py` | Logs to `~/tokenhub_<pid>.log` unless `TOKENHUB_LOG` overrides it |
| Update tests | `tests/test_proxy_headers.py` | Only test file today; focused on proxy header behavior |

## CODE MAP

| Symbol | Type | Location | Role |
|--------|------|----------|------|
| `TokenHubApp` | class | `client/app.py` | Root Textual app; routes auth/provider/exchange/status screens |
| `ProxyServer` | class | `client/proxy.py` | Local proxy server, tunnel management, token accounting |
| `ExchangeConfig` | dataclass | `client/models/models.py` | Local offer config and register message builder |
| `PairingInfo` | class | `client/models/models.py` | Runtime pairing state and token progress tracking |
| `ProviderScreen` | class | `client/screens/ProviderScreen.py` | Provider/model selection and optional live model fetch |
| `ExchangeScreen` | class | `client/screens/ExchangeScreen.py` | Offer amount, wanted provider/model, advanced-mode split |
| `StatusScreen` | class | `client/screens/StatusScreen.py` | WebSocket pairing loop, proxy start/stop, usage updates |
| `GitHubCopilotProvider` | class | `client/providers/github_copilot/provider.py` | Device auth, token refresh, Copilot model listing |

## CONVENTIONS

- Python-only repo; `from __future__ import annotations` is used broadly.
- Screen modules use PascalCase filenames (`ProviderScreen.py`, `StatusScreen.py`) rather than snake_case.
- Provider directories use snake_case paths, but provider ids exposed to users/server are lower-case strings like `openai`, `gemini`, `github-copilot`.
- Textual background work is done inside screen methods decorated with `@work(exclusive=True)`.
- Provider implementations follow a shared pattern: `PROVIDER_CONFIG`, `validate_key()`, `fetch_public_provider_models()`, `fetch_provider_models()`.
- `client/api.py` is the dispatch layer; callers should not import provider implementations directly unless they need Copilot-specific behavior.
- `pyproject.toml` is minimal: no formatter, linter, type-checker, or pytest config is declared.
- `uv.lock` is tracked, and local tooling artifacts currently visible in the repo include `.venv/`, `.ruff_cache/`, and `.pytest_cache/`.

## ANTI-PATTERNS (THIS PROJECT)

- Broad exception swallowing hides failures: `client/screens/StatusScreen.py:237`, `client/screens/StatusScreen.py:286`, `client/screens/StatusScreen.py:581`, `client/proxy.py:552`.
- Token accounting can silently undercount when response payloads change: `client/proxy.py:_extract_tokens()` falls back to `(0, 0)` and `client/models/utils.py:to_int()` falls back to `0`.
- `PairingInfo` trusts incoming websocket payloads too much; missing or malformed fields degrade to empty strings or zeroes instead of failing fast.
- `StatusScreen` mutates proxy internals directly (`proxy._temp_key`, `_total_budget`, `_input_budget`, `_output_budget`, `_advanced`) after pairing.
- Adding a provider is a cross-file change; updating only the provider module is insufficient.
- Several async fetch paths collapse to generic failure states without surfacing much context to the user, especially in `client/screens/ExchangeScreen.py` and `client/screens/CopilotModelScreen.py`.

## ENVIRONMENT VARIABLES

| Variable | Default | Used in |
|----------|---------|---------|
| `TOKENHUB_SERVER` | `ws://localhost:8080` | `client/providers/utils.py`, `client/screens/StatusScreen.py` |
| `NGROK_AUTHTOKEN` | empty | `client/proxy.py` |
| `TOKENHUB_LOG` | `~/tokenhub_<pid>.log` | `client/logging_config.py` |
| `TOKENHUB_DEBUG` | unset | `client/logging_config.py`; enables stderr logging |

## RUNTIME DETAILS

- CLI entry point is `tokenhub = "client.app:main"` in `pyproject.toml`.
- Main flow is `AuthChoiceScreen -> ProviderScreen/CopilotAuthScreen -> ExchangeScreen -> KeyScreen/CopilotModelScreen -> StatusScreen`.
- `StatusScreen.connect_and_run()` starts the proxy first, then connects to the websocket server at `TOKENHUB_SERVER + "/ws"`.
- Default local proxy port is `9100`, but `ProxyServer.start()` will probe up to 10 sequential ports.
- Proxy exposes provider-specific routes plus model discovery endpoints at `/v1/models` and `/models`.
- For streaming requests, proxy usage tracking is based on parsed SSE chunks, then clamped to remaining budget before recording totals.

## COMMANDS

```bash
# install
pip install -e .

# run
tokenhub
# or
python -m client.app

# tests
pytest tests/
```

## NOTES

- The project root and Python package are both named `client`, so paths are easy to misread (`client/client/...`).
- Root-only AGENTS coverage is enough for this repo today; `client/screens/` and `client/providers/` are distinct, but still small enough that child files would mostly duplicate root guidance.
- `.env` is gitignored, but `.env.example` documents the runtime variables future edits should preserve.
- Existing caches and local env directories are not fully ignored in `.gitignore`; do not treat `.ruff_cache/` or `.pytest_cache/` as source.
