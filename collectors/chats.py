"""Chat volume and per-model response-time collectors."""

from collectors.client import get_json
from metrics import CHAT_AVG_RESPONSE_SECONDS, CHATS_ARCHIVED_TOTAL, CHATS_TOTAL


def collect_chats_stats(session, base_url):
    data = get_json(session, base_url, "/api/v1/chats/stats/usage")
    items = data.get("items", [])

    CHATS_TOTAL.set(data.get("total", len(items)))

    # Average response time per model, averaged across chats that used that model.
    sums = {}
    counts = {}
    for item in items:
        avg_response = item.get("average_response_time") or 0
        if avg_response <= 0:
            continue
        for model_id in (item.get("models") or {}).keys():
            sums[model_id] = sums.get(model_id, 0) + avg_response
            counts[model_id] = counts.get(model_id, 0) + 1

    CHAT_AVG_RESPONSE_SECONDS.clear()
    for model_id, total in sums.items():
        CHAT_AVG_RESPONSE_SECONDS.labels(model=model_id).set(total / counts[model_id])


def collect_chats_archived(session, base_url):
    count = get_json(session, base_url, "/api/v1/chats/archived/count")
    CHATS_ARCHIVED_TOTAL.set(count)
