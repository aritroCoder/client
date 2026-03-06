# TokenHub Client

Share part of your LLM API budget and get access to a different provider's model in return. You offer tokens on OpenAI, Anthropic, or Gemini — and receive equivalent tokens on whichever provider you pick.

## How it works

1. Pick the model you want to share and the one you want access to
2. Enter your token budget and API key
3. The app waits for a peer with the opposite offer
4. Once paired, you get a temporary URL and key to call their model, and they get one to call yours

Your API key never leaves your machine — it sits behind a local proxy that enforces the budget and shuts down when tokens run out.

## Quickstart

```bash
pip install -e .
tokenhub
```

Set `TOKENHUB_SERVER` to point at your server (defaults to `ws://localhost:8080`).  
Set `NGROK_AUTHTOKEN` if you have an ngrok account (optional, but gives longer sessions).

## Advanced mode

Toggle "Advanced" on the exchange screen to split your budget into separate input and output token pools. If your peer also uses advanced mode, exchange rates are calculated per token type. Otherwise it falls back to a simple total.
