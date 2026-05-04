from __future__ import annotations

import httpx
from typer.testing import CliRunner

from agent_os import AgentOS, AgentTier, OutputType
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
    class FakeGetResponse:
        status_code = 200

        def raise_for_status(self):
            return None

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": '{"type":"final","content":"Done.","confidence_score":0.84,"confidence_basis":["tool_evidence"],"uncertainties":[]}',
                "usage": {"input_tokens": 120, "output_tokens": 30, "reasoning_tokens": 0, "total_tokens": 150},
            }

    def fake_post(self, url, headers, json):
        return FakeResponse()
    
    def fake_get(self, url, headers):
        return FakeGetResponse()

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    agent_os = AgentOS.load(root=tmp_path / ".agent-os", runtime_mode="openai", openai_api_key="k")
    agent_os.create_agent(
        agent_id="project_selector",
        goal="Select projects.",
        model="gpt-4.1-mini",
        agent_tier=AgentTier.SELF_LEARNING_AGENT,
    )
    session = agent_os.sessions.init("project_selector", "Find a project")
    output = agent_os.sessions.run(session.session_id)
    assert output.type == OutputType.FINAL
    assert output.confidence.score <= 0.45


def test_context_budget_truncates_deterministically(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(
        agent_id="project_selector",
        goal="Select projects.",
        model="gpt-4.1-mini",
        agent_tier=AgentTier.SELF_LEARNING_AGENT,
    )
    session = agent_os.sessions.init(agent_id="project_selector", input="select projects quickly")
    agent_os.sessions.feedback(session.session_id, " ".join(["need more constraints"] * 300))
    events = agent_os.sessions.events(session.session_id)
    packet = agent_os.context.build(
        agent_id="project_selector",
        active_input="select projects quickly",
        events=events,
        token_budget=40,
    )
    assert packet.truncated is True
    assert packet.estimated_tokens is not None
    assert "feedback_compacted" in packet.truncation_notes


def test_soft_gate_confidence_downgrade_for_weak_evidence(monkeypatch, tmp_path) -> None:
    class FakeGetResponse:
        status_code = 200

        def raise_for_status(self):
            return None

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": '{"type":"final","content":"Final answer.","confidence_score":0.95,"confidence_basis":["model"],"uncertainties":[]}',
                "usage": {"input_tokens": 100, "output_tokens": 20, "reasoning_tokens": 0, "total_tokens": 120},
            }

    def fake_post(self, url, headers, json):
        return FakeResponse()
    
    def fake_get(self, url, headers):
        return FakeGetResponse()

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    agent_os = AgentOS.load(root=tmp_path / ".agent-os", runtime_mode="openai", openai_api_key="k")
    agent_os.create_agent(agent_id="proposal_writer", goal="Write proposals.", model="gpt-4.1-mini")
    session = agent_os.sessions.init("proposal_writer", "draft proposal")
    output = agent_os.sessions.run(session.session_id)
    assert output.type == OutputType.FINAL
    assert output.confidence.score <= 0.45
    assert "weak_evidence_soft_gate" in output.confidence.basis


def test_cli_runtime_validate_config(tmp_path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    root = str(tmp_path / ".agent-os")
    result = runner.invoke(app, ["runtime", "validate-config", "--root", root, "--runtime-mode", "openai"])
    assert result.exit_code == 0
    assert '"ok": false' in result.output


def test_openai_runtime_json_schema_mode_returns_content_json(monkeypatch, tmp_path) -> None:
    class FakeGetResponse:
        status_code = 200

        def raise_for_status(self):
            return None

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": '{"title":"Proposal","decision":"Proceed","risks":["delay"],"next_steps":["review"]}',
                "usage": {"input_tokens": 80, "output_tokens": 20, "reasoning_tokens": 0, "total_tokens": 100},
            }

    def fake_post(self, url, headers, json):
        return FakeResponse()

    def fake_get(self, url, headers):
        return FakeGetResponse()

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    agent_os = AgentOS.load(root=tmp_path / ".agent-os", runtime_mode="openai", openai_api_key="k")
    agent_os.create_agent(
        agent_id="json_writer",
        goal="Write structured proposals.",
        model="gpt-4.1-mini",
        agent_tier=AgentTier.SELF_LEARNING_AGENT,
        output_mode="json_schema",
        output_schema={
            "type": "object",
            "required": ["title", "decision", "risks", "next_steps"],
            "properties": {
                "title": {"type": "string"},
                "decision": {"type": "string"},
                "risks": {"type": "array", "items": {"type": "string"}},
                "next_steps": {"type": "array", "items": {"type": "string"}},
            },
            "additionalProperties": False,
        },
    )
    session = agent_os.sessions.init("json_writer", "Draft proposal")
    output = agent_os.sessions.run(session.session_id)
    assert output.type == OutputType.FINAL
    assert isinstance(output.content_json, dict)
    assert output.content_json["title"] == "Proposal"


def test_openai_runtime_json_schema_mode_invalid_output_errors(monkeypatch, tmp_path) -> None:
    class FakeGetResponse:
        status_code = 200

        def raise_for_status(self):
            return None

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": '{"title":"Proposal"}',
                "usage": {"input_tokens": 80, "output_tokens": 20, "reasoning_tokens": 0, "total_tokens": 100},
            }

    def fake_post(self, url, headers, json):
        return FakeResponse()

    def fake_get(self, url, headers):
        return FakeGetResponse()

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    agent_os = AgentOS.load(root=tmp_path / ".agent-os", runtime_mode="openai", openai_api_key="k")
    agent_os.create_agent(
        agent_id="json_writer",
        goal="Write structured proposals.",
        model="gpt-4.1-mini",
        output_mode="json_schema",
        output_schema={
            "type": "object",
            "required": ["title", "decision"],
            "properties": {
                "title": {"type": "string"},
                "decision": {"type": "string"},
            },
            "additionalProperties": False,
        },
    )
    session = agent_os.sessions.init("json_writer", "Draft proposal")
    output = agent_os.sessions.run(session.session_id)
    assert output.type == OutputType.ERROR
    assert "invalid_model_output" in output.confidence.basis
