"""Populate an Open WebUI instance with realistic mock activity for demoing the
Prometheus exporter / Grafana dashboard.

It calls Open WebUI's own REST API (no DB access) to create:
  - mock users (emails at @mock.local, so they're easy to find & delete)
  - user groups and knowledge bases (names suffixed "[mock]")
  - chats across several models, each with fabricated per-message token `usage`
    (this is exactly what /api/v1/analytics/* aggregates from), and
  - thumbs up/down feedback with occasional comments.

Nothing here runs model inference — the assistant messages carry pre-computed
`usage` blocks, which is what the analytics endpoints read. All of it is real,
persisted Open WebUI data; remove it with teardown_mock_data.py.

Usage:
    export $(cat .env | xargs)          # needs OPENWEBUI_API_KEY (admin key)
    .venv/bin/python scripts/seed_mock_data.py
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
MOCK_TAG = "[mock]"
PASSWORD = "mockpass123"

random.seed(42)

# Registered models carry rich /api/models metadata (size, context, provider),
# so the catalog/provider panels stay meaningful. Weights bias message volume.
MODELS = [
    {"id": "qwen3.5:2b", "weight": 5, "pos_bias": 0.90},
    {"id": "agent-model", "weight": 3, "pos_bias": 0.75},
    {"id": "llama3.2:1b", "weight": 2, "pos_bias": 0.55},
]

USERS = [
    ("Alice Nguyen", "alice"), ("Bob Martinez", "bob"), ("Carla Rossi", "carla"),
    ("David Okafor", "david"), ("Elena Petrova", "elena"), ("Farid Hassan", "farid"),
    ("Grace Kim", "grace"), ("Hiro Tanaka", "hiro"),
]

GROUPS = [
    ("Engineering", "Backend and platform engineers"),
    ("Research", "ML research and evaluation"),
    ("Product", "PM and design"),
    ("Support", "Customer support team"),
]

KNOWLEDGE_BASES = [
    ("Company Handbook", "Internal policies and onboarding"),
    ("API Documentation", "Service and SDK references"),
    ("Customer FAQ", "Common support questions"),
    ("Research Papers", "Curated ML papers"),
    ("Product Specs", "Feature specifications"),
]

# (topic tag, [ (prompt, reply) ... ]) — reply text length feeds the message-length panels.
TOPICS = {
    "coding": [
        ("Write a Python function to debounce calls.",
         "Here's a debounce decorator using threading.Timer that resets on each call and only fires after the quiet period elapses. It's thread-safe and cancels any pending invocation before scheduling a new one."),
        ("How do I fix a circular import in Python?",
         "Circular imports usually mean two modules depend on each other at import time. Move the shared piece into a third module, defer the import inside the function that needs it, or restructure so the dependency flows one way."),
    ],
    "research": [
        ("Explain retrieval augmented generation.",
         "RAG pairs a retriever with a generator: the retriever pulls relevant passages from a knowledge store, and those passages are concatenated into the prompt so the model can ground its answer in external, up-to-date facts instead of relying solely on parametric memory."),
        ("What's the difference between LoRA and full fine-tuning?",
         "Full fine-tuning updates every weight; LoRA freezes the base model and learns small low-rank adapter matrices, cutting memory and storage dramatically while keeping quality close for most downstream tasks."),
    ],
    "writing": [
        ("Draft a friendly out-of-office reply.",
         "Thanks for your message! I'm currently out of office and will be back on Monday. For anything urgent, please reach out to my colleague. Otherwise I'll respond as soon as I return."),
        ("Rewrite this sentence to be more concise.",
         "Here's a tighter version that keeps the meaning while dropping the filler words and passive voice."),
    ],
    "data-analysis": [
        ("How do I read a large CSV efficiently in pandas?",
         "Use chunksize to stream the file, pass dtype to avoid inference overhead, and select only the columns you need with usecols. For very large data, consider polars or DuckDB which handle out-of-core queries far better."),
        ("What's a good metric for imbalanced classification?",
         "Accuracy is misleading on imbalanced data. Prefer precision/recall, F1, or the area under the precision-recall curve, and look at the confusion matrix to understand the error trade-offs directly."),
    ],
    "support": [
        ("How do I reset my password?",
         "Go to Settings, choose Account, and select Reset Password. You'll get an email with a secure link that stays valid for one hour."),
        ("The dashboard won't load, what should I check?",
         "First confirm the service is running and reachable, then clear the cache and check the browser console for errors. If it persists, capture the network tab and share the failing request."),
    ],
}
COMMENTS_POS = ["Very clear!", "Exactly what I needed.", "Great explanation.", "Super helpful, thanks."]
COMMENTS_NEG = ["Missed the point.", "Too vague.", "Incorrect for my case.", "Needs more detail."]


def post(path, headers, json):
    r = requests.post(f"{BASE_URL}{path}", headers=headers, json=json, timeout=15)
    r.raise_for_status()
    return r.json()


def make_usage():
    inp = random.randint(120, 2200)
    out = random.randint(60, 1600)
    dur = random.randint(1, 28) * 1_000_000_000  # ns
    return {
        "input_tokens": inp, "output_tokens": out, "total_tokens": inp + out,
        "prompt_tokens": inp, "completion_tokens": out,
        "response_token/s": round(out / (dur / 1e9), 2), "total_duration": dur,
        "prompt_eval_count": inp, "eval_count": out,
    }


def build_chat(title, model_id, turns, when):
    """turns: list of (user_text, assistant_text). Returns a chat object."""
    messages = {}
    order = []
    prev_id = None
    ts = when
    for user_text, asst_text in turns:
        uid = str(uuid.uuid4())
        aid = str(uuid.uuid4())
        messages[uid] = {"id": uid, "parentId": prev_id, "childrenIds": [aid], "role": "user",
                         "content": user_text, "timestamp": ts, "models": [model_id]}
        if prev_id:
            messages[prev_id]["childrenIds"] = [uid]
        messages[aid] = {"id": aid, "parentId": uid, "childrenIds": [], "role": "assistant",
                         "content": asst_text, "done": True, "model": model_id, "modelName": model_id,
                         "timestamp": ts + random.randint(1, 20), "usage": make_usage()}
        order += [uid, aid]
        prev_id = aid
        ts += random.randint(30, 600)
    last = order[-1]
    return {"id": "", "title": title, "models": [model_id],
            "history": {"currentId": last, "messages": messages},
            "messages": [messages[m] for m in order], "tags": [], "timestamp": when, "files": []}


def weighted_model():
    pool = [m for m in MODELS for _ in range(m["weight"])]
    return random.choice(pool)


def main():
    print(f"Seeding mock data into {BASE_URL} ...")
    now = int(time.time())

    # 1) Users -------------------------------------------------------------
    users = []  # (name, email, id, token)
    for name, handle in USERS:
        email = f"{handle}{MOCK_DOMAIN}"
        try:
            u = post("/api/v1/auths/add", ADMIN,
                     {"name": name, "email": email, "password": PASSWORD, "role": "user"})
            users.append((name, email, u["id"], u["token"]))
            print(f"  user  + {name} <{email}>")
        except requests.HTTPError as e:
            # Likely already exists from a previous run; sign in to reuse.
            r = requests.post(f"{BASE_URL}/api/v1/auths/signin",
                              json={"email": email, "password": PASSWORD}, timeout=15)
            if r.ok:
                u = r.json()
                users.append((name, email, u["id"], u["token"]))
                print(f"  user  = {name} <{email}> (existing)")
            else:
                print(f"  user  ! {email} failed: {e}")

    # 2) Groups (distribute users round-robin) -----------------------------
    for i, (gname, gdesc) in enumerate(GROUPS):
        try:
            g = post("/api/v1/groups/create", ADMIN, {"name": f"{gname} {MOCK_TAG}", "description": gdesc})
            members = [u[2] for j, u in enumerate(users) if j % len(GROUPS) == i]
            post(f"/api/v1/groups/id/{g['id']}/update", ADMIN,
                 {"name": f"{gname} {MOCK_TAG}", "description": gdesc, "user_ids": members})
            print(f"  group + {gname} ({len(members)} members)")
        except requests.HTTPError as e:
            print(f"  group ! {gname}: {e}")

    # 3) Knowledge bases ---------------------------------------------------
    for kname, kdesc in KNOWLEDGE_BASES:
        try:
            post("/api/v1/knowledge/create", ADMIN,
                 {"name": f"{kname} {MOCK_TAG}", "description": kdesc, "data": {}, "access_control": {}})
            print(f"  kb    + {kname}")
        except requests.HTTPError as e:
            print(f"  kb    ! {kname}: {e}")

    # 4) Chats + feedback per user ----------------------------------------
    topic_names = list(TOPICS)
    n_chats = n_msgs = n_fb = 0
    for name, email, uid, token in users:
        uh = {"Authorization": f"Bearer {token}"}
        for _ in range(random.randint(3, 8)):
            model = weighted_model()
            topic = random.choice(topic_names)
            n_turns = random.randint(1, 3)
            turns = [random.choice(TOPICS[topic]) for _ in range(n_turns)]
            title = turns[0][0][:48]
            when = now - random.randint(0, 14 * 86400)
            chat_obj = build_chat(title, model["id"], turns, when)
            chat_obj["tags"] = [topic]
            try:
                created = post("/api/v1/chats/new", uh, {"chat": chat_obj})
            except requests.HTTPError as e:
                print(f"  chat  ! {email}: {e}")
                continue
            chat_id = created["id"]
            n_chats += 1
            n_msgs += n_turns

            # Feedback on ~60% of chats, biased by the model's quality.
            if random.random() < 0.6:
                last_aid = chat_obj["history"]["currentId"]
                positive = random.random() < model["pos_bias"]
                rating = 1 if positive else -1
                comment = ""
                if random.random() < 0.4:
                    comment = random.choice(COMMENTS_POS if positive else COMMENTS_NEG)
                try:
                    post("/api/v1/evaluations/feedback", uh, {
                        "type": "rating",
                        "data": {"rating": rating, "model_id": model["id"], "reason": "",
                                 "comment": comment, "tags": []},
                        "meta": {"model_id": model["id"], "chat_id": chat_id, "message_id": last_aid},
                    })
                    n_fb += 1
                except requests.HTTPError as e:
                    print(f"  fb    ! {email}: {e}")

    print(f"\nDone: {len(users)} users, {len(GROUPS)} groups, {len(KNOWLEDGE_BASES)} KBs, "
          f"{n_chats} chats (~{n_msgs} turns), {n_fb} feedback.")
    print("The exporter will reflect this within one poll interval (~30s).")


if __name__ == "__main__":
    main()
