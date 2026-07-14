"""Knowledge base, tools, prompts, and functions inventory collectors."""

from collectors.client import get_json
from metrics import FUNCTIONS_TOTAL, KNOWLEDGE_BASES_TOTAL, PROMPTS_TOTAL, TOOLS_TOTAL


def collect_knowledge(session, base_url):
    data = get_json(session, base_url, "/api/v1/knowledge/")
    KNOWLEDGE_BASES_TOTAL.set(data.get("total", len(data.get("items", []))))


def collect_tools(session, base_url):
    tools = get_json(session, base_url, "/api/v1/tools/")
    TOOLS_TOTAL.set(len(tools))


def collect_prompts(session, base_url):
    prompts = get_json(session, base_url, "/api/v1/prompts/")
    PROMPTS_TOTAL.set(len(prompts))


def collect_functions(session, base_url):
    functions = get_json(session, base_url, "/api/v1/functions/")
    FUNCTIONS_TOTAL.set(len(functions))
