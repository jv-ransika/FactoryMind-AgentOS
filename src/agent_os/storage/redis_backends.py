from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from redis import Redis


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RedisIdempotencyStore:
    def __init__(self, redis_url: str, ttl_seconds: int = 24 * 3600) -> None:
        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self.ttl_seconds = ttl_seconds

    def get(self, key: str) -> dict[str, Any] | None:
        raw = self.redis.get(f"idem:{key}")
        if raw is None:
            return None
        return json.loads(raw)

    def record(self, key: str, response_ref: dict[str, Any]) -> None:
        self.redis.setex(f"idem:{key}", self.ttl_seconds, json.dumps(response_ref, separators=(",", ":")))


class RedisQueueStore:
    def __init__(self, redis_url: str) -> None:
        self.redis = Redis.from_url(redis_url, decode_responses=True)

    def init(self) -> None:
        return None

    def enqueue(self, job: dict[str, Any]) -> None:
        self.redis.hset(f"job:{job['job_id']}", mapping={"payload": json.dumps(job, separators=(",", ":"))})
        self.redis.rpush("jobs:pending", job["job_id"])

    def next_pending(self) -> dict[str, Any] | None:
        job_id = self.redis.lpop("jobs:pending")
        if not job_id:
            return None
        raw = self.redis.hget(f"job:{job_id}", "payload")
        if raw is None:
            return None
        return json.loads(raw)

    def mark_running(self, job: dict[str, Any]) -> None:
        self.redis.hset(f"job:{job['job_id']}", mapping={"payload": json.dumps(job, separators=(",", ":"))})
        self.redis.rpush("jobs:running", job["job_id"])

    def mark_completed(self, job: dict[str, Any]) -> None:
        self.redis.hset(f"job:{job['job_id']}", mapping={"payload": json.dumps(job, separators=(",", ":"))})
        self.redis.lrem("jobs:running", 0, job["job_id"])
        self.redis.rpush("jobs:completed", job["job_id"])

    def mark_failed(self, job: dict[str, Any], retry: bool) -> None:
        self.redis.hset(f"job:{job['job_id']}", mapping={"payload": json.dumps(job, separators=(",", ":"))})
        self.redis.lrem("jobs:running", 0, job["job_id"])
        if retry:
            self.redis.rpush("jobs:failed", job["job_id"])
            self.redis.rpush("jobs:pending", job["job_id"])
        else:
            self.redis.rpush("jobs:dead_letter", job["job_id"])

    def depth(self) -> int:
        return int(self.redis.llen("jobs:pending"))
