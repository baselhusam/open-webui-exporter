"""Generate a refined, native-feeling Grafana dashboard for the Open WebUI exporter.

Stays visually "Grafana" — standard panel chrome, native row dividers — but
upgrades the widget choices, layout rhythm, colour palette and gradients:
  - cohesive cool palette (blue/teal/violet) + amber accent, semantic green/red
  - gradient bar gauges instead of flat bars
  - a radial gauge for response latency
  - gradient-filled, smoothed timeseries

Emits grafana/dashboard.json (keeps the ${DS_PROMETHEUS} template var).
"""
import json

DS = {"type": "prometheus", "uid": "${DS_PROMETHEUS}"}

# ---- Cohesive palette --------------------------------------------------------
BLUE = "#4C8DFF"
TEAL = "#37C2B9"
VIOLET = "#8E7CF0"
AMBER = "#F5B849"
GREEN = "#3FB68B"
RED = "#E0655B"
SLATE = "#8A94A6"

panels = []
_id = [0]


def nid():
    _id[0] += 1
    return _id[0]


def grid(x, y, w, h):
    return {"x": x, "y": y, "w": w, "h": h}


def row(title, y):
    return {"id": nid(), "type": "row", "title": title, "collapsed": False,
            "gridPos": grid(0, y, 24, 1), "panels": []}


def stat(title, expr, x, y, w, h, *, unit="short", color=BLUE, sparkline=True,
         mappings=None, thresholds=None, decimals=None, no_value=None):
    fc = {
        "defaults": {
            "unit": unit,
            "color": {"mode": "fixed", "fixedColor": color},
            "mappings": mappings or [],
            "thresholds": {"mode": "absolute",
                           "steps": thresholds or [{"color": color, "value": None}]},
        },
        "overrides": [],
    }
    if decimals is not None:
        fc["defaults"]["decimals"] = decimals
    if no_value is not None:
        fc["defaults"]["noValue"] = no_value
    return {
        "id": nid(),
        "title": title,
        "type": "stat",
        "datasource": DS,
        "gridPos": grid(x, y, w, h),
        "fieldConfig": fc,
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "orientation": "auto",
            "textMode": "value_and_name",
            "colorMode": "value",
            "graphMode": "area" if sparkline else "none",
            "justifyMode": "center",
            "wideLayout": True,
            "showPercentChange": False,
        },
        "targets": [{"expr": expr, "legendFormat": title, "instant": not sparkline,
                     "datasource": DS, "refId": "A"}],
    }


def gauge(title, expr, x, y, w, h, *, unit="short", minv=0, maxv=100, steps=None, legend="{{model}}"):
    return {
        "id": nid(),
        "title": title,
        "type": "gauge",
        "datasource": DS,
        "gridPos": grid(x, y, w, h),
        "fieldConfig": {
            "defaults": {
                "unit": unit, "min": minv, "max": maxv,
                "color": {"mode": "thresholds"},
                "thresholds": {"mode": "absolute", "steps": steps or [
                    {"color": GREEN, "value": None},
                    {"color": AMBER, "value": maxv * 0.5},
                    {"color": RED, "value": maxv * 0.8},
                ]},
            },
            "overrides": [],
        },
        "options": {
            "orientation": "auto",
            "showThresholdLabels": False,
            "showThresholdMarkers": True,
            "sizing": "auto",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
        },
        "targets": [{"expr": expr, "legendFormat": legend, "instant": True,
                     "datasource": DS, "refId": "A"}],
    }


def bargauge(title, expr, x, y, w, h, *, legend, unit="short", scheme="continuous-BlPu",
             minv=0, maxv=None, decimals=None):
    # Gradient fill (continuous scheme); min=0 keeps a single-series result filling
    # the track instead of rendering an empty bar.
    defaults = {
        "unit": unit, "min": minv,
        "color": {"mode": scheme},
        "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]},
    }
    if maxv is not None:
        defaults["max"] = maxv
    if decimals is not None:
        defaults["decimals"] = decimals
    return {
        "id": nid(),
        "title": title,
        "type": "bargauge",
        "datasource": DS,
        "gridPos": grid(x, y, w, h),
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": {
            "displayMode": "gradient",
            "orientation": "horizontal",
            "showUnfilled": True,
            "valueMode": "color",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
        },
        "targets": [{"expr": expr, "legendFormat": legend, "instant": True,
                     "datasource": DS, "refId": "A"}],
    }


def donut(title, expr, x, y, w, h, *, legend, color_overrides=None):
    overrides = [
        {"matcher": {"id": "byName", "options": name},
         "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": col}}]}
        for name, col in (color_overrides or {}).items()
    ]
    return {
        "id": nid(),
        "title": title,
        "type": "piechart",
        "datasource": DS,
        "gridPos": grid(x, y, w, h),
        "fieldConfig": {"defaults": {"color": {"mode": "palette-classic"}}, "overrides": overrides},
        "options": {
            "pieType": "donut",
            "displayLabels": ["percent"],
            "legend": {"displayMode": "table", "placement": "right",
                       "values": ["value", "percent"], "showLegend": True},
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "tooltip": {"mode": "single", "sort": "desc"},
        },
        "targets": [{"expr": expr, "legendFormat": legend, "instant": True,
                     "datasource": DS, "refId": "A"}],
    }


def barchart(title, x, y, w, h, targets, *, unit="short", overrides=None):
    return {
        "id": nid(),
        "title": title,
        "type": "barchart",
        "datasource": DS,
        "gridPos": grid(x, y, w, h),
        "fieldConfig": {
            "defaults": {"unit": unit, "color": {"mode": "palette-classic"},
                         "custom": {"lineWidth": 1, "fillOpacity": 85, "gradientMode": "hue"}},
            "overrides": overrides or [],
        },
        "options": {
            "orientation": "horizontal",
            "showValue": "auto",
            "stacking": "none",
            "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
        "targets": [dict(t, datasource=DS) for t in targets],
    }


def timeseries(title, x, y, w, h, targets, *, unit="short", fill=25, style="line", color=None):
    defaults = {
        "unit": unit,
        "color": {"mode": "fixed", "fixedColor": color} if color else {"mode": "palette-classic"},
        "custom": {
            "drawStyle": style,
            "lineInterpolation": "smooth",
            "lineWidth": 2,
            "fillOpacity": fill,
            "gradientMode": "opacity",
            "showPoints": "never",
            "spanNulls": True,
            "pointSize": 5,
            "stacking": {"mode": "none", "group": "A"},
            "axisPlacement": "auto",
        },
    }
    return {
        "id": nid(),
        "title": title,
        "type": "timeseries",
        "datasource": DS,
        "gridPos": grid(x, y, w, h),
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": {
            "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True, "calcs": []},
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
        "targets": [dict(t, datasource=DS) for t in targets],
    }


def table(title, expr, x, y, w, h, *, legend, no_value=None, transformations=None):
    defaults = {"color": {"mode": "thresholds"},
                "custom": {"align": "auto", "cellOptions": {"type": "auto"}}}
    if no_value is not None:
        defaults["noValue"] = no_value
    return {
        "id": nid(),
        "title": title,
        "type": "table",
        "datasource": DS,
        "gridPos": grid(x, y, w, h),
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": {"showHeader": True, "cellHeight": "sm",
                    "footer": {"show": False, "reducer": ["sum"], "fields": ""}},
        "transformations": transformations or [],
        "targets": [{"expr": expr, "format": "table", "instant": True,
                     "legendFormat": legend, "datasource": DS, "refId": "A"}],
    }


HEALTH_MAP = [{"type": "value", "options": {
    "1": {"text": "HEALTHY", "color": GREEN, "index": 0},
    "0": {"text": "FAILING", "color": RED, "index": 1},
}}]

# Keep only the label columns that matter for info/capability tables.
ONLY_LABELS = lambda keep: [
    {"id": "labelsToFields", "options": {"mode": "columns"}},
    {"id": "organize", "options": {
        "excludeByName": {"Time": True, "Value": True, "__name__": True,
                          "instance": True, "job": True}}},
]

# ============================================================ OVERVIEW (HERO KPIs)
panels.append(row("Overview", 0))
y = 1
# Hero tiles use instant queries (sparkline=False): they show a current total,
# and a range-query sparkline renders "No data" for freshly-added metrics that
# lack history. The trend lives in the Cumulative timeseries panels below.
panels.append(stat("Total Users", "sum(openwebui_users_total)", 0, y, 3, 4, color=BLUE, sparkline=False))
panels.append(stat("Active 24h", 'openwebui_users_active_total{window="24h"}', 3, y, 3, 4, color=TEAL, sparkline=False))
panels.append(stat("Total Chats", "openwebui_chats_total", 6, y, 3, 4, color=VIOLET, sparkline=False))
panels.append(stat("Total Messages", "openwebui_messages_total", 9, y, 3, 4, color=BLUE, sparkline=False))
panels.append(stat("Total Tokens", "sum(openwebui_user_total_tokens)", 12, y, 3, 4, color=TEAL, sparkline=False))
panels.append(stat(
    "Satisfaction",
    "sum(openwebui_model_feedback_positive_total) / "
    "clamp_min(sum(openwebui_model_feedback_positive_total) + sum(openwebui_model_feedback_negative_total), 1)",
    15, y, 3, 4, unit="percentunit", color=GREEN, sparkline=False, no_value="N/A"))
panels.append(stat("Est. Spend", "sum(openwebui_user_estimated_cost_usd)", 18, y, 3, 4,
                   unit="currencyUSD", color=AMBER, decimals=2, sparkline=False))
panels.append(stat("Exporter Health", "openwebui_exporter_scrape_success", 21, y, 3, 4,
                   color=GREEN, sparkline=False, mappings=HEALTH_MAP,
                   thresholds=[{"color": RED, "value": None}, {"color": GREEN, "value": 1}]))

# ============================================================ TOP USERS
panels.append(row("Top Users", 5))
y = 6
panels.append(bargauge("Top Users by Messages", "topk(10, openwebui_user_messages_total)",
                       0, y, 8, 8, legend="{{user}}", scheme="continuous-BlPu"))
panels.append(bargauge("Top Users by Total Tokens", "topk(10, openwebui_user_total_tokens)",
                       8, y, 8, 8, legend="{{user}}", scheme="continuous-blues"))
panels.append(bargauge("Top Users by Est. Cost", "topk(10, openwebui_user_estimated_cost_usd)",
                       16, y, 8, 8, legend="{{user}}", unit="currencyUSD",
                       scheme="continuous-GrYlRd", decimals=2))

# ============================================================ TOKEN ECONOMICS
panels.append(row("Token Economics", 14))
y = 15
panels.append(barchart("Tokens: Input vs Output", 0, y, 8, 8, [
    {"expr": "sum(openwebui_user_input_tokens_total)", "legendFormat": "Input", "instant": True, "refId": "A"},
    {"expr": "sum(openwebui_user_output_tokens_total)", "legendFormat": "Output", "instant": True, "refId": "B"},
], overrides=[
    {"matcher": {"id": "byName", "options": "Input"},
     "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": BLUE}}]},
    {"matcher": {"id": "byName", "options": "Output"},
     "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": TEAL}}]},
]))
panels.append(timeseries("Cumulative Tokens", 8, y, 8, 8, [
    {"expr": "sum(openwebui_user_input_tokens_total)", "legendFormat": "Input", "refId": "A"},
    {"expr": "sum(openwebui_user_output_tokens_total)", "legendFormat": "Output", "refId": "B"},
    {"expr": "sum(openwebui_user_total_tokens)", "legendFormat": "Total", "refId": "C"},
], fill=15))
panels.append(timeseries("Cumulative Messages", 16, y, 8, 8, [
    {"expr": "openwebui_user_messages_global_total", "legendFormat": "User", "refId": "A"},
    {"expr": "openwebui_assistant_messages_total", "legendFormat": "Assistant", "refId": "B"},
], fill=15))

# ============================================================ MODELS & PROVIDERS
panels.append(row("Models & Providers", 23))
y = 24
panels.append(donut("Provider Breakdown", "openwebui_provider_models_total", 0, y, 8, 8,
                    legend="{{owned_by}}",
                    color_overrides={"ollama": BLUE, "arena": VIOLET, "openai": TEAL}))
panels.append(bargauge("Top Models by Messages", "topk(10, openwebui_model_messages_total)",
                       8, y, 8, 8, legend="{{model}} ({{owned_by}})", scheme="continuous-GrYlRd"))
panels.append(bargauge("Top Models by Unique Users", "topk(10, openwebui_model_unique_users)",
                       16, y, 8, 8, legend="{{model}}", scheme="continuous-purples"))

# ============================================================ MODEL CATALOG
panels.append(row("Model Catalog & Capabilities", 32))
y = 33
panels.append(table("Model Catalog", "openwebui_model_info", 0, y, 14, 8,
                    legend="{{model}}", no_value="—",
                    transformations=ONLY_LABELS(None)))
panels.append(bargauge("Model Size on Disk", "openwebui_model_size_bytes",
                       14, y, 10, 8, legend="{{model}}", unit="bytes", scheme="continuous-BlYlRd"))
y = 41
panels.append(bargauge("Context Length by Model", "openwebui_model_context_length",
                       0, y, 12, 7, legend="{{model}}", unit="short", scheme="continuous-blues"))
panels.append(table("Model Capabilities", "openwebui_model_capability",
                    12, y, 12, 7, legend="{{model}} {{capability}}",
                    no_value="No capability metadata",
                    transformations=ONLY_LABELS(None)))

# ============================================================ QUALITY & FEEDBACK
panels.append(row("Quality & Feedback", 48))
y = 49
panels.append(stat("Feedback Total", "openwebui_feedback_total", 0, y, 6, 4, color=BLUE, sparkline=False))
panels.append(stat("With Comments", "openwebui_feedback_with_comment_total", 6, y, 6, 4,
                   color=VIOLET, sparkline=False))
panels.append(stat("Feedback Coverage",
                   "openwebui_feedback_total / clamp_min(openwebui_assistant_messages_total, 1)",
                   12, y, 6, 4, unit="percentunit", color=TEAL, sparkline=False, no_value="N/A"))
panels.append(stat("Rated Models", "count(openwebui_model_satisfaction_ratio)", 18, y, 6, 4,
                   color=AMBER, sparkline=False, no_value="0"))
y = 53
fb_overrides = [
    {"matcher": {"id": "byRegexp", "options": ".*positive.*"},
     "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": GREEN}}]},
    {"matcher": {"id": "byRegexp", "options": ".*negative.*"},
     "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": RED}}]},
]
panels.append(barchart("Feedback (Positive vs Negative)", 0, y, 12, 8, [
    {"expr": "openwebui_model_feedback_positive_total", "legendFormat": "{{model}} positive", "instant": True, "refId": "A"},
    {"expr": "openwebui_model_feedback_negative_total", "legendFormat": "{{model}} negative", "instant": True, "refId": "B"},
], overrides=fb_overrides))
panels.append(bargauge("Satisfaction Rate by Model", "openwebui_model_satisfaction_ratio",
                       12, y, 8, 8, legend="{{model}}", unit="percentunit",
                       minv=0, maxv=1, scheme="continuous-RdYlGr", decimals=0))
panels.append(table("Arena Leaderboard", "openwebui_model_leaderboard_rank", 20, y, 4, 8,
                    legend="{{model}}", no_value="No arena battles yet"))

# ============================================================ ENGAGEMENT & CONTENT
panels.append(row("Engagement & Content", 61))
y = 62
panels.append(stat("Avg Messages / Chat", "openwebui_avg_messages_per_chat", 0, y, 6, 4,
                   color=VIOLET, sparkline=False, decimals=1))
panels.append(stat("Avg User Msg Length", "openwebui_avg_user_message_length_chars", 6, y, 6, 4,
                   unit="short", color=BLUE, sparkline=False, decimals=0))
panels.append(stat("Avg Assistant Msg Length", "openwebui_avg_assistant_message_length_chars", 12, y, 6, 4,
                   unit="short", color=TEAL, sparkline=False, decimals=0))
panels.append(stat("Archived Chats", "openwebui_chats_archived_total", 18, y, 6, 4,
                   color=SLATE, sparkline=False))
y = 66
panels.append(barchart("Chats by Topic Tag", 0, y, 12, 7, [
    {"expr": "topk(15, openwebui_chat_tag_total)", "legendFormat": "{{tag}}", "instant": True, "refId": "A"},
]))
panels.append(barchart("Content Inventory", 12, y, 12, 7, [
    {"expr": "openwebui_knowledge_bases_total", "legendFormat": "Knowledge Bases", "instant": True, "refId": "A"},
    {"expr": "openwebui_tools_total", "legendFormat": "Tools", "instant": True, "refId": "B"},
    {"expr": "openwebui_prompts_total", "legendFormat": "Prompts", "instant": True, "refId": "C"},
    {"expr": "openwebui_functions_total", "legendFormat": "Functions", "instant": True, "refId": "D"},
]))

# ============================================================ PERFORMANCE & TRENDS
panels.append(row("Performance & Usage Trends", 73))
y = 74
panels.append(timeseries("Average Response Time per Model", 0, y, 12, 8, [
    {"expr": "openwebui_chat_avg_response_seconds", "legendFormat": "{{model}}", "refId": "A"},
], unit="s", fill=25))
panels.append(timeseries("Messages per Day by Model", 12, y, 12, 8, [
    {"expr": "sum by (model) (increase(openwebui_model_messages_total[1d]))", "legendFormat": "{{model}}", "refId": "A"},
], unit="short", style="bars", fill=70))

# ============================================================ EXPORTER HEALTH
panels.append(row("Exporter Health", 82))
y = 83
panels.append(timeseries("Scrape Errors by Endpoint", 0, y, 16, 6, [
    {"expr": "sum by (endpoint) (increase(openwebui_exporter_scrape_errors_total[5m]))", "legendFormat": "{{endpoint}}", "refId": "A"},
], unit="short", color=RED, fill=25))
panels.append(stat("Last Scrape Duration", "openwebui_exporter_last_scrape_duration_seconds",
                   16, y, 8, 6, unit="s", color=BLUE, decimals=3))

dashboard = {
    "title": "Open WebUI",
    "uid": "openwebui-exporter",
    "tags": ["open-webui", "llm", "observability"],
    "style": "dark",
    "timezone": "browser",
    "schemaVersion": 39,
    "version": 5,
    "refresh": "30s",
    "editable": True,
    "graphTooltip": 1,
    "time": {"from": "now-6h", "to": "now"},
    "panels": panels,
    # current defaults to the provisioned datasource uid so file-provisioning
    # resolves ${DS_PROMETHEUS} without a manual pick; on UI import Grafana still
    # shows the datasource picker and remaps it.
    "templating": {"list": [{"name": "DS_PROMETHEUS", "type": "datasource",
                             "query": "prometheus", "hide": 0,
                             "label": "Prometheus", "refresh": 1,
                             "current": {"text": "Prometheus",
                                         "value": "openwebui-prometheus"}}]},
}

# --- overlap / bounds validation on the 24-col grid ------------------------
occupied = {}
for p in panels:
    g = p["gridPos"]
    assert g["x"] + g["w"] <= 24, f"{p.get('title', p['type'])} overflows width"
    for dx in range(g["w"]):
        for dy in range(g["h"]):
            c = (g["x"] + dx, g["y"] + dy)
            if c in occupied:
                raise SystemExit(f"OVERLAP at {c}: {p.get('title', p['type'])} vs {occupied[c]}")
            occupied[c] = p.get("title", p["type"])

out = "/Users/basel/Personal/open_webui_exporter/grafana/dashboard.json"
with open(out, "w") as f:
    json.dump(dashboard, f, indent=2)
print(f"OK: {len(panels)} panels, no overlaps. Wrote {out}")
