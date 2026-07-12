"""Central Prometheus metric definitions, shared by exporter.py and all collectors."""

from prometheus_client import Counter, Gauge

# Usage & adoption
USERS_TOTAL = Gauge("openwebui_users_total", "Total users", ["role"])
USERS_ACTIVE_TOTAL = Gauge("openwebui_users_active_total", "Users active within window", ["window"])
GROUPS_TOTAL = Gauge("openwebui_groups_total", "Total groups")
GROUP_MEMBERS = Gauge("openwebui_group_members", "Members per group", ["group_name"])
CHATS_TOTAL = Gauge("openwebui_chats_total", "Total chats")
CHATS_ARCHIVED_TOTAL = Gauge("openwebui_chats_archived_total", "Archived chats")

# Top models / providers
MODEL_MESSAGES_TOTAL = Gauge("openwebui_model_messages_total", "Messages per model", ["model", "owned_by"])
MODEL_UNIQUE_USERS = Gauge("openwebui_model_unique_users", "Unique users per model", ["model"])
MODEL_UNIQUE_CHATS = Gauge("openwebui_model_unique_chats", "Unique chats per model", ["model"])
MODEL_LOADED = Gauge("openwebui_model_loaded", "Whether model is currently loaded in memory (1/0)", ["model"])
PROVIDER_MODELS_TOTAL = Gauge("openwebui_provider_models_total", "Models registered per provider", ["owned_by"])

# Top users / cost
USER_MESSAGES_TOTAL = Gauge("openwebui_user_messages_total", "Messages sent per user", ["user_email"])
USER_INPUT_TOKENS_TOTAL = Gauge("openwebui_user_input_tokens_total", "Input tokens consumed per user", ["user_email"])
USER_OUTPUT_TOKENS_TOTAL = Gauge("openwebui_user_output_tokens_total", "Output tokens generated per user", ["user_email"])

# Model quality / feedback
MODEL_FEEDBACK_POSITIVE_TOTAL = Gauge("openwebui_model_feedback_positive_total", "Positive feedback per model", ["model"])
MODEL_FEEDBACK_NEGATIVE_TOTAL = Gauge("openwebui_model_feedback_negative_total", "Negative feedback per model", ["model"])
MODEL_LEADERBOARD_RANK = Gauge("openwebui_model_leaderboard_rank", "Leaderboard rank per model (lower is better)", ["model"])

# Performance
CHAT_AVG_RESPONSE_SECONDS = Gauge("openwebui_chat_avg_response_seconds", "Average response time per model", ["model"])

# Content inventory
KNOWLEDGE_BASES_TOTAL = Gauge("openwebui_knowledge_bases_total", "Total knowledge bases")
TOOLS_TOTAL = Gauge("openwebui_tools_total", "Total registered tools")

# Exporter self-health
EXPORTER_SCRAPE_SUCCESS = Gauge("openwebui_exporter_scrape_success", "Whether the last full scrape cycle succeeded (1/0)")
EXPORTER_LAST_SCRAPE_DURATION_SECONDS = Gauge(
    "openwebui_exporter_last_scrape_duration_seconds", "Duration of the last scrape cycle"
)
EXPORTER_SCRAPE_ERRORS_TOTAL = Counter(
    "openwebui_exporter_scrape_errors_total", "Errors encountered per endpoint during scraping", ["endpoint"]
)
