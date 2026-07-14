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

# Model metadata / ops (from /api/models). Sizes/context are per-model gauges;
# static string attributes ride along as labels on an info metric fixed to 1.
MODEL_SIZE_BYTES = Gauge("openwebui_model_size_bytes", "On-disk size of the model weights", ["model"])
MODEL_CONTEXT_LENGTH = Gauge("openwebui_model_context_length", "Max context length (tokens)", ["model"])
MODEL_CAPABILITY = Gauge(
    "openwebui_model_capability", "1 if the model advertises this capability", ["model", "capability"]
)
MODEL_INFO = Gauge(
    "openwebui_model_info",
    "Static model attributes as labels (value is always 1)",
    ["model", "owned_by", "family", "parameter_size", "quantization"],
)

# Top users / cost. The person's display name and email both ride as labels so
# panels can show a human name (falling back to email) instead of an opaque id.
USER_MESSAGES_TOTAL = Gauge("openwebui_user_messages_total", "Messages sent per user", ["user", "email"])
USER_INPUT_TOKENS_TOTAL = Gauge("openwebui_user_input_tokens_total", "Input tokens consumed per user", ["user", "email"])
USER_OUTPUT_TOKENS_TOTAL = Gauge("openwebui_user_output_tokens_total", "Output tokens generated per user", ["user", "email"])
USER_TOTAL_TOKENS = Gauge("openwebui_user_total_tokens", "Total tokens (input+output) per user", ["user", "email"])
USER_ESTIMATED_COST_USD = Gauge(
    "openwebui_user_estimated_cost_usd",
    "Estimated spend per user from configured $/1k-token rates",
    ["user", "email"],
)

# Engagement (derived from /api/v1/chats/stats/usage)
MESSAGES_TOTAL = Gauge("openwebui_messages_total", "Total messages across all chats")
USER_MESSAGES_GLOBAL_TOTAL = Gauge("openwebui_user_messages_global_total", "Total user (human) messages")
ASSISTANT_MESSAGES_TOTAL = Gauge("openwebui_assistant_messages_total", "Total assistant (model) messages")
AVG_MESSAGES_PER_CHAT = Gauge("openwebui_avg_messages_per_chat", "Mean messages per chat (conversation depth)")
AVG_USER_MESSAGE_LENGTH = Gauge("openwebui_avg_user_message_length_chars", "Mean user message length (characters)")
AVG_ASSISTANT_MESSAGE_LENGTH = Gauge(
    "openwebui_avg_assistant_message_length_chars", "Mean assistant message length (characters)"
)
CHAT_TAG_TOTAL = Gauge("openwebui_chat_tag_total", "Chats carrying each tag (topic breakdown)", ["tag"])

# Model quality / feedback
MODEL_FEEDBACK_POSITIVE_TOTAL = Gauge("openwebui_model_feedback_positive_total", "Positive feedback per model", ["model"])
MODEL_FEEDBACK_NEGATIVE_TOTAL = Gauge("openwebui_model_feedback_negative_total", "Negative feedback per model", ["model"])
MODEL_SATISFACTION_RATIO = Gauge(
    "openwebui_model_satisfaction_ratio", "positive / (positive+negative) feedback per model (0-1)", ["model"]
)
FEEDBACK_TOTAL = Gauge("openwebui_feedback_total", "Total rating feedback submissions")
FEEDBACK_WITH_COMMENT_TOTAL = Gauge("openwebui_feedback_with_comment_total", "Feedback entries carrying a written comment")
MODEL_LEADERBOARD_RANK = Gauge("openwebui_model_leaderboard_rank", "Arena leaderboard rank per model (lower is better)", ["model"])

# Performance
CHAT_AVG_RESPONSE_SECONDS = Gauge("openwebui_chat_avg_response_seconds", "Average response time per model", ["model"])

# Content inventory
KNOWLEDGE_BASES_TOTAL = Gauge("openwebui_knowledge_bases_total", "Total knowledge bases")
TOOLS_TOTAL = Gauge("openwebui_tools_total", "Total registered tools")
PROMPTS_TOTAL = Gauge("openwebui_prompts_total", "Total saved prompts")
FUNCTIONS_TOTAL = Gauge("openwebui_functions_total", "Total registered functions")

# Exporter self-health
EXPORTER_SCRAPE_SUCCESS = Gauge("openwebui_exporter_scrape_success", "Whether the last full scrape cycle succeeded (1/0)")
EXPORTER_LAST_SCRAPE_DURATION_SECONDS = Gauge(
    "openwebui_exporter_last_scrape_duration_seconds", "Duration of the last scrape cycle"
)
EXPORTER_SCRAPE_ERRORS_TOTAL = Counter(
    "openwebui_exporter_scrape_errors_total", "Errors encountered per endpoint during scraping", ["endpoint"]
)
