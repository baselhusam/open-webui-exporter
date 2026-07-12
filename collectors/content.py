"""Knowledge base and tools inventory collectors."""

from collectors.client import get_json
from metrics import KNOWLEDGE_BASES_TOTAL, TOOLS_TOTAL


def collect_knowledge(session, base_url):
    data = get_json(session, base_url, "/api/v1/knowledge/")
    KNOWLEDGE_BASES_TOTAL.set(data.get("total", len(data.get("items", []))))


def collect_tools(session, base_url):
    tools = get_json(session, base_url, "/api/v1/tools/")
    TOOLS_TOTAL.set(len(tools))
