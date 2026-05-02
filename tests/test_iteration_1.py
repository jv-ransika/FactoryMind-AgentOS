from __future__ import annotations

from typer.testing import CliRunner

from agent_os import AgentOS, LearningMode, OutputType
from agent_os.cli.app import app
from agent_os.protocol import EventType


def test_imports() -> None:
    assert AgentOS is not None
    assert LearningMode.COLLECT_ONLY == "collect_only"


def test_sdk_session_loop(tmp_path) -> None:
    root = tmp_path / ".agent-os"
    agent_os = AgentOS.load(root=root)
    agent = agent_os.create_agent(
        agent_id="project_selector",
        goal="Select the best project using company criteria.",
        model="gpt-4.1-mini",
    )

    session = agent_os.sessions.init(agent_id=agent.id, input="Find the best AI project.")
    output = agent_os.sessions.run(session.session_id)
    feedback_event = agent_os.sessions.feedback(session.session_id, "Prefer lower risk.")
    acceptance_event = agent_os.sessions.accept(session.session_id)
    events = agent_os.sessions.events(session.session_id)

    assert output.type == OutputType.FINAL
    assert output.confidence.level in {"low", "medium", "high"}
    assert output.confidence.requires_human_check is True
    assert feedback_event.type == EventType.FEEDBACK
    assert acceptance_event.type == EventType.ACCEPTANCE
    assert [event.type for event in events] == [
        EventType.INPUT,
        EventType.AGENT_OUTPUT,
        EventType.FEEDBACK,
        EventType.ACCEPTANCE,
    ]


def test_empty_input_returns_question(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="proposal_writer", goal="Write proposals.", model="gpt-4.1-mini")

    session = agent_os.sessions.init(agent_id="proposal_writer", input="")
    output = agent_os.sessions.run(session.session_id)

    assert output.type == OutputType.QUESTION
    assert output.confidence.score < 0.5


def test_cli_smoke_flow(tmp_path) -> None:
    runner = CliRunner()
    root = str(tmp_path / ".agent-os")

    result = runner.invoke(app, ["init", "--root", root])
    assert result.exit_code == 0

    result = runner.invoke(
        app,
        [
            "create",
            "agent",
            "keyword_extractor",
            "--goal",
            "Extract reusable project keywords.",
            "--model", "gpt-4.1-mini", "--root",
            root,
        ],
    )
    assert result.exit_code == 0

    result = runner.invoke(
        app,
        [
            "run",
            "keyword_extractor",
            "--input",
            "Extract keywords from this project description.",
            "--root",
            root,
        ],
    )
    assert result.exit_code == 0
    assert "session_id" in result.output
    assert "confidence" in result.output


