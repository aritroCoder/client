def extract_openai_models_from_catalog(payload: object) -> list[str]:
    if not isinstance(payload, list):
        return []

    models: list[str] = []
    seen: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id")
        if not isinstance(model_id, str) or not model_id:
            continue
        normalized_id = model_id.strip().lower()
        if not normalized_id.startswith("openai/"):
            continue
        canonical = normalized_id.split("/", 1)[1]
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        models.append(canonical)
    return models