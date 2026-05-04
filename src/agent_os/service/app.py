from __future__ import annotations

import time
from datetime import datetime
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from agent_os import AgentOS, AgentTier, AuthConfig, AuthContext, FlamePoolState, PromotionPolicy, Role, ToolManifest
from agent_os.observability import init_otel
from agent_os.ops.deps import check_dependencies, environment_mode
from agent_os.secrets import redact
from agent_os.service.auth import build_auth_dependency, load_auth_config
from agent_os.service.rbac import require_permission


def _op(status: str, payload: dict, reused: bool = False, operation_id: str | None = None) -> dict:
    return {
        "operation_id": operation_id or f"op_{uuid4().hex}",
        "status": status,
        "idempotency_reused": reused,
        "data": payload,
    }


def create_service_app(agent_os: AgentOS, auth_config: AuthConfig | None = None) -> FastAPI:
    app = FastAPI(title="FactoryMind AgentOS Service", version="1.3.0")
    app.state.agent_os = agent_os
    app.state.worker_healthy = True
    app.state.env_mode = environment_mode()
    app.state.otel = init_otel(service_name="factorymind-agentos-service")
    cfg = auth_config or load_auth_config(root=agent_os.root, secrets=agent_os.secrets)
    auth_any = build_auth_dependency(cfg)
    auth_ops = build_auth_dependency(cfg, {Role.OPS, Role.ADMIN})

    def _idempotent(key: str | None):
        if not key:
            return None
        return agent_os.idempotency.get(key)

    def _record(key: str | None, response: dict):
        if key:
            agent_os.idempotency.record(key, response)

    def _agent_in_tenant(agent_id: str, ctx: AuthContext):
        agent = agent_os.get_agent(agent_id)
        if agent.tenant_id != ctx.tenant_id:
            raise HTTPException(status_code=403, detail="cross_tenant_agent_denied")
        return agent

    def _session_in_tenant(session_id: str, ctx: AuthContext):
        events = agent_os.sessions.events(session_id)
        if not events:
            raise HTTPException(status_code=404, detail="session_not_found")
        if events[0].tenant_id != ctx.tenant_id:
            raise HTTPException(status_code=403, detail="cross_tenant_session_denied")
        return events

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.post("/agents")
    def agents_create(body: dict, ctx: AuthContext = Depends(auth_any)):
        require_permission(ctx, "agent:write")
        tier_raw = str(body.get("agent_tier", AgentTier.BASIC_AGENT.value))
        agent_tier = AgentTier(tier_raw)
        agent = agent_os.create_agent(
            agent_id=str(body["agent_id"]),
            goal=str(body["goal"]),
            model=str(body["model"]),
            tenant_id=ctx.tenant_id,
            agent_tier=agent_tier,
            output_mode=str(body.get("output_mode", "text")),
            output_schema=body.get("output_schema"),
        )
        return agent.model_dump(mode="json")

    @app.get("/agents/{agent_id}/status")
    def agents_status(agent_id: str, ctx: AuthContext = Depends(auth_any)):
        require_permission(ctx, "agent:status")
        _agent_in_tenant(agent_id, ctx)
        status = agent_os.monitor.status(agent_id)
        return status.model_dump(mode="json")

    @app.get("/agents/{agent_id}/usage")
    def agents_usage(agent_id: str, start: str | None = None, end: str | None = None, ctx: AuthContext = Depends(auth_any)):
        require_permission(ctx, "agent:status")
        _agent_in_tenant(agent_id, ctx)
        start_dt = datetime.fromisoformat(start) if start else None
        end_dt = datetime.fromisoformat(end) if end else None
        rows = agent_os.monitor.usage(agent_id, start=start_dt, end=end_dt)
        return {"usage": [row.model_dump(mode="json") for row in rows]}

    @app.get("/agents/{agent_id}/costs")
    def agents_costs(agent_id: str, start: str | None = None, end: str | None = None, ctx: AuthContext = Depends(auth_any)):
        require_permission(ctx, "agent:status")
        _agent_in_tenant(agent_id, ctx)
        start_dt = datetime.fromisoformat(start) if start else None
        end_dt = datetime.fromisoformat(end) if end else None
        rows = agent_os.monitor.costs(agent_id, start=start_dt, end=end_dt)
        return {"costs": [row.model_dump(mode="json") for row in rows]}

    @app.get("/readyz")
    def readyz(ctx: AuthContext = Depends(auth_ops)):
        require_permission(ctx, "ops:readyz")
        if app.state.env_mode == "prod":
            status = check_dependencies(
                root=agent_os.root,
                postgres_dsn=None,
                redis_url=None,
                require_migration_head=True,
                secrets=agent_os.secrets,
            )
            if not (status["postgres_ok"] and status["redis_ok"] and status["migration_ok"]):
                raise HTTPException(status_code=503, detail={"worker": "ok" if app.state.worker_healthy else "unhealthy", "deps": status})
        ready = bool(app.state.worker_healthy)
        if not ready:
            raise HTTPException(status_code=503, detail="worker_unhealthy")
        return {"status": "ready"}

    @app.get("/metrics")
    def metrics(ctx: AuthContext = Depends(auth_ops)):
        require_permission(ctx, "ops:metrics")
        return agent_os.metrics.read()

    @app.post("/sessions/init")
    def sessions_init(body: dict, x_idempotency_key: str | None = Header(default=None), ctx: AuthContext = Depends(auth_any)):
        require_permission(ctx, "session:init")
        reused = _idempotent(x_idempotency_key)
        if reused is not None:
            return _op(reused.get("status", "ok"), reused.get("data", {}), reused=True, operation_id=reused.get("operation_id"))
        started = time.perf_counter()
        _agent_in_tenant(body["agent_id"], ctx)
        session = agent_os.sessions.init(agent_id=body["agent_id"], input=str(body["input"]))
        response = _op("ok", session.model_dump(mode="json"))
        _record(x_idempotency_key, response)
        agent_os.metrics.inc("api_sessions_init")
        agent_os.metrics.set("api_last_latency_ms", int((time.perf_counter() - started) * 1000))
        return response

    @app.post("/sessions/{session_id}/run")
    def sessions_run(session_id: str, x_idempotency_key: str | None = Header(default=None), ctx: AuthContext = Depends(auth_any)):
        require_permission(ctx, "session:run")
        reused = _idempotent(x_idempotency_key)
        if reused is not None:
            return _op(reused.get("status", "ok"), reused.get("data", {}), reused=True, operation_id=reused.get("operation_id"))
        _session_in_tenant(session_id, ctx)
        output = agent_os.sessions.run(session_id)
        payload = output.model_dump(mode="json")
        runtime_metadata = payload.get("runtime_metadata") or {}
        payload["runtime_engine"] = runtime_metadata.get("runtime_engine", "unknown")
        payload["sdk_run_id"] = runtime_metadata.get("sdk_run_id")
        response = _op("ok", payload)
        _record(x_idempotency_key, response)
        agent_os.metrics.inc("api_sessions_run")
        return response

    @app.post("/sessions/{session_id}/feedback")
    def sessions_feedback(session_id: str, body: dict, x_idempotency_key: str | None = Header(default=None), ctx: AuthContext = Depends(auth_any)):
        require_permission(ctx, "session:feedback")
        reused = _idempotent(x_idempotency_key)
        if reused is not None:
            return _op(reused.get("status", "ok"), reused.get("data", {}), reused=True, operation_id=reused.get("operation_id"))
        _session_in_tenant(session_id, ctx)
        event = agent_os.sessions.feedback(session_id, str(body["feedback"]))
        response = _op("ok", event.model_dump(mode="json"))
        _record(x_idempotency_key, response)
        agent_os.metrics.inc("api_sessions_feedback")
        return response

    @app.post("/sessions/{session_id}/accept")
    def sessions_accept(session_id: str, body: dict | None = None, x_idempotency_key: str | None = Header(default=None), ctx: AuthContext = Depends(auth_any)):
        require_permission(ctx, "session:accept")
        reused = _idempotent(x_idempotency_key)
        if reused is not None:
            return _op(reused.get("status", "ok"), reused.get("data", {}), reused=True, operation_id=reused.get("operation_id"))
        _session_in_tenant(session_id, ctx)
        note = None if body is None else body.get("note")
        event = agent_os.sessions.accept(session_id, note=note)
        response = _op("ok", event.model_dump(mode="json"))
        _record(x_idempotency_key, response)
        agent_os.metrics.inc("api_sessions_accept")
        return response

    @app.get("/sessions/{session_id}")
    def sessions_get(session_id: str, ctx: AuthContext = Depends(auth_any)):
        require_permission(ctx, "session:get")
        events = _session_in_tenant(session_id, ctx)
        return {"session_id": session_id, "events": [event.model_dump(mode="json") for event in events]}

    @app.post("/learning/run")
    def learning_run(body: dict, x_idempotency_key: str | None = Header(default=None), ctx: AuthContext = Depends(auth_any)):
        require_permission(ctx, "learning:run")
        reused = _idempotent(x_idempotency_key)
        if reused is not None:
            return _op(reused.get("status", "ok"), reused.get("data", {}), reused=True, operation_id=reused.get("operation_id"))
        _agent_in_tenant(body["agent_id"], ctx)
        result = agent_os.jobs.enqueue(
            type="learn_run",
            payload={
                "agent_id": body["agent_id"],
                "session_ids": body.get("session_ids"),
                "window_size": body.get("window_size", 50),
            },
            idempotency_key=x_idempotency_key,
        )
        return _op(result["status"], result, operation_id=result["operation_id"])

    @app.get("/flame/pool")
    def flame_pool(agent_id: str, state: FlamePoolState | None = None, ctx: AuthContext = Depends(auth_any)):
        require_permission(ctx, "learning:evaluate")
        _agent_in_tenant(agent_id, ctx)
        rows = [row for row in agent_os.flame.list_pool(agent_id=agent_id, state=state) if row.tenant_id == ctx.tenant_id]
        return {"pool_items": [row.model_dump(mode="json") for row in rows]}

    @app.get("/flame/runs")
    def flame_runs(agent_id: str, ctx: AuthContext = Depends(auth_any)):
        require_permission(ctx, "learning:evaluate")
        _agent_in_tenant(agent_id, ctx)
        rows = [row for row in agent_os.flame.list_runs(agent_id=agent_id) if row.tenant_id == ctx.tenant_id]
        return {"runs": [row.model_dump(mode="json") for row in rows]}

    @app.post("/flame/trigger")
    def flame_trigger(body: dict, x_idempotency_key: str | None = Header(default=None), ctx: AuthContext = Depends(auth_any)):
        require_permission(ctx, "learning:run")
        reused = _idempotent(x_idempotency_key)
        if reused is not None:
            return _op(reused.get("status", "ok"), reused.get("data", {}), reused=True, operation_id=reused.get("operation_id"))
        agent_id = body.get("agent_id")
        if agent_id:
            _agent_in_tenant(str(agent_id), ctx)
        runs = agent_os.flame.trigger(agent_id=agent_id, force=bool(body.get("force", False)))
        payload = {"runs": [run.model_dump(mode="json") for run in runs]}
        response = _op("ok", payload)
        _record(x_idempotency_key, response)
        agent_os.metrics.inc("api_flame_trigger")
        return response

    @app.get("/learning/policy/{agent_id}")
    def learning_policy_get(agent_id: str, ctx: AuthContext = Depends(auth_any)):
        require_permission(ctx, "learning:policy")
        _agent_in_tenant(agent_id, ctx)
        policy = agent_os.learning.get_policy(agent_id)
        if policy.tenant_id != ctx.tenant_id:
            raise HTTPException(status_code=403, detail="cross_tenant_policy_denied")
        return policy.model_dump(mode="json")

    @app.post("/learning/policy/{agent_id}")
    def learning_policy_set(agent_id: str, body: dict, ctx: AuthContext = Depends(auth_any)):
        require_permission(ctx, "learning:policy")
        _agent_in_tenant(agent_id, ctx)
        policy = PromotionPolicy(
            agent_id=agent_id,
            tenant_id=ctx.tenant_id,
            mode=body.get("mode", "auto_low_risk"),
            max_safety_failures=body.get("max_safety_failures", 0),
            max_regression_warnings=body.get("max_regression_warnings", 1),
            min_confidence=body.get("min_confidence", 0.60),
            min_quality_delta=body.get("min_quality_delta", 0.02),
        )
        updated = agent_os.learning.set_policy(agent_id=agent_id, policy=policy)
        return updated.model_dump(mode="json")

    @app.post("/tools/register")
    def tools_register(body: dict, ctx: AuthContext = Depends(auth_any)):
        require_permission(ctx, "tools:register")
        manifest = ToolManifest.model_validate(body)
        manifest.tenant_id = ctx.tenant_id
        created = agent_os.tools.register(manifest)
        return created.model_dump(mode="json")

    @app.post("/tools/bind")
    def tools_bind(body: dict, ctx: AuthContext = Depends(auth_any)):
        require_permission(ctx, "tools:bind")
        _agent_in_tenant(body["agent_id"], ctx)
        manifest = agent_os.store.load_tool_manifest(body["tool_id"])
        if manifest.tenant_id != ctx.tenant_id:
            raise HTTPException(status_code=403, detail="cross_tenant_tool_denied")
        agent_os.tools.bind(
            agent_id=body["agent_id"],
            tool_id=body["tool_id"],
            allow_write=bool(body.get("allow_write", False)),
        )
        return {"status": "ok"}

    @app.post("/tools/call")
    def tools_call(body: dict, x_idempotency_key: str | None = Header(default=None), ctx: AuthContext = Depends(auth_any)):
        require_permission(ctx, "tools:call")
        reused = _idempotent(x_idempotency_key)
        if reused is not None:
            return _op(reused.get("status", "ok"), reused.get("data", {}), reused=True, operation_id=reused.get("operation_id"))
        _agent_in_tenant(body["agent_id"], ctx)
        result, audit = agent_os.tools.call(
            agent_id=body["agent_id"],
            session_id=body.get("session_id"),
            tool_id=body["tool_id"],
            args=body.get("args", {}),
            auth=ctx,
        )
        response = _op(
            "ok",
            {"result": result.model_dump(mode="json"), "audit": audit.model_dump(mode="json")},
        )
        _record(x_idempotency_key, response)
        agent_os.metrics.inc("api_tools_call")
        return response

    @app.get("/tools/audit")
    def tools_audit(agent_id: str, session_id: str | None = None, ctx: AuthContext = Depends(auth_any)):
        require_permission(ctx, "tools:audit")
        _agent_in_tenant(agent_id, ctx)
        audits = [a for a in agent_os.tools.audit(agent_id=agent_id, session_id=session_id) if a.tenant_id == ctx.tenant_id]
        return {"audits": [audit.model_dump(mode="json") for audit in audits]}

    @app.get("/ops/secrets/status")
    def ops_secrets_status(ctx: AuthContext = Depends(auth_ops)):
        require_permission(ctx, "ops:metrics")
        return redact(agent_os.secrets.status())

    @app.post("/ops/secrets/reload")
    def ops_secrets_reload(ctx: AuthContext = Depends(auth_ops)):
        require_permission(ctx, "ops:metrics")
        status = agent_os.secrets.reload()
        return redact(status)

    @app.post("/ops/capabilities/refresh")
    def ops_capabilities_refresh(ctx: AuthContext = Depends(auth_ops)):
        require_permission(ctx, "ops:capabilities")
        result = agent_os.capabilities.refresh()
        return {"refreshed_at": result.refreshed_at, "model_count": result.model_count}

    class RequestContextMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):  # type: ignore[override]
            request_id = request.headers.get("x-request-id", f"req_{uuid4().hex}")
            started = time.perf_counter()
            response = await call_next(request)
            response.headers["x-request-id"] = request_id
            agent_os.metrics.set("api_last_latency_ms", int((time.perf_counter() - started) * 1000))
            return response

    app.add_middleware(RequestContextMiddleware)
    return app


