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
# APPEND=1 keeps each user's existing chats and adds on top, instead of wiping
# them first — use it to grow volume without re-running inference you already paid for.
APPEND = os.environ.get("APPEND", "0") == "1"
# Up to this many user->assistant turns per chat (each turn is another real
# completion, with the running conversation fed back to the model).
MAX_TURNS = int(os.environ.get("MAX_TURNS", "3"))
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

# Generic follow-ups, appended as real second/third turns so the model answers
# them with the earlier exchange in context.
FOLLOWUPS = [
    "Can you show a short code example?",
    "Why is that the case?",
    "What are the main trade-offs?",
    "Can you summarise that in one sentence?",
    "What's a common mistake people make here?",
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


def save_chat(user_headers, title, model, tag, turns):
    """turns: list of (prompt, answer, usage) — one entry per real exchange."""
    now = int(time.time())
    messages = {}
    order = []
    prev = None
    for i, (prompt, answer, usage) in enumerate(turns):
        uid, aid = str(uuid.uuid4()), str(uuid.uuid4())
        messages[uid] = {"id": uid, "parentId": prev, "childrenIds": [aid], "role": "user",
                         "content": prompt, "timestamp": now + i * 60, "models": [model]}
        if prev:
            messages[prev]["childrenIds"] = [uid]
        messages[aid] = {"id": aid, "parentId": uid, "childrenIds": [], "role": "assistant",
                         "content": answer, "done": True, "model": model, "modelName": model,
                         "timestamp": now + i * 60 + 1, "usage": usage}
        order += [uid, aid]
        prev = aid
    chat_obj = {"id": "", "title": title, "models": [model],
                "history": {"currentId": prev, "messages": messages},
                "messages": [messages[m] for m in order], "tags": [tag],
                "timestamp": now, "files": []}
    r = requests.post(f"{BASE_URL}/api/v1/chats/new", headers=user_headers, json={"chat": chat_obj}, timeout=15)
    r.raise_for_status()
    return r.json()["id"], prev


def main():
    users = requests.get(f"{BASE_URL}/api/v1/users/?page=1", headers=ADMIN, timeout=15).json().get("users", [])
    mock = [u for u in users if str(u.get("email", "")).endswith(MOCK_DOMAIN)]
    if not mock:
        raise SystemExit("No @mock.local users found — run seed_mock_data.py first.")

    total = len(mock) * CHATS_PER_USER
    print(f"Generating {total} REAL chats for {len(mock)} users ({CHATS_PER_USER} each, "
          f"up to {MAX_TURNS} turns) using models {MODELS}.\n"
          f"Mode: {'APPEND (keeping existing chats)' if APPEND else 'REPLACE (clearing existing chats)'}. "
          f"Sequential — this is slow.\n", flush=True)

    done = 0
    for u in mock:
        email = u["email"]
        token = signin(email)
        uh = {"Authorization": f"Bearer {token}"}
        if APPEND:
            print(f"[{email}] appending", flush=True)
        else:
            print(f"[{email}] cleared {delete_existing_chats(uh)} old chats", flush=True)

        for i in range(CHATS_PER_USER):
            tag, prompt = random.choice(PROMPTS)
            model = MODELS[done % len(MODELS)]  # alternate models across the run
            n_turns = random.randint(1, MAX_TURNS)

            # Drive a genuine multi-turn conversation: each follow-up is answered
            # with the running exchange in context.
            convo = [{"role": "system", "content": "You are a helpful assistant. Be concise."}]
            turns = []
            t0 = time.time()
            for t in range(n_turns):
                q = prompt if t == 0 else random.choice(FOLLOWUPS)
                convo.append({"role": "user", "content": q})
                try:
                    answer, usage = real_complete(model, convo)
                except requests.HTTPError as e:
                    print(f"    ! completion failed on {model}: {e}", flush=True)
                    break
                if not answer.strip():
                    print(f"    ! empty answer from {model}, ending chat early", flush=True)
                    break
                convo.append({"role": "assistant", "content": answer})
                turns.append((q, answer, usage))
                time.sleep(PAUSE_SECONDS)  # gentle on Ollama between turns

            if not turns:
                continue
            chat_id, aid = save_chat(uh, prompt[:48], model, tag, turns)
            done += 1
            dt = time.time() - t0
            tok = sum(t[2].get("output_tokens", 0) for t in turns)
            print(f"    + [{done}/{total}] {model} {len(turns)}-turn {dt:5.1f}s "
                  f"{tok} out-tok  \"{prompt[:38]}\"", flush=True)

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
