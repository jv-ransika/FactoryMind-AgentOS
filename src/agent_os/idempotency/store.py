from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class IdempotencyStore:
    def __init__(self, root: Path | str = ".agent-os") -> None:
        self.root = Path(root)
        self.dir = self.root / "idempotency"

    def init(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> dict[str, Any] | None:
        self.init()
        path = self._path(key)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def record(self, key: str, response_ref: dict[str, Any]) -> None:
        self.init()
        with self._path(key).open("w", encoding="utf-8") as handle:
            json.dump(response_ref, handle, indent=2)
            handle.write("\n")

    def _path(self, key: str) -> Path:
        safe = key.replace("/", "_").replace("\\", "_")
        return self.dir / f"{safe}.json"
