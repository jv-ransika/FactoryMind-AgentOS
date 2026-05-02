from __future__ import annotations

import json
import os
from pathlib import Path

from agent_os.protocol import McpServerConfig


class McpServerRegistry:
    def __init__(self, root: Path | str = ".agent-os") -> None:
        self.root = Path(root)
        self.dir = self.root / "mcp"
        self.path = self.dir / "servers.json"

    def init(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    def add(self, config: McpServerConfig) -> McpServerConfig:
        self.init()
        current = self.list()
        kept = [item for item in current if item.name != config.name]
        kept.append(config)
        self._write([item.model_dump(mode="json") for item in kept])
        return config

    def list(self) -> list[McpServerConfig]:
        self.init()
        with self.path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        items = [McpServerConfig.model_validate(item) for item in raw]
        return [self._apply_env_override(item) for item in items]

    def get(self, name: str) -> McpServerConfig:
        for item in self.list():
            if item.name == name:
                return item
        raise FileNotFoundError(f"MCP server not found: {name}")

    def remove(self, name: str) -> bool:
        self.init()
        items = self.list()
        kept = [item for item in items if item.name != name]
        self._write([item.model_dump(mode="json") for item in kept])
        return len(kept) != len(items)

    @staticmethod
    def _apply_env_override(item: McpServerConfig) -> McpServerConfig:
        endpoint_env = os.getenv(f"AGENT_OS_MCP_{item.name.upper()}_ENDPOINT")
        if endpoint_env:
            item.endpoint = endpoint_env
        return item

    def _write(self, payload: list[dict]) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
