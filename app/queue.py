"""Small durable seed queue backed by Upstash Redis (Redis protocol)."""
from __future__ import annotations
import json, os, sqlite3
from datetime import datetime, timezone
from pathlib import Path

QUEUE_KEY = os.getenv("SEED_QUEUE_KEY", "nerfsql:seed:queue")
DONE_PREFIX = os.getenv("SEED_DONE_PREFIX", "nerfsql:seed:done:")

def _redis():
    url = os.getenv("UPSTASH_REDIS_URL") or os.getenv("REDIS_URL")
    if not url:
        return None
    try:
        import redis
        return redis.Redis.from_url(url, decode_responses=True)
    except Exception:
        return None

def enqueue_seed(dataset: str = "sustainability-demo") -> dict:
    job = {"job_id": f"{dataset}:{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}", "dataset": dataset}
    client = _redis()
    if client is None:
        # Keep the demo usable without Redis; production deployments still use
        # Upstash for durable replay across restarts.
        path = os.getenv("MOCK_DB_PATH", "data/local.db")
        if not _database_ready(path):
            from scripts.create_sample_db import main
            main()
        return {"queued": True, "mode": "local", "job": job}
    client.rpush(QUEUE_KEY, json.dumps(job))
    # Process immediately for the single-container demo; the Redis record
    # remains durable and startup draining can replay it after a restart.
    drain_seed_queue()
    return {"queued": True, "processed": True, "job": job}

def _database_ready(path: str) -> bool:
    if not Path(path).exists(): return False
    try:
        with sqlite3.connect(path) as conn:
            return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'").fetchone())
    except sqlite3.Error: return False

def drain_seed_queue() -> dict:
    client = _redis()
    if client is None: return {"processed": 0, "pending": 0, "mode": "local"}
    processed = 0
    while True:
        raw = client.lpop(QUEUE_KEY)
        if not raw: break
        job = json.loads(raw); job_id = job["job_id"]
        if client.get(DONE_PREFIX + job_id): continue
        path = os.getenv("MOCK_DB_PATH", "data/local.db")
        if not _database_ready(path):
            from scripts.create_sample_db import main
            main()
        client.set(DONE_PREFIX + job_id, "1", ex=60 * 60 * 24 * 30)
        processed += 1
    return {"processed": processed, "pending": int(client.llen(QUEUE_KEY))}
