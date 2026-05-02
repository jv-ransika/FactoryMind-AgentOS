from __future__ import annotations

import os

from typer.testing import CliRunner

from agent_os import AgentOS, StorageMode
from agent_os.cli.app import app
from agent_os.deploy import render_ecs_task, required_env_contract
from agent_os.ops.deps import check_dependencies


def test_prod_mode_rejects_local_storage(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENT_OS_ENV", "prod")
    try:
        AgentOS.load(root=tmp_path / ".agent-os", storage_mode=StorageMode.LOCAL)
        assert False, "Expected RuntimeError in prod with local storage"
    except RuntimeError:
        pass


def test_render_ecs_task_contract() -> None:
    service = render_ecs_task("service")
    worker = render_ecs_task("worker")
    assert service["family"] == "agent-os-service"
    assert worker["family"] == "agent-os-worker"
    keys = required_env_contract()
    env_keys = [item["name"] for item in service["containerDefinitions"][0]["environment"]]
    for key in keys:
        assert key in env_keys


def test_check_deps_missing_inputs(tmp_path) -> None:
    status = check_dependencies(root=tmp_path / ".agent-os", postgres_dsn=None, redis_url=None)
    assert status["postgres_ok"] is False
    assert status["redis_ok"] is False
    assert status["errors"]


def test_cli_deploy_print_and_validate(tmp_path, monkeypatch) -> None:
    runner = CliRunner()
    printed = runner.invoke(app, ["deploy", "print-ecs-task", "--role", "service"])
    assert printed.exit_code == 0
    assert '"family": "agent-os-service"' in printed.output

    monkeypatch.delenv("AGENT_OS_POSTGRES_DSN", raising=False)
    monkeypatch.delenv("AGENT_OS_REDIS_URL", raising=False)
    validated = runner.invoke(app, ["deploy", "validate-config", "--env", "prod", "--root", str(tmp_path / ".agent-os")])
    assert validated.exit_code == 0
    assert '"ok": false' in validated.output.lower()
