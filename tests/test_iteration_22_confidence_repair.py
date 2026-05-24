from __future__ import annotations

import json

import httpx

from agent_os import AgentOS, OutputType
from agent_os.protocol import AgentDefinition, AgentOutput, Confidence, ContextPacket, EventType, RuntimeConfig, SessionEvent
from agent_os.runtime import AgentRuntimeAdapter, load_runtime_config


class SequencedRuntime(AgentRuntimeAdapter):
    def __init__(self, outputs: list[AgentOutput], config: RuntimeConfig | None = None) -> None:
        self.outputs = outputs
        self.calls: list[str] = []
        self.config = config or RuntimeConfig()

    def run(
        self,
        agent: AgentDefinition,
        events: list[SessionEvent],
        input_text: str,
        context: ContextPacket | None = None,
    ) -> AgentOutput:
        self.calls.append(input_text)
        index = min(len(self.calls) - 1, len(self.outputs) - 1)
        return self.outputs[index]


def _output(type_: OutputType, score: float, content: str = "content", basis: list[str] | None = None) -> AgentOutput:
    level = "low" if score < 0.4 else "medium" if score < 0.75 else "high"
    return AgentOutput(
        type=type_,
        content=content,
        confidence=Confidence(
            level=level,
            score=score,
            basis=basis or ["test"],
            uncertainties=[],
            requires_human_check=score < 0.8,
        ),
    )


def test_high_confidence_final_does_not_trigger_repair(tmp_path) -> None:
    runtime = SequencedRuntime([_output(OutputType.FINAL, 0.8, "good")])
    app = AgentOS.load(root=tmp_path / ".agent-os", runtime=runtime)
    app.create_agent("a1", goal="g1", model="gpt-4.1-mini")
    session = app.sessions.init("a1", "answer this")

    output = app.sessions.run(session.session_id)

    assert output.content == "good"
    assert len(runtime.calls) == 1
    assert [event.type for event in app.sessions.events(session.session_id)] == [EventType.INPUT, EventType.AGENT_OUTPUT]


def test_low_confidence_final_reruns_once_and_returns_question(tmp_path) -> None:
    runtime = SequencedRuntime(
        [
            _output(OutputType.FINAL, 0.3, "weak", ["weak"]),
            _output(OutputType.QUESTION, 0.7, "Which project constraints matter most?", ["clarification"]),
        ]
    )
    app = AgentOS.load(root=tmp_path / ".agent-os", runtime=runtime)
    app.create_agent("a1", goal="g1", model="gpt-4.1-mini")
    session = app.sessions.init("a1", "answer this")

    output = app.sessions.run(session.session_id)

    assert output.type == OutputType.QUESTION
    assert output.content == "Which project constraints matter most?"
    assert len(runtime.calls) == 2
    assert "Your previous final answer had low confidence" in runtime.calls[1]
    assert output.runtime_metadata["confidence_repair_attempted"] is True
    assert output.runtime_metadata["confidence_repair_attempts"] == 1
    assert output.runtime_metadata["initial_confidence_score"] == 0.3
    assert output.runtime_metadata["initial_confidence_basis"] == ["weak"]
    events = app.sessions.events(session.session_id)
    assert [event.type for event in events] == [EventType.INPUT, EventType.AGENT_OUTPUT]
    assert events[-1].payload["content"] == "Which project constraints matter most?"


def test_low_confidence_final_reruns_once_and_returns_improved_final(tmp_path) -> None:
    runtime = SequencedRuntime(
        [
            _output(OutputType.FINAL, 0.4, "weak", ["weak"]),
            _output(OutputType.FINAL, 0.82, "improved", ["evidence"]),
        ]
    )
    app = AgentOS.load(root=tmp_path / ".agent-os", runtime=runtime)
    app.create_agent("a1", goal="g1", model="gpt-4.1-mini")
    session = app.sessions.init("a1", "answer this")

    output = app.sessions.run(session.session_id)

    assert output.type == OutputType.FINAL
    assert output.content == "improved"
    assert output.confidence.score == 0.82
    assert len(runtime.calls) == 2
    assert output.runtime_metadata["initial_confidence_score"] == 0.4


def test_low_confidence_repair_returns_second_low_confidence_output(tmp_path) -> None:
    runtime = SequencedRuntime(
        [
            _output(OutputType.FINAL, 0.2, "weak", ["first"]),
            _output(OutputType.FINAL, 0.35, "still weak", ["second"]),
        ]
    )
    app = AgentOS.load(root=tmp_path / ".agent-os", runtime=runtime)
    app.create_agent("a1", goal="g1", model="gpt-4.1-mini")
    session = app.sessions.init("a1", "answer this")

    output = app.sessions.run(session.session_id)

    assert output.type == OutputType.FINAL
    assert output.content == "still weak"
    assert output.confidence.score == 0.35
    assert len(runtime.calls) == 2
    assert output.runtime_metadata["confidence_repair_attempts"] == 1


def test_question_and_error_do_not_trigger_repair(tmp_path) -> None:
    for output_type in [OutputType.QUESTION, OutputType.ERROR]:
        runtime = SequencedRuntime([_output(output_type, 0.1, output_type.value)])
        app = AgentOS.load(root=tmp_path / output_type.value / ".agent-os", runtime=runtime)
        app.create_agent("a1", goal="g1", model="gpt-4.1-mini")
        session = app.sessions.init("a1", "answer this")

        output = app.sessions.run(session.session_id)

        assert output.type == output_type
        assert len(runtime.calls) == 1


def test_runtime_config_confidence_repair_defaults_and_file_overrides(tmp_path) -> None:
    default_cfg = load_runtime_config(root=tmp_path / "default" / ".agent-os")
    assert default_cfg.confidence_repair_enabled is True
    assert default_cfg.confidence_threshold == 0.60
    assert default_cfg.confidence_repair_max_attempts == 1

    root = tmp_path / "configured" / ".agent-os"
    root.mkdir(parents=True)
    (root / "runtime.json").write_text(
        json.dumps(
            {
                "confidence_repair_enabled": False,
                "confidence_threshold": 0.72,
                "confidence_repair_max_attempts": 2,
            }
        ),
        encoding="utf-8",
    )

    cfg = load_runtime_config(root=root)
    assert cfg.confidence_repair_enabled is False
    assert cfg.confidence_threshold == 0.72
    assert cfg.confidence_repair_max_attempts == 2


def test_openai_runtime_low_confidence_final_repairs_with_second_call(monkeypatch, tmp_path) -> None:
    class FakeGetResponse:
        status_code = 200

        def raise_for_status(self):
            return None

    class FakeResponse:
        def __init__(self, output_text: str) -> None:
            self.output_text = output_text

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": self.output_text,
                "usage": {"input_tokens": 100, "output_tokens": 20, "reasoning_tokens": 0, "total_tokens": 120},
            }

    responses = [
        '{"type":"final","content":"Weak answer.","confidence_score":0.40,"confidence_basis":["model"],"uncertainties":["missing details"]}',
        '{"type":"question","content":"Which constraints should I use?","confidence_score":0.70,"confidence_basis":["clarification"],"uncertainties":[]}',
    ]
    seen_payloads: list[dict] = []

    def fake_post(self, url, headers, json):
        seen_payloads.append(json)
        return FakeResponse(responses[len(seen_payloads) - 1])

    def fake_get(self, url, headers):
        return FakeGetResponse()

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    app = AgentOS.load(root=tmp_path / ".agent-os", runtime_mode="openai", openai_api_key="k")
    app.create_agent("a1", goal="g1", model="gpt-4.1-mini")
    session = app.sessions.init("a1", "answer this")

    output = app.sessions.run(session.session_id)

    assert output.type == OutputType.QUESTION
    assert output.content == "Which constraints should I use?"
    assert len(seen_payloads) == 2
    assert "Your previous final answer had low confidence" in seen_payloads[1]["input"][1]["content"]
    assert output.runtime_metadata["confidence_repair_attempted"] is True
    assert output.runtime_metadata["confidence_repair_attempts"] == 1
    assert output.runtime_metadata["initial_confidence_score"] == 0.4
