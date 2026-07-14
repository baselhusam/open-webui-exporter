# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Prometheus exporter for Open WebUI. Open WebUI has no first-party `/metrics` endpoint, and the existing community exporter (`ncecere/exporter-openwebui`) requires direct PostgreSQL access. This exporter instead polls Open WebUI's REST API — including its built-in `/api/v1/analytics/*` endpoints, which return pre-aggregated per-model and per-user usage data — so it works against any backend (SQLite or Postgres) with no database credentials, only an Open WebUI API key.

**Two separate compose stacks.** `docker-compose.yml` runs only Open WebUI itself (project `open_webui_exporter`; pointed at a natively-running Ollama on the host via `host.docker.internal`, not a containerized Ollama — see the comment block at the top of that file for why). `docker-compose.monitoring.yml` runs the observability stack — exporter + Prometheus + Grafana (project `openwebui-monitoring`, set via a top-level `name:` so it never shares networks/volumes with or orphans the app). The exporter reaches Open WebUI over `host.docker.internal:3000`, so the two stacks stay decoupled; start the app first, then the monitoring stack. Host ports: Open WebUI `3000`, exporter `9090`, Prometheus `9091`, Grafana `3001`. The Open WebUI data lives in the named volume `open_webui_exporter_open-webui_data` — never `docker compose down -v` the app stack.

## Commands

```bash
# Install deps into the existing .venv
.venv/bin/pip install -r requirements.txt

# Run standalone (needs OPENWEBUI_BASE_URL and OPENWEBUI_API_KEY; copy .env.example -> .env)
export $(cat .env | xargs)
.venv/bin/python exporter.py

# Verify metrics are being served
curl http://localhost:9090/metrics

# Compile-check all Python files (no test suite exists yet)
.venv/bin/python -m py_compile exporter.py metrics.py collectors/*.py scripts/*.py

# Run the whole thing with Docker Compose (app first, then monitoring)
docker compose up -d                                          # Open WebUI on :3000
docker compose -f docker-compose.monitoring.yml up -d --build # exporter/prometheus/grafana

# Regenerate the Grafana dashboard JSON after editing the layout builder
.venv/bin/python grafana/build_dashboard.py

# Seed / tear down realistic mock data for demoing the dashboard.
# NOTE: run from the host, so override BASE_URL to localhost — .env points the
# exporter *container* at host.docker.internal, which won't resolve on the host.
export $(cat .env | xargs)
OPENWEBUI_BASE_URL=http://localhost:3000 .venv/bin/python scripts/seed_mock_data.py
OPENWEBUI_BASE_URL=http://localhost:3000 .venv/bin/python scripts/teardown_mock_data.py
```

There is no test suite, linter, or formatter configured — `py_compile` is currently the only automated check.

## Architecture

**Poll-based, not push-based.** A single background daemon thread (`exporter.py::poll_loop`) wakes up every `POLL_INTERVAL_SECONDS` (default 30s), calls every collector once, and `prometheus_client.start_http_server` serves whatever is currently in the in-memory Gauge/Counter registry on the main thread. There is no per-scrape-request fetching — Prometheus scraping `/metrics` just reads whatever the last poll cycle wrote.

**Collector isolation is the core design constraint.** Each collector function in `collectors/` is called independently inside its own `try/except` in `exporter.py::poll_once`. One endpoint failing (bad auth, Open WebUI down, unexpected response shape) must never crash the process or block other collectors — it increments `EXPORTER_SCRAPE_ERRORS_TOTAL{endpoint=...}` and flips `EXPORTER_SCRAPE_SUCCESS` to 0 instead. Any new collector must follow this pattern: do its own `get_json` calls, let exceptions propagate up to `poll_once`'s try/except rather than swallowing them internally.

**Two-step dependency between collectors.** `collect_models` runs first and returns a `model_id -> owned_by` dict, which is passed into `collect_model_analytics` to label `/api/v1/analytics/models` data with the correct provider (ollama/openai/arena). This is the one place collector ordering matters; it's handled explicitly in `exporter.py::poll_once`, not via shared global state.

**Metric definitions live in one place.** All Prometheus Gauges/Counters are declared in `metrics.py` and imported by whichever collector(s) populate them — `exporter.py` and the collectors never construct metric objects themselves. When adding a new metric, add it to `metrics.py` first.

**`collectors/client.py::get_json`** is the single shared HTTP call wrapper (Bearer auth session, 5s timeout, raises on any failure) — all collectors route through it rather than calling `requests` directly.

**Endpoint scope matters: some Open WebUI endpoints are admin-wide, others are scoped to the calling user.** `/api/v1/analytics/*` and `/api/v1/evaluations/feedbacks/all/export` are admin-wide (they see every user). But `/api/v1/chats/stats/usage` and `/api/v1/chats/archived/count` are scoped to the *requester* — using them undercounts to just the API key's own chats. So `collect_chats_stats` instead pulls the admin-wide `/api/v1/chats/all/db` and aggregates message counts, user/assistant splits, content lengths, tags, archived count, and per-model response times client-side. This is a heavier per-poll fetch (full chat objects), but it's the same global-pull pattern the feedback collector already uses, and it's the only way these totals are correct on a multi-user instance.

**Per-model token usage is not exposed by the analytics API.** `/api/v1/analytics/models` returns only `count`/`unique_users`/`unique_chats` per model — no token fields. `/api/v1/analytics/users` returns `user_id`, `name`, `email`, and token counts, but no model breakdown, so it can't price a mix of cheap and expensive models on its own.

**Cost is reconstructed, never reported.** Open WebUI has no notion of price. `pricing.py` holds the rate table (model id -> `(input $/1M, output $/1M)`, exact match then longest prefix, overridable via a `MODEL_PRICES_FILE` JSON; `COST_PER_1K_*` is now only the fallback for unpriced models). The **local Ollama entries in that table are mock prices** — placeholders so a local-only instance produces a non-zero cost signal to build the dashboard against. The only place both halves of the multiplication exist is the raw chat messages (each assistant message carries `model` *and* a `usage` block), so `collect_chats_stats` — which already fetches `/api/v1/chats/all/db` — is what applies the table and owns `openwebui_model_estimated_cost_usd` and `openwebui_user_estimated_cost_usd`, plus `openwebui_model_price_usd_per_1m_tokens` (the rate card itself, so the dashboard can show which price produced a cost). Do not reintroduce a flat blended rate in `collect_user_analytics`.

**A second two-step dependency: `collect_user_analytics` -> `collect_chats_stats`.** Like `collect_models` -> `collect_model_analytics`, the first returns a `user_id -> (name, email)` map that the second needs to label per-user cost with a human name. Both pairs run explicitly in `poll_once` (each still in its own `try/except`), *not* in the `STEPS` list.

**Known API gaps** (see notes in `README.md` and comments in `collectors/feedback.py`): `/api/v1/users/` is only fetched as a single page (no pagination yet). Feedback counts are aggregated client-side from `/api/v1/evaluations/feedbacks/all/export` (the `/feedbacks/models` endpoint only returns a bare `list[str]` of model ids with no counts, so it is not used); the Arena `/leaderboard` stays empty until users run side-by-side battles, which is separate from thumbs up/down. Open WebUI reports `average_assistant_message_content_length` as 0 for older chats, so assistant-length is computed from raw message `content` in `collect_chats_stats`.

**Mock-data scripts** (`scripts/seed_mock_data.py`, `scripts/teardown_mock_data.py`) populate a real instance with users/groups/knowledge-bases/chats/feedback purely through the REST API (creating users, signing in as each, and POSTing chats whose assistant messages carry fabricated `usage` blocks — no inference). Everything is namespaced (`@mock.local` emails, `[mock]`-suffixed groups/KBs) so teardown can find and delete it.

## Grafana dashboard

`grafana/dashboard.json` is **generated** by `grafana/build_dashboard.py` (a small panel/grid builder that validates the 24-col layout has no overlaps) — edit the builder and rerun it rather than hand-editing the JSON.

Panels reference the datasource via a `${DS_PROMETHEUS}` template variable whose `current` defaults to uid `openwebui-prometheus`. That uid matches the datasource provisioned in `grafana/provisioning/datasources/datasource.yml`, so **file-provisioning resolves it automatically** (no substitution needed) when the monitoring stack brings Grafana up. On manual UI import into some other Grafana, the datasource picker remaps it. If importing programmatically via the `/api/dashboards/db` API against a datasource with a *different* uid, replace the `${DS_PROMETHEUS}`/`openwebui-prometheus` references with that uid first.
