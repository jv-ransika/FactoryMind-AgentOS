from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timedelta, timezone

import httpx
from fastapi.testclient import TestClient

from agent_os import AgentOS, AgentTier, OutputType
from agent_os.service import create_service_app


def _token_headers(tenant_id: str, roles: list[str]) -> dict[str, str]:
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


def test_acceptance_with_feedback_enqueues_reflection_for_self_learning_agent(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(
        agent_id="a1",
        goal="g1",
        model="gpt-4.1-mini",
        tenant_id="t1",
        agent_tier=AgentTier.SELF_LEARNING_AGENT,
    )
    session = agent_os.sessions.init("a1", "hello")
    agent_os.sessions.run(session.session_id)
    agent_os.sessions.feedback(session.session_id, "use clearer structure")
    agent_os.sessions.accept(session.session_id)

    pool = agent_os.flame.list_pool("a1")
    assert pool
    assert all(item.extracted_type.value == "learning_point" for item in pool)


def test_acceptance_without_feedback_stores_experience_for_self_learning_agent(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(
        agent_id="a1",
        goal="g1",
        model="gpt-4.1-mini",
        tenant_id="t1",
        agent_tier=AgentTier.SELF_LEARNING_AGENT,
    )
    session = agent_os.sessions.init("a1", "hello")
    agent_os.sessions.run(session.session_id)
    agent_os.sessions.accept(session.session_id)
    pool = agent_os.flame.list_pool("a1")
    assert pool
    assert all(item.extracted_type.value == "experience" for item in pool)


def test_openai_runtime_fails_closed_for_unknown_model_capability(monkeypatch, tmp_path) -> None:
    class FakeGetResponse:
        status_code = 200

        def raise_for_status(self):
            return None

    monkeypatch.setattr(httpx.Client, "get", lambda self, url, headers: FakeGetResponse())
    agent_os = AgentOS.load(root=tmp_path / ".agent-os", runtime_mode="openai", openai_api_key="k")
    agent_os.create_agent(agent_id="a1", goal="g1", model="unknown-model", tenant_id="t1")
    session = agent_os.sessions.init("a1", "hello")
    output = agent_os.sessions.run(session.session_id)
    assert output.type == OutputType.ERROR
    assert "runtime_config_error" in output.confidence.basis


def test_status_usage_cost_endpoints(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="a1", goal="g1", model="gpt-4.1-mini", tenant_id="t1", agent_tier=AgentTier.SELF_LEARNING_AGENT)
    session = agent_os.sessions.init("a1", "hello")
    agent_os.sessions.run(session.session_id)
    from agent_os.protocol import CostRecord, UsageRecord

    usage = UsageRecord(
        agent_id="a1",
        tenant_id="t1",
        session_id=session.session_id,
        operation_bucket="main_run",
        model="gpt-4.1-mini",
        request_bytes=120,
        input_tokens=30,
        output_tokens=10,
        total_tokens=40,
        latency_ms=5,
    )
    cost = CostRecord(
        usage_id=usage.usage_id,
        agent_id="a1",
        tenant_id="t1",
        operation_bucket="main_run",
        model="gpt-4.1-mini",
        estimated_cost_usd=0.0001,
        cost_status="computed",
    )
    agent_os.usage.record(usage, cost)

    client = TestClient(create_service_app(agent_os))
    headers = _token_headers(tenant_id="t1", roles=["admin", "ops", "user"])
    status = client.get("/agents/a1/status", headers=headers)
    usage = client.get("/agents/a1/usage", headers=headers)
    costs = client.get("/agents/a1/costs", headers=headers)

    assert status.status_code == 200
    assert usage.status_code == 200
    assert costs.status_code == 200
    assert "usage" in usage.json()
    assert "costs" in costs.json()
