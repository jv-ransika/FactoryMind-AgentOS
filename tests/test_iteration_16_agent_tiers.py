from __future__ import annotations

from typer.testing import CliRunner

from agent_os import AgentDefinition, AgentOS, AgentTier, LearningMode
from agent_os.cli.app import app


def _accepted_session(agent_os: AgentOS, agent_id: str) -> str:
    session = agent_os.sessions.init(agent_id=agent_id, input="Find low risk projects.")
    agent_os.sessions.run(session.session_id)
    agent_os.sessions.accept(session.session_id)
    return session.session_id


def test_basic_agent_context_excludes_long_term_memory(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="a1", goal="g", model="gpt-4.1-mini", agent_tier=AgentTier.BASIC_AGENT)
    agent_os.flame.memory.create(agent_id="a1", content="Long-term preference memory", tags=["risk"])
    packet = agent_os.context.build(agent_id="a1", active_input="Need risk plan")
    assert packet.selected_memories == []


def test_basic_agent_context_excludes_long_term_memory_with_existing_memory(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="a2", goal="g", model="gpt-4.1-mini", agent_tier=AgentTier.BASIC_AGENT)
    agent_os.flame.memory.create(agent_id="a2", content="Prefer low risk delivery", tags=["risk"])
    packet = agent_os.context.build(agent_id="a2", active_input="Need low risk path")
    assert packet.selected_memories == []


def test_self_learning_agent_allows_learning_and_basic_agent_forbids_learning(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="t1", goal="g", model="gpt-4.1-mini", agent_tier=AgentTier.BASIC_AGENT)
    agent_os.create_agent(agent_id="t2", goal="g", model="gpt-4.1-mini", agent_tier=AgentTier.BASIC_AGENT)
    agent_os.create_agent(
        agent_id="t3",
        goal="g",
        model="gpt-4.1-mini",
        agent_tier=AgentTier.SELF_LEARNING_AGENT,
        learning_mode=LearningMode.AUTO_LOW_RISK,
    )

    _accepted_session(agent_os, "t1")
    _accepted_session(agent_os, "t2")
    _accepted_session(agent_os, "t3")

    for blocked in ("t1", "t2"):
        try:
            agent_os.learning.run(blocked)
            assert False, f"Expected learning to be blocked for {blocked}"
        except ValueError as exc:
            assert "tier_forbids_learning" in str(exc)

    run = agent_os.learning.run("t3")
    assert run.experience_count >= 1


def test_create_agent_cli_accepts_agent_tier(tmp_path) -> None:
    runner = CliRunner()
    root = str(tmp_path / ".agent-os")
    assert runner.invoke(app, ["init", "--root", root]).exit_code == 0
    out = runner.invoke(
        app,
        [
            "create",
            "agent",
            "tier-agent",
            "--goal",
            "g",
            "--model",
            "gpt-4.1-mini",
            "--agent-tier",
            "self_learning_agent",
            "--root",
            root,
        ],
    )
    assert out.exit_code == 0
    assert '"agent_tier": "self_learning_agent"' in out.output


def test_missing_agent_tier_defaults_to_basic_agent() -> None:
    parsed = AgentDefinition.model_validate({"id": "legacy", "goal": "g", "model": "gpt-4.1-mini"})
    assert parsed.agent_tier == AgentTier.BASIC_AGENT
