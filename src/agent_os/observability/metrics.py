from __future__ import annotations

import json
from pathlib import Path


class MetricsStore:
    def __init__(self, root: Path | str = ".agent-os") -> None:
        self.root = Path(root)
        self.dir = self.root / "metrics"
        self.path = self.dir / "metrics.json"

    def init(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({})

    def inc(self, key: str, value: int = 1) -> None:
        data = self.read()
        data[key] = int(data.get(key, 0)) + int(value)
        self._write(data)

    def set(self, key: str, value: int | float) -> None:
        data = self.read()
        data[key] = value
        self._write(data)

    def read(self) -> dict:
        self.init()
        with self.path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write(self, data: dict) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
