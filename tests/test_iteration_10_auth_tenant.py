from __future__ import annotations

import os
import json
import base64
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from agent_os import AgentOS, AgentTier
from agent_os.service import create_service_app


def _token_headers(tmp_path, tenant_id: str, roles: list[str]) -> dict[str, str]:
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


def test_missing_auth_denied(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="a1", goal="g1", model="gpt-4.1-mini", tenant_id="t1", agent_tier=AgentTier.SELF_LEARNING_AGENT)
    client = TestClient(create_service_app(agent_os))
    resp = client.post("/sessions/init", json={"agent_id": "a1", "input": "hi"})
    assert resp.status_code == 401


def test_cross_tenant_denied(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="a1", goal="g1", model="gpt-4.1-mini", tenant_id="t1")
    headers = _token_headers(tmp_path, tenant_id="t2", roles=["admin", "user"])
    client = TestClient(create_service_app(agent_os))
    resp = client.post("/sessions/init", json={"agent_id": "a1", "input": "hi"}, headers=headers)
    assert resp.status_code == 403


def test_role_denied_for_policy_set(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="a1", goal="g1", model="gpt-4.1-mini", tenant_id="t1", agent_tier=AgentTier.SELF_LEARNING_AGENT)
    headers = _token_headers(tmp_path, tenant_id="t1", roles=["user"])
    client = TestClient(create_service_app(agent_os))
    resp = client.post("/learning/policy/a1", json={"mode": "suggest_only"}, headers=headers)
    assert resp.status_code == 403


def test_tool_audit_has_actor_tenant_and_hash_chain(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="a1", goal="g1", model="gpt-4.1-mini", tenant_id="t1")
    manifest = agent_os.tools.register_from_fields(name="project_db.search")
    manifest.tenant_id = "t1"
    agent_os.tools.register(manifest)
    agent_os.tools.bind("a1", manifest.tool_id)
    headers = _token_headers(tmp_path, tenant_id="t1", roles=["admin", "user"])
    client = TestClient(create_service_app(agent_os))
    first = client.post("/tools/call", json={"agent_id": "a1", "tool_id": manifest.tool_id, "args": {"query": "a"}}, headers=headers)
    second = client.post("/tools/call", json={"agent_id": "a1", "tool_id": manifest.tool_id, "args": {"query": "b"}}, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    audits = client.get("/tools/audit", params={"agent_id": "a1"}, headers=headers).json()["audits"]
    assert len(audits) >= 2
    assert audits[-1]["actor_sub"] == "u1"
    assert audits[-1]["tenant_id"] == "t1"
    assert audits[-1]["entry_hash"] is not None
