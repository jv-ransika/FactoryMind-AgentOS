from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any
import httpx

from agent_os.protocol import (
    EventType,
    SessionEvent,
    ToolAuditEvent,
    AuthContext,
    ToolCallRequest,
    ToolCallResult,
    ToolCallStatus,
    ToolManifest,
    ToolScope,
)
from agent_os.storage import DomainStore
from agent_os.tools.adapter import ToolAdapter
from agent_os.tools.registry import ToolRegistry


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


class ToolGateway:
    def __init__(self, store: DomainStore, registry: ToolRegistry, adapter: ToolAdapter) -> None:
        self.store = store
        self.registry = registry
        self.adapter = adapter

    def call(self, request: ToolCallRequest, auth: AuthContext | None = None) -> tuple[ToolCallResult, ToolAuditEvent]:
        started = time.perf_counter()
        manifest = self.registry.get(request.tool_id)
        request_hash = self._request_hash(request)

        deny_reason = self._precheck_denied(manifest, request.agent_id, request.tool_id)
        if deny_reason is not None:
            return self._finalize(
                request=request,
                status=ToolCallStatus.DENIED,
                error_code=deny_reason,
                output=None,
                started=started,
                request_hash=request_hash,
                auth=auth,
            )

        invalid_reason = self._validate_request(manifest, request.arguments)
        if invalid_reason is not None:
            return self._finalize(
                request=request,
                status=ToolCallStatus.INVALID,
                error_code=invalid_reason,
                output=None,
                started=started,
                request_hash=request_hash,
                auth=auth,
            )

        try:
            raw_output = self.adapter.execute(
                manifest=manifest,
                arguments=request.arguments,
                timeout_ms=manifest.timeout_ms,
            )
        except (TimeoutError, httpx.TimeoutException):
            return self._finalize(
                request=request,
                status=ToolCallStatus.TIMEOUT,
                error_code="timeout",
                output=None,
                started=started,
                request_hash=request_hash,
                auth=auth,
            )
        except Exception:
            return self._finalize(
                request=request,
                status=ToolCallStatus.ERROR,
                error_code="execution_error",
                output=None,
                started=started,
                request_hash=request_hash,
                auth=auth,
            )

        sanitized, applied = self._sanitize_output(raw_output)
        raw_size = len(json.dumps(raw_output, separators=(",", ":")).encode("utf-8"))
        if raw_size > manifest.max_output_bytes:
            return self._finalize(
                request=request,
                status=ToolCallStatus.INVALID,
                error_code="output_too_large",
                output=None,
                started=started,
                request_hash=request_hash,
                auth=auth,
            )

        return self._finalize(
            request=request,
            status=ToolCallStatus.SUCCESS,
            error_code=None,
            output=raw_output,
            sanitized_output=sanitized,
            sanitization_applied=applied,
            started=started,
            request_hash=request_hash,
            auth=auth,
        )

    def _precheck_denied(self, manifest: ToolManifest, agent_id: str, tool_id: str) -> str | None:
        if not manifest.enabled:
            return "tool_disabled"
        bindings = self.registry.list_bound(agent_id)
        binding = next((entry for entry in bindings if str(entry.get("tool_id")) == tool_id), None)
        if binding is None:
            return "tool_not_bound"
        if manifest.scope == ToolScope.WRITE and not bool(binding.get("allow_write", False)):
            return "write_scope_denied"
        return None

    def _validate_request(self, manifest: ToolManifest, arguments: dict[str, Any]) -> str | None:
        raw = json.dumps(arguments, separators=(",", ":")).encode("utf-8")
        if len(raw) > manifest.max_input_bytes:
            return "input_too_large"
        schema = manifest.input_schema or {}
        schema_type = schema.get("type")
        if schema_type and schema_type != "object":
            return "schema_invalid"
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        additional = bool(schema.get("additionalProperties", False))
        for field in required:
            if field not in arguments:
                return f"missing_required:{field}"
        for key, value in arguments.items():
            if key.startswith("_"):
                continue
            if key not in properties and not additional:
                return f"unexpected_field:{key}"
            declared = properties.get(key, {})
            expected_type = declared.get("type")
            if expected_type and expected_type in TYPE_MAP and not isinstance(value, TYPE_MAP[expected_type]):
                return f"invalid_type:{key}:{expected_type}"
        return None

    def _sanitize_output(self, payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        text_markers = [
            "ignore previous instructions",
            "system prompt",
            "developer message",
            "reveal secrets",
        ]
        applied = False

        def sanitize(value: Any) -> Any:
            nonlocal applied
            if isinstance(value, str):
                lowered = value.lower()
                if any(marker in lowered for marker in text_markers):
                    applied = True
                    return "[SANITIZED_TOOL_OUTPUT]"
                return value
            if isinstance(value, list):
                return [sanitize(item) for item in value]
            if isinstance(value, dict):
                return {str(key): sanitize(item) for key, item in value.items()}
            return value

        sanitized = sanitize(payload)
        return sanitized if isinstance(sanitized, dict) else {"value": sanitized}, applied

    def _finalize(
        self,
        request: ToolCallRequest,
        status: ToolCallStatus,
        error_code: str | None,
        output: dict[str, Any] | None,
        started: float,
        request_hash: str,
        auth: AuthContext | None,
        sanitized_output: dict[str, Any] | None = None,
        sanitization_applied: bool = False,
    ) -> tuple[ToolCallResult, ToolAuditEvent]:
        duration_ms = int((time.perf_counter() - started) * 1000)
        result = ToolCallResult(
            request_id=request.request_id,
            status=status,
            output=output,
            duration_ms=duration_ms,
            error_code=error_code,
            error_message=error_code,
            sanitized_output=sanitized_output,
        )
        evidence = {
            "status": status.value,
            "tool_id": request.tool_id,
            "result_keys": sorted(list((sanitized_output or output or {}).keys()))[:10],
        }
        mcp_meta = None
        if manifest := self.registry.get(request.tool_id):
            if manifest.mcp_server and manifest.mcp_tool_name:
                mcp_meta = {
                    "server": manifest.mcp_server,
                    "tool": manifest.mcp_tool_name,
                    "transport": "http",
                }
        prev_hash = self._prev_hash(request.agent_id)
        audit = ToolAuditEvent(
            session_id=request.session_id,
            agent_id=request.agent_id,
            tenant_id=auth.tenant_id if auth else "default",
            tool_id=request.tool_id,
            request_hash=request_hash,
            status=status,
            duration_ms=duration_ms,
            sanitization_applied=sanitization_applied,
            error_code=error_code,
            summary_evidence=evidence,
            mcp=mcp_meta,
            actor_sub=auth.sub if auth else None,
            actor_roles=[] if auth is None else list(auth.roles),
            auth_method="jwt_bearer" if auth else "none",
            prev_hash=prev_hash,
        )
        audit.entry_hash = self._entry_hash(audit)
        self.store.save_tool_audit(audit)

        if request.session_id:
            self.store.append_event(
                SessionEvent(
                    session_id=request.session_id,
                    agent_id=request.agent_id,
                    type=EventType.TOOL_CALL,
                    payload={
                        "audit_id": audit.audit_id,
                        "tool_id": request.tool_id,
                        "status": status.value,
                        "summary_evidence": evidence,
                    },
                    tenant_id=auth.tenant_id if auth else "default",
                )
            )
        return result, audit

    def _prev_hash(self, agent_id: str) -> str | None:
        audits = self.store.list_tool_audits(agent_id=agent_id)
        if not audits:
            return None
        audits = sorted(audits, key=lambda item: item.created_at)
        return audits[-1].entry_hash

    @staticmethod
    def _entry_hash(audit: ToolAuditEvent) -> str:
        payload = json.dumps(
            {
                "audit_id": audit.audit_id,
                "prev_hash": audit.prev_hash,
                "agent_id": audit.agent_id,
                "tenant_id": audit.tenant_id,
                "tool_id": audit.tool_id,
                "status": audit.status.value,
                "request_hash": audit.request_hash,
                "created_at": audit.created_at.isoformat(),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _request_hash(request: ToolCallRequest) -> str:
        payload = json.dumps(
            {
                "agent_id": request.agent_id,
                "tool_id": request.tool_id,
                "arguments": request.arguments,
                "session_id": request.session_id,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
