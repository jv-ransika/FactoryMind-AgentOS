from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from agent_os import AgentOS
from agent_os.cli.app import app
from agent_os.secrets import SecretManager, redact
from agent_os.service import create_service_app


def _dev_token(tenant_id: str = "t1", roles: list[str] | None = None) -> str:
    import base64

    roles = roles or ["admin", "ops", "user"]
    payload = {
        "sub": "u1",
        "tenant_id": tenant_id,
        "roles": roles,
        "iss": "agent-os",
        "aud": "agent-os",
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp()),
    }
    return "dev." + base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")


def test_secret_provider_precedence(tmp_path, monkeypatch) -> None:
    root = tmp_path / ".agent-os"
    root.mkdir(parents=True, exist_ok=True)
    (root / "secrets.env").write_text("OPENAI_API_KEY=from_env_file\n", encoding="utf-8")
    (root / "secrets.json").write_text(json.dumps({"OPENAI_API_KEY": "from_json_file"}), encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "from_environment")
    manager = SecretManager(root=root)
    assert manager.get("OPENAI_API_KEY") == "from_environment"


def test_validate_required_profiles(tmp_path, monkeypatch) -> None:
    root = tmp_path / ".agent-os"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    manager = SecretManager(root=root)
    assert manager.validate_required("dev")["ok"] is False
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    assert SecretManager(root=root).validate_required("dev")["ok"] is True


def test_redaction_hides_values() -> None:
    raw = {"openai_api_key": "sk-secret", "nested": {"Authorization": "Bearer x"}}
    r = redact(raw)
    assert r["openai_api_key"] == "[REDACTED]"
    assert r["nested"]["Authorization"] == "[REDACTED]"


def test_runtime_fail_closed_then_reload(monkeypatch, tmp_path) -> None:
    root = tmp_path / ".agent-os"
    agent_os = AgentOS.load(root=root, runtime_mode="openai")
    agent_os.create_agent(agent_id="a1", goal="g", model="gpt-4.1-mini", tenant_id="t1")
    session = agent_os.sessions.init("a1", "hello")
    out = agent_os.sessions.run(session.session_id)
    assert out.type == "error"
    monkeypatch.setenv("OPENAI_API_KEY", "now_available")
    agent_os.secrets.reload()
    # runtime call can still fail provider, but config error should disappear
    out2 = agent_os.sessions.run(session.session_id)
    assert "runtime_config_error" not in out2.confidence.basis


def test_service_ops_secret_reload_and_status(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENT_OS_JWT_ISSUER", "agent-os")
    monkeypatch.setenv("AGENT_OS_JWT_AUDIENCE", "agent-os")
    token = _dev_token()
    headers = {"Authorization": f"Bearer {token}"}
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="a1", goal="g", model="gpt-4.1-mini", tenant_id="t1")
    client = TestClient(create_service_app(agent_os))
    status = client.get("/ops/secrets/status", headers=headers)
    reloaded = client.post("/ops/secrets/reload", headers=headers)
    assert status.status_code == 200
    assert reloaded.status_code == 200
    assert "providers" in status.json()


def test_cli_secrets_commands(tmp_path) -> None:
    runner = CliRunner()
    root = str(tmp_path / ".agent-os")
    assert runner.invoke(app, ["secrets", "show-status", "--root", root]).exit_code == 0
    assert runner.invoke(app, ["secrets", "validate", "--env", "dev", "--root", root]).exit_code == 0
    assert runner.invoke(app, ["secrets", "reload", "--root", root]).exit_code == 0
