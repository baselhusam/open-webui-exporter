"""Per-model token prices.

Open WebUI never reports what a request cost — it only reports token counts, so
spend has to be reconstructed here from a price table.

Prices are $ per 1M tokens, the unit every provider publishes. The hosted
entries below are the real published list prices; the local Ollama entries are
*mock* prices, invented so that a local-only instance still produces a non-zero
cost signal to build and demo the dashboard against. Replace them (or point
MODEL_PRICES_FILE at a JSON file) once real rates matter.

Lookup is exact-match first, then longest matching prefix, so `gpt-4o-2024-11-20`
resolves to the `gpt-4o` row without needing an entry per snapshot date.
"""

import json
import logging
import os

log = logging.getLogger("openwebui-exporter")

# model id -> (input $/1M, output $/1M)
MODEL_PRICES = {
    # --- Local Ollama: MOCK prices. Real local inference costs $0 in API fees;
    # these stand in for an internal chargeback rate so cost panels have data.
    "llama3.2:1b": (0.05, 0.10),
    "qwen3.5:2b": (0.08, 0.16),
    "agent-model": (0.20, 0.60),
    # --- Hosted APIs: published list prices.
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "o3-mini": (1.10, 4.40),
    "claude-opus-4": (15.00, 75.00),
    "claude-sonnet-4": (3.00, 15.00),
    "claude-haiku-4": (0.80, 4.00),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.30, 2.50),
}

# Fallback for any model with no table entry. The legacy COST_PER_1K_* vars feed
# it, so an existing flat-rate config keeps working unchanged.
DEFAULT_INPUT_PER_1M = float(os.environ.get("COST_PER_1K_INPUT_TOKENS", "0")) * 1000
DEFAULT_OUTPUT_PER_1M = float(os.environ.get("COST_PER_1K_OUTPUT_TOKENS", "0")) * 1000


def _load_overrides():
    """MODEL_PRICES_FILE: JSON of {"model-id": [input_per_1m, output_per_1m]}."""
    path = os.environ.get("MODEL_PRICES_FILE")
    if not path:
        return
    try:
        with open(path) as fh:
            data = json.load(fh)
    except Exception:
        log.exception("could not read MODEL_PRICES_FILE=%s; using built-in prices", path)
        return
    for model_id, rates in data.items():
        MODEL_PRICES[model_id] = (float(rates[0]), float(rates[1]))
    log.info("loaded %s model price overrides from %s", len(data), path)


_load_overrides()


def price_for(model_id):
    """Return (input $/1M, output $/1M) for a model id."""
    if model_id in MODEL_PRICES:
        return MODEL_PRICES[model_id]
    prefixes = [k for k in MODEL_PRICES if model_id.startswith(k)]
    if prefixes:
        return MODEL_PRICES[max(prefixes, key=len)]
    return (DEFAULT_INPUT_PER_1M, DEFAULT_OUTPUT_PER_1M)


def cost_for(model_id, input_tokens, output_tokens):
    """Estimated USD for one model's token usage."""
    input_per_1m, output_per_1m = price_for(model_id)
    return (input_tokens / 1e6) * input_per_1m + (output_tokens / 1e6) * output_per_1m
