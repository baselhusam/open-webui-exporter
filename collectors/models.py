"""Models, providers, and per-model usage analytics collectors."""

from collectors.client import get_json
from metrics import (
    MODEL_LOADED,
    MODEL_MESSAGES_TOTAL,
    MODEL_UNIQUE_CHATS,
    MODEL_UNIQUE_USERS,
    PROVIDER_MODELS_TOTAL,
)


def collect_models(session, base_url):
    data = get_json(session, base_url, "/api/models")
    models = data.get("data", [])

    MODEL_LOADED.clear()
    PROVIDER_MODELS_TOTAL.clear()

    owned_by_counts = {}
    for model in models:
        model_id = model.get("id", "unknown")
        owned_by = model.get("owned_by", "unknown")
        owned_by_counts[owned_by] = owned_by_counts.get(owned_by, 0) + 1
        MODEL_LOADED.labels(model=model_id).set(1 if model.get("loaded") else 0)

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
