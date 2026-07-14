"""Remove everything seed_mock_data.py created, leaving your real data intact.

Deletes: all users with an @mock.local email (and their chats cascade with the
user), plus any group or knowledge base whose name ends with "[mock]".

Usage:
    export $(cat .env | xargs)
    .venv/bin/python scripts/teardown_mock_data.py
"""
import os

import requests

BASE_URL = os.environ.get("OPENWEBUI_BASE_URL", "http://localhost:3000").rstrip("/")
API_KEY = os.environ["OPENWEBUI_API_KEY"]
ADMIN = {"Authorization": f"Bearer {API_KEY}"}
MOCK_DOMAIN = "@mock.local"
MOCK_TAG = "[mock]"


def main():
    print(f"Removing mock data from {BASE_URL} ...")

    # Knowledge bases
    kbs = requests.get(f"{BASE_URL}/api/v1/knowledge/", headers=ADMIN, timeout=15).json()
    for kb in kbs.get("items", kbs if isinstance(kbs, list) else []):
        if str(kb.get("name", "")).endswith(MOCK_TAG):
            requests.delete(f"{BASE_URL}/api/v1/knowledge/{kb['id']}/delete", headers=ADMIN, timeout=15)
            print(f"  kb    - {kb['name']}")

    # Groups
    groups = requests.get(f"{BASE_URL}/api/v1/groups/", headers=ADMIN, timeout=15).json()
    for g in groups:
        if str(g.get("name", "")).endswith(MOCK_TAG):
            requests.delete(f"{BASE_URL}/api/v1/groups/id/{g['id']}/delete", headers=ADMIN, timeout=15)
            print(f"  group - {g['name']}")

    # Users (chats are owned by the user and go away with them)
    users = requests.get(f"{BASE_URL}/api/v1/users/?page=1", headers=ADMIN, timeout=15).json().get("users", [])
    removed = 0
    for u in users:
        if str(u.get("email", "")).endswith(MOCK_DOMAIN):
            r = requests.delete(f"{BASE_URL}/api/v1/users/{u['id']}", headers=ADMIN, timeout=15)
            if r.ok:
                removed += 1
                print(f"  user  - {u['email']}")
    print(f"\nDone: removed {removed} mock users (+ their chats), mock groups and KBs.")


if __name__ == "__main__":
    main()
