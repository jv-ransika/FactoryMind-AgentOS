from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class LocalQueueStore:
    def __init__(self, root: Path | str = ".agent-os") -> None:
        self.root = Path(root)
        self.jobs_dir = self.root / "jobs"
        self.pending_dir = self.jobs_dir / "pending"
        self.running_dir = self.jobs_dir / "running"
        self.completed_dir = self.jobs_dir / "completed"
        self.failed_dir = self.jobs_dir / "failed"
        self.dead_dir = self.jobs_dir / "dead_letter"
        self.init()

    def init(self) -> None:
        for path in [self.pending_dir, self.running_dir, self.completed_dir, self.failed_dir, self.dead_dir]:
            path.mkdir(parents=True, exist_ok=True)

    def enqueue(self, job: dict[str, Any]) -> None:
        self._write(self.pending_dir / f"{job['job_id']}.json", job)

    def next_pending(self) -> dict[str, Any] | None:
        pending = sorted(self.pending_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        if not pending:
            return None
        path = pending[0]
        job = self._read(path)
        path.unlink(missing_ok=True)
        return job

    def mark_running(self, job: dict[str, Any]) -> None:
        self._write(self.running_dir / f"{job['job_id']}.json", job)

    def mark_completed(self, job: dict[str, Any]) -> None:
        (self.running_dir / f"{job['job_id']}.json").unlink(missing_ok=True)
        self._write(self.completed_dir / f"{job['job_id']}.json", job)

    def mark_failed(self, job: dict[str, Any], retry: bool) -> None:
        (self.running_dir / f"{job['job_id']}.json").unlink(missing_ok=True)
        if retry:
            self._write(self.failed_dir / f"{job['job_id']}.json", job)
            retry_job = dict(job)
            retry_job["status"] = "pending"
            self._write(self.pending_dir / f"{job['job_id']}.json", retry_job)
        else:
            self._write(self.dead_dir / f"{job['job_id']}.json", job)

    def depth(self) -> int:
        return len(list(self.pending_dir.glob("*.json")))

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _write(path: Path, data: dict[str, Any]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
