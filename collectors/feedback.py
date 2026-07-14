"""Model feedback and leaderboard collectors.

Feedback counts are aggregated from /api/v1/evaluations/feedbacks/all/export,
which returns every user's raw feedback record (admin-only). Each "rating"
feedback carries data.rating = 1 (thumbs up) or -1 (thumbs down) and a
data.model_id, so positive/negative tallies (and a satisfaction ratio) are
computed per model here. A written data.comment, when present, is also counted.

(The sibling /feedbacks/models endpoint only returns a flat list of model-id
strings with no counts, and /leaderboard returns pre-aggregated Arena Elo
entries already sorted best-first — and stays empty until users run
side-by-side Arena battles, which is separate from thumbs up/down.)
"""

from collectors.client import get_json
from metrics import (
    FEEDBACK_TOTAL,
    FEEDBACK_WITH_COMMENT_TOTAL,
    MODEL_FEEDBACK_NEGATIVE_TOTAL,
    MODEL_FEEDBACK_POSITIVE_TOTAL,
    MODEL_LEADERBOARD_RANK,
    MODEL_SATISFACTION_RATIO,
)


def collect_feedback(session, base_url):
    data = get_json(session, base_url, "/api/v1/evaluations/feedbacks/all/export")
    # Endpoint returns a bare list; tolerate a wrapped {"items": [...]} too.
    entries = data if isinstance(data, list) else data.get("items", [])

    positive = {}
    negative = {}
    total = 0
    with_comment = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        fdata = entry.get("data") or {}
        model_id = fdata.get("model_id") or (entry.get("meta") or {}).get("model_id") or "unknown"
        rating = fdata.get("rating") or 0
        if rating > 0:
            positive[model_id] = positive.get(model_id, 0) + 1
            total += 1
        elif rating < 0:
            negative[model_id] = negative.get(model_id, 0) + 1
            total += 1
        if (fdata.get("comment") or "").strip():
            with_comment += 1

    FEEDBACK_TOTAL.set(total)
    FEEDBACK_WITH_COMMENT_TOTAL.set(with_comment)

    MODEL_FEEDBACK_POSITIVE_TOTAL.clear()
    MODEL_FEEDBACK_NEGATIVE_TOTAL.clear()
    MODEL_SATISFACTION_RATIO.clear()
    for model_id in set(positive) | set(negative):
        pos = positive.get(model_id, 0)
        neg = negative.get(model_id, 0)
        MODEL_FEEDBACK_POSITIVE_TOTAL.labels(model=model_id).set(pos)
        MODEL_FEEDBACK_NEGATIVE_TOTAL.labels(model=model_id).set(neg)
        MODEL_SATISFACTION_RATIO.labels(model=model_id).set(pos / (pos + neg) if (pos + neg) else 0)


def collect_leaderboard(session, base_url):
    data = get_json(session, base_url, "/api/v1/evaluations/leaderboard")
    entries = data.get("entries", []) if isinstance(data, dict) else []

    MODEL_LEADERBOARD_RANK.clear()
    # Entries arrive already sorted best-first (highest Elo rating), so the
    # enumeration index is the rank (1 = best).
    for rank, entry in enumerate(entries, start=1):
        model_id = entry.get("model_id", "unknown")
        MODEL_LEADERBOARD_RANK.labels(model=model_id).set(rank)
