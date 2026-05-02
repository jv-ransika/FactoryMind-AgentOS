from __future__ import annotations

import httpx
from typer.testing import CliRunner

from agent_os import AgentOS, OutputType
from agent_os.cli.app import app
from agent_os.runtime import OpenAIRuntimeAdapter, load_runtime_config


def test_runtime_config_fail_fast_for_openai_missing_key(tmp_path) -> None:
    cfg = load_runtime_config(root=tmp_path / ".agent-os", runtime_mode="openai")
    adapter = OpenAIRuntimeAdapter(config=cfg)
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent = agent_os.create_agent(agent_id="proposal_writer", goal="Write proposals.", model="gpt-4.1-mini")
    session = agent_os.sessions.init(agent.id, "Draft proposal")
    output = adapter.run(agent=agent, events=agent_os.sessions.events(session.session_id), input_text="Draft proposal")
    assert output.type == OutputType.ERROR
    assert "runtime_config_error" in output.confidence.basis


def test_openai_runtime_typed_final_with_mock(monkeypatch, tmp_path) -> None:
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"type":"final","content":"Done.","confidence_score":0.84,"confidence_basis":["tool_evidence"],"uncertainties":[]}'
                        }
                    }
                ]
            }

    def fake_post(self, url, headers, json):
        return FakeResponse()

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    agent_os = AgentOS.load(root=tmp_path / ".agent-os", runtime_mode="openai", openai_api_key="k")
    agent_os.create_agent(agent_id="project_selector", goal="Select projects.", model="gpt-4.1-mini")
    session = agent_os.sessions.init("project_selector", "Find a project")
    output = agent_os.sessions.run(session.session_id)
    assert output.type == OutputType.FINAL
    assert output.confidence.score <= 0.45


def test_context_budget_truncates_deterministically(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="project_selector", goal="Select projects.", model="gpt-4.1-mini")
    for i in range(20):
        agent_os.memory.create(
            agent_id="project_selector",
            content=f"select projects memory content {i} with many repeated words repeated repeated",
            tags=["select", "projects"],
        )
    packet = agent_os.context.build(
        agent_id="project_selector",
        active_input="select projects quickly",
        token_budget=40,
    )
    assert packet.truncated is True
    assert packet.estimated_tokens is not None
    assert packet.estimated_tokens <= 40


def test_soft_gate_confidence_downgrade_for_weak_evidence(monkeypatch, tmp_path) -> None:
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"type":"final","content":"Final answer.","confidence_score":0.95,"confidence_basis":["model"],"uncertainties":[]}'
                        }
                    }
                ]
            }

    def fake_post(self, url, headers, json):
        return FakeResponse()

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    agent_os = AgentOS.load(root=tmp_path / ".agent-os", runtime_mode="openai", openai_api_key="k")
    agent_os.create_agent(agent_id="proposal_writer", goal="Write proposals.", model="gpt-4.1-mini")
    session = agent_os.sessions.init("proposal_writer", "draft proposal")
    output = agent_os.sessions.run(session.session_id)
    assert output.type == OutputType.FINAL
    assert output.confidence.score <= 0.45
    assert "weak_evidence_soft_gate" in output.confidence.basis


def test_cli_runtime_validate_config(tmp_path) -> None:
    runner = CliRunner()
    root = str(tmp_path / ".agent-os")
    result = runner.invoke(app, ["runtime", "validate-config", "--root", root, "--runtime-mode", "openai"])
    assert result.exit_code == 0
    assert '"ok": false' in result.output
