from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from agent_os.idempotency import IdempotencyStore
from agent_os.observability import MetricsStore
from agent_os.storage import IdempotencyBackend, LocalQueueStore, QueueStore


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JobManager:
    def __init__(
        self,
        root: Path | str,
        agent_os: Any,
        max_attempts: int = 3,
        queue_store: QueueStore | None = None,
        idempotency: IdempotencyBackend | None = None,
    ) -> None:
        self.root = Path(root)
        self.agent_os = agent_os
        self.max_attempts = max_attempts
        self.queue = queue_store or LocalQueueStore(root=self.root)
        self.metrics = MetricsStore(root=self.root)
        self.idempotency = idempotency or IdempotencyStore(root=self.root)
        self.init()

    def init(self) -> None:
        self.queue.init()

    def enqueue(self, type: str, payload: dict[str, Any], idempotency_key: str | None = None) -> dict[str, Any]:
        if idempotency_key:
            cached = self.idempotency.get(idempotency_key)
            if cached is not None:
                cached["idempotency_reused"] = True
                return cached

        job = {
            "job_id": f"job_{uuid4().hex}",
            "type": type,
            "payload": payload,
            "attempt": 0,
            "status": "pending",
            "available_at": utc_now().isoformat(),
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
            "last_error": None,
        }
        self.queue.enqueue(job)
        self.metrics.inc("jobs_enqueued")
        response = {"operation_id": job["job_id"], "status": "queued", "idempotency_reused": False}
        if idempotency_key:
            self.idempotency.record(idempotency_key, response)
        return response

    def process_next(self) -> dict[str, Any] | None:
        job = self.queue.next_pending()
        if job is None:
            self.metrics.set("queue_depth", 0)
            return None
        now = utc_now()
        available_at = datetime.fromisoformat(job["available_at"])
        if available_at > now:
            self.queue.enqueue(job)
            return None

        job["status"] = "running"
        job["updated_at"] = utc_now().isoformat()
        self.queue.mark_running(job)
        self.metrics.inc("jobs_running")

        started = time.perf_counter()
        try:
            result = self._execute_job(job)
            duration_ms = int((time.perf_counter() - started) * 1000)
            job["status"] = "completed"
            job["result"] = result
            job["duration_ms"] = duration_ms
            job["updated_at"] = utc_now().isoformat()
            self.queue.mark_completed(job)
            self.metrics.inc("jobs_completed")
            self.metrics.set("jobs_queue_lag", self.queue.depth())
            self.metrics.set("queue_depth", self.queue.depth())
            return job
        except Exception as exc:
            job["attempt"] = int(job["attempt"]) + 1
            job["last_error"] = str(exc)
            job["updated_at"] = utc_now().isoformat()
            if job["attempt"] >= self.max_attempts:
                job["status"] = "dead_letter"
                self.queue.mark_failed(job, retry=False)
                self.metrics.inc("jobs_dead_letter")
                self.metrics.inc("sli_dead_letter")
            else:
                job["status"] = "failed"
                retry = dict(job)
                retry["available_at"] = utc_now().isoformat()
                self.queue.mark_failed(retry, retry=True)
                self.metrics.inc("jobs_retried")
                self.metrics.inc("sli_job_retry")
            self.metrics.inc("jobs_failed")
            self.metrics.inc("sli_job_failure")
            self.metrics.set("queue_depth", self.queue.depth())
            return job

    def run_worker(self, once: bool = False) -> int:
        processed = 0
        while True:
            job = self.process_next()
            if job is None:
                if once:
                    break
                time.sleep(0.1)
                continue
            processed += 1
            if once:
                break
        return processed

    def _execute_job(self, job: dict[str, Any]) -> dict[str, Any]:
        payload = job["payload"]
        type = job["type"]
        if type == "learn_run":
            run = self.agent_os.learning.run(
                agent_id=payload["agent_id"],
                session_ids=payload.get("session_ids"),
                window_size=int(payload.get("window_size", 50)),
            )
            return run.model_dump(mode="json")
        if type == "flame_extract_session":
            result = self.agent_os.flame.ingest_accepted_session(
                agent_id=payload["agent_id"],
                session_id=payload["session_id"],
            )
            return result
        if type == "flame_reflect_batch":
            runs = self.agent_os.flame.trigger(
                agent_id=payload.get("agent_id"),
                force=bool(payload.get("force", False)),
            )
            return {"runs": [run.model_dump(mode="json") for run in runs]}
        if type == "flame_trigger_scan":
            runs = self.agent_os.flame.trigger(
                agent_id=payload.get("agent_id"),
                force=False,
            )
            return {"runs": [run.model_dump(mode="json") for run in runs]}
        if type == "candidate_evaluate":
            report = self.agent_os.learning.evaluate(candidate_id=payload["candidate_id"])
            return report.model_dump(mode="json")
        if type == "candidate_promote":
            candidate = self.agent_os.learning.promote(candidate_id=payload["candidate_id"])
            return candidate.model_dump(mode="json")
        if type == "candidate_rollback":
            record = self.agent_os.learning.rollback(
                candidate_id=payload["candidate_id"],
                reason=payload["reason"],
            )
            return record.model_dump(mode="json")
        if type == "tool_call_async":
            result, audit = self.agent_os.tools.call(
                agent_id=payload["agent_id"],
                session_id=payload.get("session_id"),
                tool_id=payload["tool_id"],
                args=payload.get("args", {}),
            )
            return {"result": result.model_dump(mode="json"), "audit": audit.model_dump(mode="json")}
        raise ValueError(f"Unknown job type: {type}")
