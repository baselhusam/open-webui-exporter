"""Chat volume, engagement, and per-model response-time collectors.

These aggregate from /api/v1/chats/all/db, the admin-wide export of every
user's chats. (The lighter /api/v1/chats/stats/usage endpoint is scoped to the
*calling* user only, so it undercounts on a multi-user instance — the totals
here are meant to be global.) This is a heavier fetch, but it matches the
exporter's existing global pull of /evaluations/feedbacks/all/export.
"""

from collectors.client import get_json
from metrics import (
    ASSISTANT_MESSAGES_TOTAL,
    AVG_ASSISTANT_MESSAGE_LENGTH,
    AVG_MESSAGES_PER_CHAT,
    AVG_USER_MESSAGE_LENGTH,
    CHAT_AVG_RESPONSE_SECONDS,
    CHAT_TAG_TOTAL,
    CHATS_ARCHIVED_TOTAL,
    CHATS_TOTAL,
    MESSAGES_TOTAL,
    MODEL_ESTIMATED_COST_USD,
    MODEL_INPUT_TOKENS_TOTAL,
    MODEL_OUTPUT_TOKENS_TOTAL,
    MODEL_PRICE_USD_PER_1M,
    USER_ESTIMATED_COST_USD,
    USER_MESSAGES_GLOBAL_TOTAL,
)
from pricing import cost_for, price_for


def _tag_name(tag):
    """Tags may be plain strings or {id,name} dicts depending on version."""
    if isinstance(tag, dict):
        return tag.get("name") or tag.get("id")
    return tag


def collect_chats_stats(session, base_url, user_map=None):
    """Aggregate chat/message stats, and price the per-message token usage.

    user_map ({user_id: (name, email)}, from collect_user_analytics) is only
    used to label per-user cost. Cost is computed here rather than in the users
    collector because /api/v1/analytics/users has no model breakdown, and a
    single blended rate can't price a mix of cheap and expensive models. The raw
    chat messages do carry both `model` and a `usage` block, so this is the only
    place both halves of the multiplication are available.
    """
    user_map = user_map or {}
    chats = get_json(session, base_url, "/api/v1/chats/all/db")
    if not isinstance(chats, list):
        chats = chats.get("items", [])

    total_chats = len(chats)
    archived = 0
    total_messages = 0
    user_messages = 0
    assistant_messages = 0
    user_len_sum = 0.0
    user_len_n = 0
    asst_len_sum = 0.0
    asst_len_n = 0
    tag_counts = {}
    resp_sum = {}
    resp_n = {}
    model_in = {}
    model_out = {}
    model_cost = {}
    user_cost = {}

    for entry in chats:
        if entry.get("archived"):
            archived += 1

        owner = entry.get("user_id")
        chat = entry.get("chat") or {}
        for tag in chat.get("tags") or []:
            name = _tag_name(tag)
            if name:
                tag_counts[name] = tag_counts.get(name, 0) + 1

        messages = (chat.get("history") or {}).get("messages") or {}
        for msg in messages.values():
            role = msg.get("role")
            content = msg.get("content") or ""
            total_messages += 1
            if role == "user":
                user_messages += 1
                if content:
                    user_len_sum += len(content)
                    user_len_n += 1
            elif role == "assistant":
                assistant_messages += 1
                if content:
                    asst_len_sum += len(content)
                    asst_len_n += 1
                # Response time: prefer the model's reported generation duration
                # (ns), else fall back to the user->assistant timestamp gap.
                model_id = msg.get("model") or "unknown"
                usage = msg.get("usage") or {}

                # Ollama and OpenAI-compatible backends name the token fields
                # differently; accept either spelling.
                in_tok = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
                out_tok = usage.get("output_tokens") or usage.get("completion_tokens") or 0
                if in_tok or out_tok:
                    model_in[model_id] = model_in.get(model_id, 0) + in_tok
                    model_out[model_id] = model_out.get(model_id, 0) + out_tok
                    spend = cost_for(model_id, in_tok, out_tok)
                    model_cost[model_id] = model_cost.get(model_id, 0.0) + spend
                    if owner:
                        user_cost[owner] = user_cost.get(owner, 0.0) + spend

                seconds = 0.0
                if usage.get("total_duration"):
                    seconds = usage["total_duration"] / 1e9
                else:
                    parent = messages.get(msg.get("parentId"))
                    if parent and parent.get("timestamp") and msg.get("timestamp"):
                        seconds = max(0, msg["timestamp"] - parent["timestamp"])
                if seconds > 0:
                    resp_sum[model_id] = resp_sum.get(model_id, 0) + seconds
                    resp_n[model_id] = resp_n.get(model_id, 0) + 1

    CHATS_TOTAL.set(total_chats)
    CHATS_ARCHIVED_TOTAL.set(archived)
    MESSAGES_TOTAL.set(total_messages)
    USER_MESSAGES_GLOBAL_TOTAL.set(user_messages)
    ASSISTANT_MESSAGES_TOTAL.set(assistant_messages)
    AVG_MESSAGES_PER_CHAT.set(total_messages / total_chats if total_chats else 0)
    AVG_USER_MESSAGE_LENGTH.set(user_len_sum / user_len_n if user_len_n else 0)
    AVG_ASSISTANT_MESSAGE_LENGTH.set(asst_len_sum / asst_len_n if asst_len_n else 0)

    CHAT_TAG_TOTAL.clear()
    for tag, count in tag_counts.items():
        CHAT_TAG_TOTAL.labels(tag=tag).set(count)

    CHAT_AVG_RESPONSE_SECONDS.clear()
    for model_id, total in resp_sum.items():
        CHAT_AVG_RESPONSE_SECONDS.labels(model=model_id).set(total / resp_n[model_id])

    MODEL_INPUT_TOKENS_TOTAL.clear()
    MODEL_OUTPUT_TOKENS_TOTAL.clear()
    MODEL_ESTIMATED_COST_USD.clear()
    MODEL_PRICE_USD_PER_1M.clear()
    for model_id in model_cost:
        MODEL_INPUT_TOKENS_TOTAL.labels(model=model_id).set(model_in.get(model_id, 0))
        MODEL_OUTPUT_TOKENS_TOTAL.labels(model=model_id).set(model_out.get(model_id, 0))
        MODEL_ESTIMATED_COST_USD.labels(model=model_id).set(model_cost[model_id])
        input_per_1m, output_per_1m = price_for(model_id)
        MODEL_PRICE_USD_PER_1M.labels(model=model_id, token_type="input").set(input_per_1m)
        MODEL_PRICE_USD_PER_1M.labels(model=model_id, token_type="output").set(output_per_1m)

    # Users beyond page 1 of /api/v1/users/ aren't in user_map (known pagination
    # gap); fall back to the raw id rather than dropping their spend.
    USER_ESTIMATED_COST_USD.clear()
    for user_id, cost in user_cost.items():
        name, email = user_map.get(user_id, (user_id, "unknown"))
        USER_ESTIMATED_COST_USD.labels(user=name, email=email).set(cost)
