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
    USER_MESSAGES_GLOBAL_TOTAL,
)


def _tag_name(tag):
    """Tags may be plain strings or {id,name} dicts depending on version."""
    if isinstance(tag, dict):
        return tag.get("name") or tag.get("id")
    return tag


def collect_chats_stats(session, base_url):
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

    for entry in chats:
        if entry.get("archived"):
            archived += 1

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
