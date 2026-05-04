from __future__ import annotations

import os
import json
import base64
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from agent_os import AgentOS, AgentTier
from agent_os.cli.app import app
from agent_os.service import create_service_app


def _auth_headers(tmp_path, tenant_id: str = "t1", roles: list[str] | None = None) -> dict[str, str]:
    roles = roles or ["admin", "ops", "user"]
    os.environ["AGENT_OS_JWT_ISSUER"] = "agent-os"
    os.environ["AGENT_OS_JWT_AUDIENCE"] = "agent-os"
    payload = {
        "sub": "u1",
        "tenant_id": tenant_id,
        "roles": roles,
        "iss": "agent-os",
        "aud": "agent-os",
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp()),
    }
    token = "dev." + base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
    return {"Authorization": f"Bearer {token}"}


def test_idempotency_reuses_mutating_result(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(
        agent_id="project_selector",
        goal="Select projects.",
        model="gpt-4.1-mini",
        tenant_id="t1",
        agent_tier=AgentTier.SELF_LEARNING_AGENT,
    )
    auth = _auth_headers(tmp_path)
    client = TestClient(create_service_app(agent_os))
    headers = {"x-idempotency-key": "same-key-1"}
    headers.update(auth)

    first = client.post("/sessions/init", json={"agent_id": "project_selector", "input": "Find projects."}, headers=headers)
    second = client.post("/sessions/init", json={"agent_id": "project_selector", "input": "Find projects."}, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["idempotency_reused"] is True
    assert first.json()["operation_id"] == second.json()["operation_id"]


def test_queue_retry_and_dead_letter(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(
        agent_id="project_selector",
        goal="Select projects.",
        model="gpt-4.1-mini",
        tenant_id="t1",
        agent_tier=AgentTier.SELF_LEARNING_AGENT,
    )
    bad = agent_os.jobs.enqueue(
        type="tool_call_async",
        payload={"agent_id": "project_selector", "tool_id": "missing_tool", "args": {}},
    )
    assert bad["status"] == "queued"
    for _ in range(4):
        agent_os.jobs.process_next()
    dead = list((agent_os.store.root / "jobs" / "dead_letter").glob("*.json"))
    assert dead, "Expected dead-letter job after retries."


def test_api_session_flow_end_to_end(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(
        agent_id="proposal_writer",
        goal="Write proposals.",
        model="gpt-4.1-mini",
        tenant_id="t1",
        agent_tier=AgentTier.SELF_LEARNING_AGENT,
    )
    auth = _auth_headers(tmp_path)
    client = TestClient(create_service_app(agent_os))

    init = client.post("/sessions/init", json={"agent_id": "proposal_writer", "input": "Draft proposal."}, headers=auth)
    session_id = init.json()["data"]["session_id"]
    run = client.post(f"/sessions/{session_id}/run", headers=auth)
    feedback = client.post(f"/sessions/{session_id}/feedback", json={"feedback": "Add delivery risk."}, headers=auth)
    accept = client.post(f"/sessions/{session_id}/accept", json={"note": "ok"}, headers=auth)
    get = client.get(f"/sessions/{session_id}", headers=auth)

    assert init.status_code == 200
    assert run.status_code == 200
    assert feedback.status_code == 200
    assert accept.status_code == 200
    assert get.status_code == 200
    assert len(get.json()["events"]) >= 4


def test_learning_async_job_pipeline(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(
        agent_id="project_selector",
        goal="Select projects.",
        model="gpt-4.1-mini",
        tenant_id="t1",
        agent_tier=AgentTier.SELF_LEARNING_AGENT,
    )
    session = agent_os.sessions.init("project_selector", "Select low risk projects.")
    agent_os.sessions.run(session.session_id)
    agent_os.sessions.feedback(session.session_id, "Prefer delivery risk.")
    agent_os.sessions.accept(session.session_id)
    auth = _auth_headers(tmp_path)
    client = TestClient(create_service_app(agent_os))
    queued = client.post("/learning/run", json={"agent_id": "project_selector", "window_size": 10}, headers=auth)
    assert queued.status_code == 200
    assert queued.json()["status"] == "queued"
    processed = agent_os.jobs.run_worker(once=True)
    assert processed >= 1


def test_tools_async_and_audit(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(
        agent_id="project_selector",
        goal="Select projects.",
        model="gpt-4.1-mini",
        tenant_id="t1",
        agent_tier=AgentTier.SELF_LEARNING_AGENT,
    )
    manifest = agent_os.tools.register_from_fields(name="project_db.search")
    manifest.tenant_id = "t1"
    agent_os.tools.register(manifest)
    agent_os.tools.bind("project_selector", manifest.tool_id)
    auth = _auth_headers(tmp_path)
    client = TestClient(create_service_app(agent_os))
    response = client.post(
        "/tools/call",
        json={"agent_id": "project_selector", "tool_id": manifest.tool_id, "args": {"query": "ai"}},
        headers=auth,
    )
    assert response.status_code == 200
    audits = client.get("/tools/audit", params={"agent_id": "project_selector"}, headers=auth)
    assert audits.status_code == 200
    assert audits.json()["audits"]


def test_readiness_and_metrics(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    auth = _auth_headers(tmp_path, roles=["ops"])
    service = create_service_app(agent_os)
    client = TestClient(service)
    health = client.get("/healthz")
    ready = client.get("/readyz", headers=auth)
    metrics = client.get("/metrics", headers=auth)
    assert health.status_code == 200
    assert ready.status_code == 200
    assert metrics.status_code == 200
    assert isinstance(metrics.json(), dict)


def test_api_json_schema_agent_run_returns_content_json(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(
        agent_id="json_writer",
        goal="Write structured proposals.",
        model="gpt-4.1-mini",
        tenant_id="t1",
        agent_tier=AgentTier.SELF_LEARNING_AGENT,
        output_mode="json_schema",
        output_schema={
            "type": "object",
            "required": ["title"],
            "properties": {"title": {"type": "string"}},
            "additionalProperties": False,
        },
    )
    auth = _auth_headers(tmp_path)
    client = TestClient(create_service_app(agent_os))
    init = client.post("/sessions/init", json={"agent_id": "json_writer", "input": "Draft proposal."}, headers=auth)
    session_id = init.json()["data"]["session_id"]
    run = client.post(f"/sessions/{session_id}/run", headers=auth)
    assert run.status_code == 200
    assert isinstance(run.json()["data"].get("content_json"), dict)
    assert "title" in run.json()["data"]["content_json"]


def test_worker_cli_run_once_and_tick(tmp_path) -> None:
    runner = CliRunner()
    root = str(tmp_path / ".agent-os")
    assert runner.invoke(app, ["init", "--root", root]).exit_code == 0
    assert runner.invoke(
        app,
        [
            "create",
            "agent",
            "project_selector",
            "--goal",
            "Select projects.",
            "--model",
            "gpt-4.1-mini",
            "--agent-tier",
            "self_learning_agent",
            "--root",
            root,
        ],
    ).exit_code == 0
    queued = runner.invoke(
        app,
        [
            "learn",
            "run",
            "project_selector",
            "--window-size",
            "5",
            "--root",
            root,
        ],
    )
    assert queued.exit_code == 0
    tick = runner.invoke(app, ["worker", "tick", "--root", root])
    run_once = runner.invoke(app, ["worker", "run", "--once", "--root", root])
    assert tick.exit_code == 0
    assert run_once.exit_code == 0


