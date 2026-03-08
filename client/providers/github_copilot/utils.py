from __future__ import annotations

import html
import re

_PUBLIC_MODEL_NAME_ALIASES: dict[str, str] = {
    "claude opus 4.6 fast mode": "claude-opus-4.6",
}


def canonicalize_public_copilot_model_name(name: str) -> str | None:
    text = html.unescape(name)
    text = re.sub(r"\[[^\]]*\]", "", text)
    text = re.sub(r"\([^)]*\)", "", text)
    text = text.strip().lower()
    if not text:
        return None

    text = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2015]", "-", text)
    text = re.sub(r"\s+", " ", text)
    if text in _PUBLIC_MODEL_NAME_ALIASES:
        return _PUBLIC_MODEL_NAME_ALIASES[text]

    text = text.replace("/", " ").replace("_", " ")
    text = re.sub(r"[^a-z0-9.\-\s]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    if not text:
        return None

    return text


def extract_public_copilot_models(page: str) -> list[str]:
    start_marker = '<h2 id="supported-ai-models-in-copilot"'
    end_marker = '<h2 id="model-retirement-history"'
    start = page.find(start_marker)
    end = page.find(end_marker)
    if start == -1 or end == -1 or end <= start:
        return []

    section = page[start:end]
    names = re.findall(r'<th scope="row">([^<]+)</th>', section)

    models: list[str] = []
    seen: set[str] = set()
    for name in names:
        canonical = canonicalize_public_copilot_model_name(name)
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        models.append(canonical)

    return models
