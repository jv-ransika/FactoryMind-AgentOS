from __future__ import annotations

from datetime import datetime, timezone

from agent_os.protocol import ToolManifest
from agent_os.storage import DomainStore


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ToolRegistry:
    def __init__(self, store: DomainStore) -> None:
        self.store = store

    def register(self, manifest: ToolManifest) -> ToolManifest:
        manifest.updated_at = utc_now()
        self.store.save_tool_manifest(manifest)
        return manifest

    def get(self, tool_id: str) -> ToolManifest:
        return self.store.load_tool_manifest(tool_id)

    def list(self) -> list[ToolManifest]:
        return self.store.list_tool_manifests()

    def bind(self, agent_id: str, tool_id: str, allow_write: bool = False) -> None:
        self.store.bind_tool(agent_id=agent_id, tool_id=tool_id, allow_write=allow_write)

    def list_bound(self, agent_id: str) -> list[dict]:
        return self.store.list_bound_tools(agent_id)
