"""Per-model token prices.

Open WebUI never reports what a request cost — it only reports token counts, so
spend has to be reconstructed here from a price table.

Prices are $ per 1M tokens, the unit every provider publishes, split into
``input`` / ``output`` and (where the provider offers prompt caching)
``cache_read`` / ``cache_write``. The hosted entries below are published list
prices captured as a **snapshot (July 2026)** — they drift, so treat them as a
sensible default, not gospel, and override the ones you actually bill against
(see "Overriding prices" below). The local Ollama entries are *mock* prices,
invented so that a local-only instance still produces a non-zero cost signal to
build and demo the dashboard against.

Lookup is exact-match first, then longest matching prefix, so `gpt-4o-2024-11-20`
resolves to the `gpt-4o` row and `claude-opus-4-5-20260101` to `claude-opus-4-5`
without needing an entry per snapshot date.

Overriding prices (two ways, both merged on top of the built-in table):
  * MODEL_PRICES_CSV  — path to a CSV sheet (human-friendly; open it in Excel).
                        Columns: model, provider, input_per_1m, output_per_1m,
                        cache_read_per_1m, cache_write_per_1m. See
                        model_prices.example.csv for the template.
  * MODEL_PRICES_FILE — path to a JSON file of {"model-id": [input, output]} or
                        {"model-id": [input, output, cache_read, cache_write]}.
CSV is applied last, so it wins over both the built-in table and the JSON file.
"""

import csv
import json
import logging
import os
from collections import namedtuple

log = logging.getLogger("openwebui-exporter")

# A model's rate card, all in $ per 1M tokens. cache_read / cache_write are 0
# when the provider has no prompt-caching tier (or we simply don't track it).
Price = namedtuple("Price", ["input", "output", "cache_read", "cache_write"])

# model id -> Price
MODEL_PRICES = {}
# model id -> provider label ("openai", "anthropic", ...), purely descriptive.
MODEL_PROVIDER = {}


def _add(provider, model, inp, out, cache_read=0.0, cache_write=0.0):
    MODEL_PRICES[model] = Price(float(inp), float(out), float(cache_read), float(cache_write))
    MODEL_PROVIDER[model] = provider


# --- Local Ollama: MOCK prices. Real local inference costs $0 in API fees;
# these stand in for an internal chargeback rate so cost panels have data.
_add("ollama", "llama3.2:1b", 0.05, 0.10)
_add("ollama", "qwen3.5:2b", 0.08, 0.16)
_add("ollama", "agent-model", 0.20, 0.60)

# --- OpenAI (https://openai.com/api/pricing/). Cached input ~= 10% of input.
# GPT-5.6 (Sol/Terra/Luna) went GA 2026-07-09; GPT-5.5 is the prior flagship.
_add("openai", "gpt-5.6", 5.00, 30.00, cache_read=0.50)        # Sol (flagship)
_add("openai", "gpt-5.6-terra", 2.50, 15.00, cache_read=0.25)
_add("openai", "gpt-5.6-luna", 1.00, 6.00, cache_read=0.10)
_add("openai", "gpt-5.5", 5.00, 30.00, cache_read=0.50)
_add("openai", "gpt-5.5-pro", 30.00, 180.00)                   # no cached-input tier
_add("openai", "gpt-5.1", 1.25, 10.00, cache_read=0.125)
_add("openai", "gpt-5", 1.25, 10.00, cache_read=0.125)
_add("openai", "gpt-5-mini", 0.25, 2.00, cache_read=0.025)
_add("openai", "gpt-5-nano", 0.05, 0.40, cache_read=0.005)
_add("openai", "gpt-4.1", 2.00, 8.00, cache_read=0.50)
_add("openai", "gpt-4o", 2.50, 10.00, cache_read=1.25)
_add("openai", "gpt-4o-mini", 0.15, 0.60, cache_read=0.075)
_add("openai", "o4-mini", 1.10, 4.40, cache_read=0.275)

# --- Anthropic (https://platform.claude.com/docs/en/about-claude/pricing).
# cache_read ~= 10% of input, cache_write (5m TTL) ~= 1.25x input.
_add("anthropic", "claude-opus-4-8", 5.00, 25.00, cache_read=0.50, cache_write=6.25)  # flagship, GA 2026-05-28
_add("anthropic", "claude-opus-4-5", 5.00, 25.00, cache_read=0.50, cache_write=6.25)
_add("anthropic", "claude-sonnet-5", 3.00, 15.00, cache_read=0.30, cache_write=3.75)  # $2/$10 intro thru 2026-08-31
_add("anthropic", "claude-sonnet-4-6", 3.00, 15.00, cache_read=0.30, cache_write=3.75)
_add("anthropic", "claude-sonnet-4-5", 3.00, 15.00, cache_read=0.30, cache_write=3.75)
_add("anthropic", "claude-haiku-4-5", 1.00, 5.00, cache_read=0.10, cache_write=1.25)
_add("anthropic", "claude-fable-5", 10.00, 50.00, cache_read=1.00, cache_write=12.50)

# --- Google Gemini (https://ai.google.dev/gemini-api/docs/pricing).
# Pro rises to 4/18 above a 200K-token prompt; the base tier is listed here.
_add("google", "gemini-3.1-pro", 2.00, 12.00, cache_read=0.20)
_add("google", "gemini-3.5-flash", 1.50, 9.00, cache_read=0.15)
_add("google", "gemini-3-flash", 0.50, 3.00, cache_read=0.05)
_add("google", "gemini-3.1-flash-lite", 0.25, 1.50, cache_read=0.025)
_add("google", "gemini-2.5-pro", 1.25, 10.00, cache_read=0.31)
_add("google", "gemini-2.5-flash", 0.30, 2.50, cache_read=0.075)

# --- xAI Grok (https://docs.x.ai/developers/models).
_add("xai", "grok-4.5", 2.00, 6.00, cache_read=0.50)   # 500K ctx; surcharge >200K
_add("xai", "grok-4.3", 1.25, 2.50, cache_read=0.31)   # 1M ctx
_add("xai", "grok-4-fast", 0.20, 0.50, cache_read=0.05)
_add("xai", "grok-4", 3.00, 15.00, cache_read=0.75)

# --- DeepSeek V3.2 (https://api-docs.deepseek.com/quick_start/pricing).
_add("deepseek", "deepseek-chat", 0.28, 0.42, cache_read=0.028)
_add("deepseek", "deepseek-reasoner", 0.28, 0.42, cache_read=0.028)

# --- Alibaba Qwen (https://www.alibabacloud.com/help/en/model-studio/models).
_add("qwen", "qwen3.7-max", 1.25, 3.75)   # flagship (promo; list is 2.50/7.50)
_add("qwen", "qwen-max", 1.25, 3.75)
_add("qwen", "qwen-plus", 0.40, 1.20)
_add("qwen", "qwen-turbo", 0.05, 0.20)

# --- Zhipu / Z.ai GLM (https://docs.z.ai/guides/overview/pricing).
_add("zai", "glm-5.2", 1.40, 4.40)
_add("zai", "glm-5", 0.60, 1.92)
_add("zai", "glm-4.7", 0.40, 1.75)
_add("zai", "glm-4.6", 0.60, 2.00)

# --- Mistral (https://mistral.ai/pricing).
_add("mistral", "mistral-large-3", 0.50, 1.50)   # Large 3 (2512)
_add("mistral", "mistral-large", 0.50, 1.50)
_add("mistral", "mistral-small", 0.20, 0.60)
_add("mistral", "codestral", 0.30, 0.90)

# Fallback for any model with no table entry. The legacy COST_PER_1K_* vars feed
# it, so an existing flat-rate config keeps working unchanged.
DEFAULT_INPUT_PER_1M = float(os.environ.get("COST_PER_1K_INPUT_TOKENS", "0")) * 1000
DEFAULT_OUTPUT_PER_1M = float(os.environ.get("COST_PER_1K_OUTPUT_TOKENS", "0")) * 1000


def _coerce_price(rates):
    """Accept [in, out], [in, out, cache_read, cache_write], or a dict."""
    if isinstance(rates, dict):
        return Price(
            float(rates.get("input", 0) or 0),
            float(rates.get("output", 0) or 0),
            float(rates.get("cache_read", 0) or 0),
            float(rates.get("cache_write", 0) or 0),
        )
    vals = [float(x or 0) for x in rates]
    vals += [0.0] * (4 - len(vals))  # pad missing cache fields with 0
    return Price(*vals[:4])


def _load_json_overrides():
    """MODEL_PRICES_FILE: JSON of {"model-id": [input_per_1m, output_per_1m, ...]}."""
    path = os.environ.get("MODEL_PRICES_FILE")
    if not path:
        return
    try:
        with open(path) as fh:
            data = json.load(fh)
    except Exception:
        log.exception("could not read MODEL_PRICES_FILE=%s; skipping", path)
        return
    for model_id, rates in data.items():
        MODEL_PRICES[model_id] = _coerce_price(rates)
    log.info("loaded %s model price overrides from JSON %s", len(data), path)


# CSV header aliases -> canonical field. Headers are matched case-insensitively
# with surrounding whitespace stripped, so a sheet exported from Excel just works.
_CSV_ALIASES = {
    "model": "model", "model_id": "model", "name": "model",
    "provider": "provider", "vendor": "provider",
    "input_per_1m": "input", "input": "input", "input_usd_per_1m": "input",
    "output_per_1m": "output", "output": "output", "output_usd_per_1m": "output",
    "cache_read_per_1m": "cache_read", "cache_read": "cache_read",
    "cached_input_per_1m": "cache_read", "cache_hit": "cache_read",
    "cache_write_per_1m": "cache_write", "cache_write": "cache_write",
    "cache_creation_per_1m": "cache_write",
}


def _num(row, key):
    val = row.get(key)
    if val is None or str(val).strip() == "":
        return 0.0
    return float(str(val).strip())


def _load_csv_overrides():
    """MODEL_PRICES_CSV: a price sheet with model/provider/input/output/cache cols."""
    path = os.environ.get("MODEL_PRICES_CSV")
    if not path:
        return
    try:
        with open(path, newline="") as fh:
            # Drop blank and #-comment lines so the template can carry notes.
            lines = [ln for ln in fh if ln.strip() and not ln.lstrip().startswith("#")]
        reader = csv.DictReader(lines)
        if not reader.fieldnames:
            log.warning("MODEL_PRICES_CSV=%s has no header row; skipping", path)
            return
        # Remap headers to canonical field names.
        fieldmap = {fn: _CSV_ALIASES.get((fn or "").strip().lower()) for fn in reader.fieldnames}
        count = 0
        for raw in reader:
            row = {fieldmap[k]: v for k, v in raw.items() if fieldmap.get(k)}
            model_id = (row.get("model") or "").strip()
            if not model_id:
                continue
            MODEL_PRICES[model_id] = Price(
                _num(row, "input"), _num(row, "output"),
                _num(row, "cache_read"), _num(row, "cache_write"),
            )
            provider = (row.get("provider") or "").strip()
            if provider:
                MODEL_PROVIDER[model_id] = provider
            count += 1
    except Exception:
        log.exception("could not read MODEL_PRICES_CSV=%s; skipping", path)
        return
    log.info("loaded %s model price overrides from CSV %s", count, path)


_load_json_overrides()
_load_csv_overrides()  # CSV wins over JSON and the built-in table


def price_for(model_id):
    """Return the Price (input, output, cache_read, cache_write $/1M) for a model."""
    if model_id in MODEL_PRICES:
        return MODEL_PRICES[model_id]
    prefixes = [k for k in MODEL_PRICES if model_id.startswith(k)]
    if prefixes:
        return MODEL_PRICES[max(prefixes, key=len)]
    return Price(DEFAULT_INPUT_PER_1M, DEFAULT_OUTPUT_PER_1M, 0.0, 0.0)


def provider_for(model_id):
    """Best-effort provider label for a model id ('unknown' if untabled)."""
    if model_id in MODEL_PROVIDER:
        return MODEL_PROVIDER[model_id]
    prefixes = [k for k in MODEL_PROVIDER if model_id.startswith(k)]
    if prefixes:
        return MODEL_PROVIDER[max(prefixes, key=len)]
    return "unknown"


def cost_for(model_id, input_tokens, output_tokens, cache_read_tokens=0, cache_write_tokens=0):
    """Estimated USD for one model's token usage.

    cache_read_tokens / cache_write_tokens are the cached portion of the prompt
    when the backend reports it (e.g. prompt_tokens_details.cached_tokens); they
    are billed at the model's cache rate and subtracted from the standard input
    so the same token is never charged twice. When a model has no cache rate, or
    the backend reports no cached tokens, this is identical to the plain
    input*rate + output*rate it always was.
    """
    p = price_for(model_id)
    billable_input = max(0, input_tokens - cache_read_tokens - cache_write_tokens)
    cost = (billable_input / 1e6) * p.input + (output_tokens / 1e6) * p.output
    if cache_read_tokens:
        cost += (cache_read_tokens / 1e6) * (p.cache_read or p.input)
    if cache_write_tokens:
        cost += (cache_write_tokens / 1e6) * (p.cache_write or p.input)
    return cost
