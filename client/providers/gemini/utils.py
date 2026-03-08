import html
import re


def extract_public_gemini_models(page: str, pattern: str) -> list[str]:
    text = html.unescape(page).lower()

    models: list[str] = []
    seen: set[str] = set()
    for raw in re.findall(pattern, text):
        model = raw.strip().lower().strip(".,:;`'\"()[]{}")
        model = re.sub(r"\s+", "-", model)
        model = re.sub(r"-+", "-", model).strip("-")
        if not model or model in seen:
            continue
        seen.add(model)
        models.append(model)
    return models


def extract_gemini_models_from_payload(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return []

    models: list[str] = []
    seen: set[str] = set()
    for item in payload.get("models", []):
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        methods = item.get("supportedGenerationMethods", [])
        if not isinstance(name, str) or not name:
            continue
        if not isinstance(methods, list) or "generateContent" not in methods:
            continue
        normalized = name[7:] if name.startswith("models/") else name
        if normalized and normalized not in seen:
            seen.add(normalized)
            models.append(normalized)
    return models
