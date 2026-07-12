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
.venv/bin/python -m py_compile exporter.py metrics.py collectors/*.py

# Run the whole thing with Docker Compose (app first, then monitoring)
docker compose up -d                                          # Open WebUI on :3000
docker compose -f docker-compose.monitoring.yml up -d --build # exporter/prometheus/grafana

# Regenerate the Grafana dashboard JSON after editing the layout builder
.venv/bin/python grafana/build_dashboard.py
```

There is no test suite, linter, or formatter configured — `py_compile` is currently the only automated check.

## Architecture

**Poll-based, not push-based.** A single background daemon thread (`exporter.py::poll_loop`) wakes up every `POLL_INTERVAL_SECONDS` (default 30s), calls every collector once, and `prometheus_client.start_http_server` serves whatever is currently in the in-memory Gauge/Counter registry on the main thread. There is no per-scrape-request fetching — Prometheus scraping `/metrics` just reads whatever the last poll cycle wrote.

**Collector isolation is the core design constraint.** Each collector function in `collectors/` is called independently inside its own `try/except` in `exporter.py::poll_once`. One endpoint failing (bad auth, Open WebUI down, unexpected response shape) must never crash the process or block other collectors — it increments `EXPORTER_SCRAPE_ERRORS_TOTAL{endpoint=...}` and flips `EXPORTER_SCRAPE_SUCCESS` to 0 instead. Any new collector must follow this pattern: do its own `get_json` calls, let exceptions propagate up to `poll_once`'s try/except rather than swallowing them internally.

**Two-step dependency between collectors.** `collect_models` runs first and returns a `model_id -> owned_by` dict, which is passed into `collect_model_analytics` to label `/api/v1/analytics/models` data with the correct provider (ollama/openai/arena). This is the one place collector ordering matters; it's handled explicitly in `exporter.py::poll_once`, not via shared global state.

**Metric definitions live in one place.** All Prometheus Gauges/Counters are declared in `metrics.py` and imported by whichever collector(s) populate them — `exporter.py` and the collectors never construct metric objects themselves. When adding a new metric, add it to `metrics.py` first.

**`collectors/client.py::get_json`** is the single shared HTTP call wrapper (Bearer auth session, 5s timeout, raises on any failure) — all collectors route through it rather than calling `requests` directly.

**Known API gaps** (see notes in `README.md` and comments in `collectors/feedback.py`): `/api/v1/users/` is only fetched as a single page (no pagination yet). Feedback counts are aggregated client-side from `/api/v1/evaluations/feedbacks/all/export` (the `/feedbacks/models` endpoint only returns a bare `list[str]` of model ids with no counts, so it is not used).

## Grafana dashboard

`grafana/dashboard.json` is **generated** by `grafana/build_dashboard.py` (a small panel/grid builder that validates the 24-col layout has no overlaps) — edit the builder and rerun it rather than hand-editing the JSON.

Panels reference the datasource via a `${DS_PROMETHEUS}` template variable whose `current` defaults to uid `openwebui-prometheus`. That uid matches the datasource provisioned in `grafana/provisioning/datasources/datasource.yml`, so **file-provisioning resolves it automatically** (no substitution needed) when the monitoring stack brings Grafana up. On manual UI import into some other Grafana, the datasource picker remaps it. If importing programmatically via the `/api/dashboards/db` API against a datasource with a *different* uid, replace the `${DS_PROMETHEUS}`/`openwebui-prometheus` references with that uid first.
