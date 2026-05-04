from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agent_os.protocol import CostRecord, UsageRecord


def _parse_ts(raw: str):
    return datetime.fromisoformat(raw)


class UsageTracker:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.dir = self.root / "usage"
        self.usage_path = self.dir / "usage.jsonl"
        self.cost_path = self.dir / "costs.jsonl"
        self._init()

    def _init(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.usage_path.touch(exist_ok=True)
        self.cost_path.touch(exist_ok=True)

    def record(self, usage: UsageRecord, cost: CostRecord) -> None:
        self._append(self.usage_path, usage.model_dump(mode="json"))
        self._append(self.cost_path, cost.model_dump(mode="json"))

    def list_usage(
        self,
        agent_id: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[UsageRecord]:
        rows = [UsageRecord.model_validate(item) for item in self._read_jsonl(self.usage_path)]
        rows = [row for row in rows if row.agent_id == agent_id]
        if start:
            rows = [row for row in rows if row.created_at >= start]
        if end:
            rows = [row for row in rows if row.created_at <= end]
        return rows

    def list_costs(
        self,
        agent_id: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[CostRecord]:
        rows = [CostRecord.model_validate(item) for item in self._read_jsonl(self.cost_path)]
        rows = [row for row in rows if row.agent_id == agent_id]
        if start:
            rows = [row for row in rows if row.created_at >= start]
        if end:
            rows = [row for row in rows if row.created_at <= end]
        return rows

    @staticmethod
    def _append(path: Path, payload: dict) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, separators=(",", ":")))
            handle.write("\n")

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict]:
        rows: list[dict] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))
        return rows
