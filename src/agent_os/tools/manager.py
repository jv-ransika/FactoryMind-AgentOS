from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agent_os.observability import MetricsStore
from agent_os.protocol import AuthContext, ToolAuditEvent, ToolCallRequest, ToolCallResult, ToolCallStatus, ToolManifest, ToolScope
from agent_os.storage import DomainStore
from agent_os.tools.adapter import CompositeToolAdapter, McpToolAdapter, MockToolAdapter, ToolAdapter
from agent_os.tools.gateway import ToolGateway
from agent_os.tools.mcp import McpServerRegistry
from agent_os.tools.registry import ToolRegistry


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ToolManager:
    def __init__(self, store: DomainStore, adapter: ToolAdapter | None = None) -> None:
        self.store = store
        self.metrics = MetricsStore(root=store.root)
        self.registry = ToolRegistry(store=store)
        self.mcp = McpServerRegistry(root=store.root)
        self.adapter = adapter or CompositeToolAdapter(mock=MockToolAdapter(), mcp=McpToolAdapter(self.mcp))
        self.gateway = ToolGateway(store=store, registry=self.registry, adapter=self.adapter)

    def register(self, manifest: ToolManifest) -> ToolManifest:
        return self.registry.register(manifest)

    def register_from_fields(
        self,
        name: str,
        scope: ToolScope = ToolScope.READ,
        description: str = "",
        input_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        timeout_ms: int = 2000,
        max_input_bytes: int = 8192,
        max_output_bytes: int = 32768,
        enabled: bool = True,
        version: str = "1.0.0",
    ) -> ToolManifest:
        manifest = ToolManifest(
            name=name,
            scope=scope,
            description=description,
            input_schema=input_schema or {},
            output_schema=output_schema or {},
            timeout_ms=timeout_ms,
            max_input_bytes=max_input_bytes,
            max_output_bytes=max_output_bytes,
            enabled=enabled,
            version=version,
        )
        return self.register(manifest)

    def register_mcp_tool(
        self,
        name: str,
        mcp_server: str,
        mcp_tool_name: str,
        scope: ToolScope = ToolScope.READ,
        description: str = "",
        input_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        timeout_ms: int = 2000,
        max_input_bytes: int = 8192,
        max_output_bytes: int = 32768,
        enabled: bool = True,
        version: str = "1.0.0",
    ) -> ToolManifest:
        self.mcp.get(mcp_server)
        manifest = ToolManifest(
            name=name,
            scope=scope,
            description=description,
            input_schema=input_schema or {},
            output_schema=output_schema or {},
            timeout_ms=timeout_ms,
            max_input_bytes=max_input_bytes,
            max_output_bytes=max_output_bytes,
            enabled=enabled,
            version=version,
            mcp_server=mcp_server,
            mcp_tool_name=mcp_tool_name,
        )
        return self.register(manifest)

    def bind(self, agent_id: str, tool_id: str, allow_write: bool = False) -> None:
        self.registry.bind(agent_id=agent_id, tool_id=tool_id, allow_write=allow_write)

    def list(self, agent_id: str | None = None) -> list[ToolManifest]:
        manifests = self.registry.list()
        if agent_id is None:
            return manifests
        bound = self.registry.list_bound(agent_id)
        bound_ids = {str(entry.get("tool_id")) for entry in bound}
        return [manifest for manifest in manifests if manifest.tool_id in bound_ids]

    def list_bindings(self, agent_id: str) -> list[dict]:
        return self.registry.list_bound(agent_id)

    def call(
        self,
        agent_id: str,
        session_id: str | None,
        tool_id: str,
        args: dict[str, Any],
        auth: AuthContext | None = None,
    ) -> tuple[ToolCallResult, ToolAuditEvent]:
        request = ToolCallRequest(
            session_id=session_id,
            agent_id=agent_id,
            tool_id=tool_id,
            arguments=args,
        )
        result, audit = self.gateway.call(request=request, auth=auth)
        if audit.mcp is not None:
            self.metrics.inc("mcp_calls_total")
            self.metrics.inc(f"mcp_calls_{result.status.value}")
            if result.status in {ToolCallStatus.ERROR, ToolCallStatus.TIMEOUT}:
                self.metrics.inc("mcp_calls_unhealthy")
        return result, audit

    def audit(self, agent_id: str, session_id: str | None = None) -> list[ToolAuditEvent]:
        return self.store.list_tool_audits(agent_id=agent_id, session_id=session_id)
