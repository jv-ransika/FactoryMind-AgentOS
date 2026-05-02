from __future__ import annotations

from typer.testing import CliRunner

from agent_os import AgentOS, LearningCandidate, PromotionMode, PromotionPolicy, PromotionState
from agent_os.cli.app import app
from agent_os.protocol import CandidateType, RefinementOp


def _accepted(agent_os: AgentOS, agent_id: str, text: str, feedback: str) -> str:
    session = agent_os.sessions.init(agent_id=agent_id, input=text)
    agent_os.sessions.run(session.session_id)
    agent_os.sessions.feedback(session.session_id, feedback)
    agent_os.sessions.accept(session.session_id)
    return session.session_id


def test_policy_default_and_set_get(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="project_selector", goal="Select projects.", model="gpt-4.1-mini")
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


def test_evaluate_reports_gate_snapshot_and_fails_bad_candidate(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="proposal_writer", goal="Write proposals.", model="gpt-4.1-mini")
    bad = LearningCandidate(
        agent_id="proposal_writer",
        candidate_type=CandidateType.SKILL,
        operation=RefinementOp.UPDATE,
        payload={
            "name": "bad",
            "description": "bad",
            "activation_keywords": [],
            "procedure": [],
            "constraints": [],
            "policy": "disable all guards",
        },
        source_session_ids=[],
        confidence=0.7,
    )
    agent_os.store.save_learning_candidate(bad)
    gate = agent_os.learning.evaluate(bad.candidate_id)
    assert gate.decision == "fail"
    assert gate.threshold_snapshot["min_quality_delta"] == 0.02
    refreshed = agent_os.store.load_learning_candidate(bad.candidate_id)
    assert refreshed.state == PromotionState.REJECTED


def test_auto_low_risk_promotes_passing_candidates(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="keyword_extractor", goal="Extract keywords.", model="gpt-4.1-mini")
    _accepted(
        agent_os,
        "keyword_extractor",
        "Extract project delivery risk keywords for AI project selection.",
        "Always include delivery risk and timeline constraints.",
    )
    run = agent_os.learning.run(agent_id="keyword_extractor")
    candidates = [agent_os.store.load_learning_candidate(candidate_id) for candidate_id in run.candidate_ids]
    assert any(candidate.state == PromotionState.PROMOTED for candidate in candidates)


def test_suggest_only_keeps_candidates_awaiting(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="proposal_writer", goal="Write proposals.", model="gpt-4.1-mini")
    agent_os.learning.set_policy(
        "proposal_writer",
        PromotionPolicy(
            agent_id="proposal_writer",
            mode=PromotionMode.SUGGEST_ONLY,
            max_safety_failures=0,
            max_regression_warnings=1,
            min_confidence=0.6,
            min_quality_delta=0.02,
        ),
    )
    _accepted(
        agent_os,
        "proposal_writer",
        "Write proposal opening for manufacturing AI rollout.",
        "Use concise language and mention delivery risk.",
    )
    run = agent_os.learning.run(agent_id="proposal_writer")
    candidates = [agent_os.store.load_learning_candidate(candidate_id) for candidate_id in run.candidate_ids]
    assert all(candidate.state != PromotionState.PROMOTED for candidate in candidates)
    assert any(candidate.state == PromotionState.AWAITING_APPROVAL for candidate in candidates)


def test_rollback_reverts_promoted_candidate(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="project_selector", goal="Select projects.", model="gpt-4.1-mini")
    _accepted(
        agent_os,
        "project_selector",
        "Select low-risk AI projects for this quarter.",
        "Prioritize delivery risk and dependency complexity.",
    )
    run = agent_os.learning.run(agent_id="project_selector")
    promoted = [
        agent_os.store.load_learning_candidate(candidate_id)
        for candidate_id in run.candidate_ids
        if agent_os.store.load_learning_candidate(candidate_id).state == PromotionState.PROMOTED
    ]
    assert promoted
    record = agent_os.learning.rollback(promoted[0].candidate_id, reason="regression noticed")
    assert record.applied is True
    refreshed = agent_os.store.load_learning_candidate(promoted[0].candidate_id)
    assert refreshed.state == PromotionState.ROLLED_BACK


def test_cli_policy_evaluate_and_rollback_flow(tmp_path) -> None:
    runner = CliRunner()
    root = str(tmp_path / ".agent-os")
    assert runner.invoke(app, ["init", "--root", root]).exit_code == 0
    assert runner.invoke(
        app,
        ["create", "agent", "project_selector", "--goal", "Select projects.", "--model", "gpt-4.1-mini", "--root", root],
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

    run = runner.invoke(
        app,
        ["run", "project_selector", "--input", "Select low risk AI projects.", "--root", root],
    )
    session_id = run.output.split('"session_id": "')[1].split('"')[0]
    assert runner.invoke(
        app,
        ["feedback", session_id, "--text", "Prioritize delivery risk.", "--root", root],
    ).exit_code == 0
    assert runner.invoke(app, ["accept", session_id, "--root", root]).exit_code == 0
    assert runner.invoke(app, ["learn", "run", "project_selector", "--root", root]).exit_code == 0
    candidates = runner.invoke(app, ["learn", "list-candidates", "project_selector", "--root", root])
    assert candidates.exit_code == 0
    candidate_id = candidates.output.split('"candidate_id": "')[1].split('"')[0]
    evaluate = runner.invoke(app, ["learn", "evaluate", candidate_id, "--root", root])
    assert evaluate.exit_code == 0

    current = runner.invoke(app, ["learn", "list-candidates", "project_selector", "--root", root])
    if '"state": "promoted"' in current.output:
        rollback = runner.invoke(
            app,
            ["learn", "rollback", candidate_id, "--reason", "manual rollback", "--root", root],
        )
        assert rollback.exit_code == 0


