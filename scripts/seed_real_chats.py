"""Give the mock users REAL chats: actually query the LLM (through Open WebUI ->
Ollama), then save each genuine question/answer as that user's chat.

Unlike seed_mock_data.py (which fabricates assistant text and token usage), this
runs live inference. The completion is generated with the admin key (regular
users aren't granted model access on this instance), and the resulting real
message + real token `usage` is persisted under the mock user via chats/new — so
the saved conversation is authentic model output with authentic token counts.

Runs strictly sequentially with a short pause between calls, so it never fires
concurrent requests at Ollama. It first deletes each mock user's existing
(fabricated) chats so the data ends up fully real.

Usage (from the host; override BASE_URL because .env targets the container host):
    export $(cat .env | xargs)
    OPENWEBUI_BASE_URL=http://localhost:3000 .venv/bin/python scripts/seed_real_chats.py
Optional env: CHATS_PER_USER (default 2), REAL_CHAT_MODELS (csv), PAUSE_SECONDS.
"""
import os
import random
import time
import uuid

import requests

BASE_URL = os.environ.get("OPENWEBUI_BASE_URL", "http://localhost:3000").rstrip("/")
API_KEY = os.environ["OPENWEBUI_API_KEY"]
ADMIN = {"Authorization": f"Bearer {API_KEY}"}
MOCK_DOMAIN = "@mock.local"
PASSWORD = "mockpass123"
CHATS_PER_USER = int(os.environ.get("CHATS_PER_USER", "2"))
PAUSE_SECONDS = float(os.environ.get("PAUSE_SECONDS", "1.5"))
# agent-model first: it returns content and is the fastest here. qwen3.5:2b is a
# "thinking" model, so it needs think=False to emit visible content.
MODELS = os.environ.get("REAL_CHAT_MODELS", "agent-model,qwen3.5:2b").split(",")

random.seed()

PROMPTS = [
    ("coding", "Write a short Python function to check if a string is a palindrome."),
    ("coding", "How do I safely read environment variables in Python with defaults?"),
    ("coding", "What's the difference between a list and a tuple in Python?"),
    ("research", "In two sentences, what is retrieval augmented generation?"),
    ("research", "Briefly, how does a transformer attention mechanism work?"),
    ("research", "What is the difference between LoRA and full fine-tuning?"),
    ("writing", "Draft a two-sentence friendly out-of-office email reply."),
    ("writing", "Give me three concise subject lines for a product launch email."),
    ("data-analysis", "How do I read a large CSV efficiently in pandas?"),
    ("data-analysis", "What metric should I use for imbalanced classification, and why?"),
    ("support", "How would you explain resetting a password to a non-technical user?"),
    ("support", "A web dashboard won't load. List three things to check first."),
]


def real_complete(model, messages):
    """Generate a real completion with the admin key. Returns (content, usage)."""
    body = {"model": model, "messages": messages, "stream": False}
    if "qwen" in model:
        body["think"] = False  # thinking models otherwise return empty content
    r = requests.post(f"{BASE_URL}/api/chat/completions", headers=ADMIN, json=body, timeout=180)
    r.raise_for_status()
    d = r.json()
    content = d.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
    return content, d.get("usage", {})


def signin(email):
    r = requests.post(f"{BASE_URL}/api/v1/auths/signin",
                      json={"email": email, "password": PASSWORD}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


def delete_existing_chats(user_headers):
    chats = requests.get(f"{BASE_URL}/api/v1/chats/?page=1", headers=user_headers, timeout=15).json()
    for c in chats if isinstance(chats, list) else []:
        requests.delete(f"{BASE_URL}/api/v1/chats/{c['id']}", headers=user_headers, timeout=15)
    return len(chats) if isinstance(chats, list) else 0


def save_chat(user_headers, title, model, tag, prompt, answer, usage):
    now = int(time.time())
    uid, aid = str(uuid.uuid4()), str(uuid.uuid4())
    messages = {
        uid: {"id": uid, "parentId": None, "childrenIds": [aid], "role": "user",
              "content": prompt, "timestamp": now, "models": [model]},
        aid: {"id": aid, "parentId": uid, "childrenIds": [], "role": "assistant",
              "content": answer, "done": True, "model": model, "modelName": model,
              "timestamp": now + 1, "usage": usage},
    }
    chat_obj = {"id": "", "title": title, "models": [model],
                "history": {"currentId": aid, "messages": messages},
                "messages": [messages[uid], messages[aid]], "tags": [tag],
                "timestamp": now, "files": []}
    r = requests.post(f"{BASE_URL}/api/v1/chats/new", headers=user_headers, json={"chat": chat_obj}, timeout=15)
    r.raise_for_status()
    return r.json()["id"], aid


def main():
    users = requests.get(f"{BASE_URL}/api/v1/users/?page=1", headers=ADMIN, timeout=15).json().get("users", [])
    mock = [u for u in users if str(u.get("email", "")).endswith(MOCK_DOMAIN)]
    if not mock:
        raise SystemExit("No @mock.local users found — run seed_mock_data.py first.")

    total = len(mock) * CHATS_PER_USER
    print(f"Generating {total} REAL chats for {len(mock)} users "
          f"({CHATS_PER_USER} each) using models {MODELS} — sequential, this is slow.\n")

    done = 0
    for u in mock:
        email = u["email"]
        token = signin(email)
        uh = {"Authorization": f"Bearer {token}"}
        removed = delete_existing_chats(uh)
        print(f"[{email}] cleared {removed} old chats")

        for i in range(CHATS_PER_USER):
            tag, prompt = random.choice(PROMPTS)
            model = MODELS[(done) % len(MODELS)]  # alternate models across the run
            t0 = time.time()
            try:
                answer, usage = real_complete(model, [
                    {"role": "system", "content": "You are a helpful assistant. Be concise."},
                    {"role": "user", "content": prompt}])
            except requests.HTTPError as e:
                print(f"    ! completion failed on {model}: {e}")
                continue
            if not answer.strip():
                print(f"    ! empty answer from {model}, skipping")
                continue
            chat_id, aid = save_chat(uh, prompt[:48], model, tag, prompt, answer, usage)
            done += 1
            dt = time.time() - t0
            print(f"    + [{done}/{total}] {model} {dt:4.1f}s "
                  f"{usage.get('output_tokens','?')} out-tok  \"{prompt[:40]}\"")

            # ~55% leave feedback, biased positive
            if random.random() < 0.55:
                positive = random.random() < 0.75
                requests.post(f"{BASE_URL}/api/v1/evaluations/feedback", headers=uh, json={
                    "type": "rating",
                    "data": {"rating": 1 if positive else -1, "model_id": model,
                             "reason": "", "comment": "Helpful, thanks!" if positive else "Not quite right.",
                             "tags": []},
                    "meta": {"model_id": model, "chat_id": chat_id, "message_id": aid}}, timeout=15)

            time.sleep(PAUSE_SECONDS)  # gentle on Ollama

    print(f"\nDone: {done} real chats generated. Exporter reflects it within ~30s.")


if __name__ == "__main__":
    main()
