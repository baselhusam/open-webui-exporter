"""Shared HTTP helper for all collectors."""

REQUEST_TIMEOUT_SECONDS = 5


def get_json(session, base_url, path, params=None):
    """GET base_url+path and return parsed JSON. Raises on any HTTP/network/JSON error."""
    resp = session.get(f"{base_url}{path}", params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp.json()
