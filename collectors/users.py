"""Users and groups collectors."""

import time

from collectors.client import get_json
from metrics import (
    GROUP_MEMBERS,
    GROUPS_TOTAL,
    USER_ESTIMATED_COST_USD,
    USER_INPUT_TOKENS_TOTAL,
    USER_MESSAGES_TOTAL,
    USER_OUTPUT_TOKENS_TOTAL,
    USER_TOTAL_TOKENS,
    USERS_ACTIVE_TOTAL,
    USERS_TOTAL,
)

DAY_SECONDS = 24 * 60 * 60


def collect_users(session, base_url):
    data = get_json(session, base_url, "/api/v1/users/", params={"page": 1})
    users = data.get("users", [])

    by_role = {}
    now = time.time()
    active_24h = 0
    active_7d = 0
    for user in users:
        role = user.get("role", "unknown")
        by_role[role] = by_role.get(role, 0) + 1

        last_active_at = user.get("last_active_at")
        if last_active_at:
            age = now - last_active_at
            if age <= DAY_SECONDS:
                active_24h += 1
            if age <= 7 * DAY_SECONDS:
                active_7d += 1

    USERS_TOTAL.clear()
    for role, count in by_role.items():
        USERS_TOTAL.labels(role=role).set(count)

    USERS_ACTIVE_TOTAL.labels(window="24h").set(active_24h)
    USERS_ACTIVE_TOTAL.labels(window="7d").set(active_7d)


def collect_user_analytics(session, base_url, cost_per_1k_input=0.0, cost_per_1k_output=0.0):
    data = get_json(session, base_url, "/api/v1/analytics/users")
    entries = data.get("users", [])

    USER_MESSAGES_TOTAL.clear()
    USER_INPUT_TOKENS_TOTAL.clear()
    USER_OUTPUT_TOKENS_TOTAL.clear()
    USER_TOTAL_TOKENS.clear()
    USER_ESTIMATED_COST_USD.clear()

    for entry in entries:
        email = entry.get("email") or "unknown"
        # Display name for dashboards; fall back to email when it's blank.
        name = entry.get("name") or email
        labels = {"user": name, "email": email}

        input_tokens = entry.get("input_tokens", 0)
        output_tokens = entry.get("output_tokens", 0)
        total_tokens = entry.get("total_tokens", input_tokens + output_tokens)

        USER_MESSAGES_TOTAL.labels(**labels).set(entry.get("count", 0))
        USER_INPUT_TOKENS_TOTAL.labels(**labels).set(input_tokens)
        USER_OUTPUT_TOKENS_TOTAL.labels(**labels).set(output_tokens)
        USER_TOTAL_TOKENS.labels(**labels).set(total_tokens)

        cost = (input_tokens / 1000.0) * cost_per_1k_input + (output_tokens / 1000.0) * cost_per_1k_output
        USER_ESTIMATED_COST_USD.labels(**labels).set(cost)


def collect_groups(session, base_url):
    groups = get_json(session, base_url, "/api/v1/groups/")

    GROUPS_TOTAL.set(len(groups))

    GROUP_MEMBERS.clear()
    for group in groups:
        name = group.get("name", "unknown")
        GROUP_MEMBERS.labels(group_name=name).set(group.get("member_count", 0))
