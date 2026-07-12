"""Open WebUI Prometheus exporter.

Polls Open WebUI's REST API on an interval and exposes the results as
Prometheus metrics on /metrics. Configured entirely via environment
variables (see .env.example).
"""

import logging
import os
import threading
import time

import requests
from prometheus_client import start_http_server

from collectors.chats import collect_chats_archived, collect_chats_stats
from collectors.content import collect_knowledge, collect_tools
from collectors.feedback import collect_feedback, collect_leaderboard
from collectors.models import collect_model_analytics, collect_models
from collectors.users import collect_groups, collect_user_analytics, collect_users
from metrics import (
    EXPORTER_LAST_SCRAPE_DURATION_SECONDS,
    EXPORTER_SCRAPE_ERRORS_TOTAL,
    EXPORTER_SCRAPE_SUCCESS,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("openwebui-exporter")

BASE_URL = os.environ.get("OPENWEBUI_BASE_URL", "http://localhost:3000").rstrip("/")
API_KEY = os.environ.get("OPENWEBUI_API_KEY", "")
POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "30"))
EXPORTER_PORT = int(os.environ.get("EXPORTER_PORT", "9090"))

# (name, callable) pairs run each poll cycle. Each is isolated: a failure in
# one does not prevent the others from running, and increments the
# per-endpoint error counter instead of crashing the exporter.
STEPS = [
    ("users", collect_users),
    ("user_analytics", collect_user_analytics),
    ("groups", collect_groups),
    ("chats_stats", collect_chats_stats),
    ("chats_archived", collect_chats_archived),
    ("feedback", collect_feedback),
    ("leaderboard", collect_leaderboard),
    ("knowledge", collect_knowledge),
    ("tools", collect_tools),
]


def make_session():
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {API_KEY}"})
    return session


def poll_once(session):
    start = time.monotonic()
    ok = True

    # Models must run first: its return value (model -> owned_by map) feeds
    # the model-analytics step's provider labels.
    try:
        model_owners = collect_models(session, BASE_URL)
    except Exception:
        log.exception("collector 'models' failed")
        EXPORTER_SCRAPE_ERRORS_TOTAL.labels(endpoint="models").inc()
        model_owners = {}
        ok = False

    try:
        collect_model_analytics(session, BASE_URL, model_owners)
    except Exception:
        log.exception("collector 'model_analytics' failed")
        EXPORTER_SCRAPE_ERRORS_TOTAL.labels(endpoint="model_analytics").inc()
        ok = False

    for name, step in STEPS:
        try:
            step(session, BASE_URL)
        except Exception:
            log.exception("collector '%s' failed", name)
            EXPORTER_SCRAPE_ERRORS_TOTAL.labels(endpoint=name).inc()
            ok = False

    EXPORTER_SCRAPE_SUCCESS.set(1 if ok else 0)
    EXPORTER_LAST_SCRAPE_DURATION_SECONDS.set(time.monotonic() - start)


def poll_loop():
    session = make_session()
    while True:
        poll_once(session)
        time.sleep(POLL_INTERVAL_SECONDS)


def main():
    if not API_KEY:
        log.warning("OPENWEBUI_API_KEY is not set - all requests will fail authentication")

    log.info(
        "starting openwebui-exporter: base_url=%s poll_interval=%ss port=%s",
        BASE_URL,
        POLL_INTERVAL_SECONDS,
        EXPORTER_PORT,
    )

    start_http_server(EXPORTER_PORT)
    threading.Thread(target=poll_loop, daemon=True).start()

    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
