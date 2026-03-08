import html
import re


def extract_public_openai_models(page: str, pattern: str) -> list[str]:
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
