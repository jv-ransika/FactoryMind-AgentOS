from __future__ import annotations

from typer.testing import CliRunner

from agent_os import AgentOS, AgentTier, PromotionMode, PromotionPolicy
from agent_os.cli.app import app


def _accepted(agent_os: AgentOS, agent_id: str, text: str, feedback: str) -> str:
    session = agent_os.sessions.init(agent_id=agent_id, input=text)
    agent_os.sessions.run(session.session_id)
    agent_os.sessions.feedback(session.session_id, feedback)
    agent_os.sessions.accept(session.session_id)
    return session.session_id


def test_policy_default_and_set_get(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(
        agent_id="project_selector",
        goal="Select projects.",
        model="gpt-4.1-mini",
        agent_tier=AgentTier.SELF_LEARNING_AGENT,
    )
    default_policy = agent_os.learning.get_policy("project_selector")
    assert default_policy.mode == PromotionMode.AUTO_LOW_RISK
    assert default_policy.min_quality_delta == 0.02

    updated = agent_os.learning.set_policy(
        "project_selector",
        PromotionPolicy(
            agent_id="project_selector",
            mode=PromotionMode.SUGGEST_ONLY,
            max_safety_failures=0,
            max_regression_warnings=1,
            min_confidence=0.6,
            min_quality_delta=0.02,
        ),
    )
    loaded = agent_os.learning.get_policy("project_selector")
    assert updated.mode == PromotionMode.SUGGEST_ONLY
    assert loaded.mode == PromotionMode.SUGGEST_ONLY


def test_learning_run_compatibility_alias_and_removed_candidate_ops(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(
        agent_id="proposal_writer",
        goal="Write proposals.",
        model="gpt-4.1-mini",
        agent_tier=AgentTier.SELF_LEARNING_AGENT,
    )
    _accepted(
        agent_os,
        "proposal_writer",
        "Write proposal opening for manufacturing AI rollout.",
        "Use concise language and mention delivery risk.",
    )
    run = agent_os.learning.run(agent_id="proposal_writer")
    assert run.candidate_ids == []
    assert "FLAME trigger executed" in run.summary

    for call in (
        lambda: agent_os.learning.evaluate("cand_x"),
        lambda: agent_os.learning.promote("cand_x"),
        lambda: agent_os.learning.rollback("cand_x", "manual rollback"),
    ):
        try:
            call()
            assert False, "Expected candidate-era API removal error"
        except ValueError as exc:
            assert "learning_candidates_removed_in_v1_2_0" in str(exc)


def test_cli_policy_and_removed_candidate_commands(tmp_path) -> None:
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
    set_policy = runner.invoke(
        app,
        [
            "learn",
            "policy",
            "set",
            "project_selector",
            "--mode",
            "auto_low_risk",
            "--min-quality-delta",
            "0.02",
            "--root",
            root,
        ],
    )
    assert set_policy.exit_code == 0
    get_policy = runner.invoke(app, ["learn", "policy", "get", "project_selector", "--root", root])
    assert get_policy.exit_code == 0
    assert '"mode": "auto_low_risk"' in get_policy.output

    removed = runner.invoke(app, ["learn", "evaluate", "cand_x", "--root", root])
    assert removed.exit_code != 0

