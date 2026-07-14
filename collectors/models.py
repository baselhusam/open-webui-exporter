"""Models, providers, and per-model usage analytics collectors."""

from collectors.client import get_json
from metrics import (
    MODEL_CAPABILITY,
    MODEL_CONTEXT_LENGTH,
    MODEL_INFO,
    MODEL_LOADED,
    MODEL_MESSAGES_TOTAL,
    MODEL_SIZE_BYTES,
    MODEL_UNIQUE_CHATS,
    MODEL_UNIQUE_USERS,
    PROVIDER_MODELS_TOTAL,
)


def collect_models(session, base_url):
    data = get_json(session, base_url, "/api/models")
    models = data.get("data", [])

    MODEL_LOADED.clear()
    PROVIDER_MODELS_TOTAL.clear()
    MODEL_SIZE_BYTES.clear()
    MODEL_CONTEXT_LENGTH.clear()
    MODEL_CAPABILITY.clear()
    MODEL_INFO.clear()

    owned_by_counts = {}
    for model in models:
        model_id = model.get("id", "unknown")
        owned_by = model.get("owned_by", "unknown")
        owned_by_counts[owned_by] = owned_by_counts.get(owned_by, 0) + 1
        MODEL_LOADED.labels(model=model_id).set(1 if model.get("loaded") else 0)

        # Ollama models carry rich metadata under `ollama`; hosted models
        # (openai/arena) don't, so every field access here is best-effort.
        ollama = model.get("ollama") or {}
        details = ollama.get("details") or {}

        size = ollama.get("size")
        if size:
            MODEL_SIZE_BYTES.labels(model=model_id).set(size)

        context_length = details.get("context_length")
        if context_length:
            MODEL_CONTEXT_LENGTH.labels(model=model_id).set(context_length)

        for capability in ollama.get("capabilities") or []:
            MODEL_CAPABILITY.labels(model=model_id, capability=capability).set(1)

        MODEL_INFO.labels(
            model=model_id,
            owned_by=owned_by,
            family=details.get("family") or "",
            parameter_size=details.get("parameter_size") or "",
            quantization=details.get("quantization_level") or "",
        ).set(1)

    for owned_by, count in owned_by_counts.items():
        PROVIDER_MODELS_TOTAL.labels(owned_by=owned_by).set(count)

    return {m.get("id"): m.get("owned_by", "unknown") for m in models}


def collect_model_analytics(session, base_url, model_owners):
    data = get_json(session, base_url, "/api/v1/analytics/models")
    entries = data.get("models", [])

    MODEL_MESSAGES_TOTAL.clear()
    MODEL_UNIQUE_USERS.clear()
    MODEL_UNIQUE_CHATS.clear()

    for entry in entries:
        model_id = entry.get("model_id", "unknown")
        owned_by = model_owners.get(model_id, "unknown")
        MODEL_MESSAGES_TOTAL.labels(model=model_id, owned_by=owned_by).set(entry.get("count", 0))
        MODEL_UNIQUE_USERS.labels(model=model_id).set(entry.get("unique_users", 0))
        MODEL_UNIQUE_CHATS.labels(model=model_id).set(entry.get("unique_chats", 0))
