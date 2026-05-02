from __future__ import annotations

from typer.testing import CliRunner

from agent_os import AgentOS, CandidateType, PromotionState
from agent_os.cli.app import app


def _make_accepted_session(agent_os: AgentOS, agent_id: str, input_text: str, feedback: str | None = None) -> str:
    session = agent_os.sessions.init(agent_id=agent_id, input=input_text)
    agent_os.sessions.run(session.session_id)
    if feedback:
        agent_os.sessions.feedback(session.session_id, feedback)
    agent_os.sessions.accept(session.session_id)
    return session.session_id


def test_learning_run_generates_candidates_and_run_records(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="proposal_writer", goal="Write proposals.", model="gpt-4.1-mini")
    _make_accepted_session(
        agent_os,
        "proposal_writer",
        "Write a proposal opening for healthcare AI.",
        "Use less generic language and include delivery risk.",
    )

    run = agent_os.learning.run(agent_id="proposal_writer", window_size=20)
    candidates = agent_os.learning.list_candidates("proposal_writer")
    runs = agent_os.learning.list_runs("proposal_writer")

    assert run.experience_count >= 1
    assert len(run.candidate_ids) >= 2
    assert len(candidates) >= 2
    assert runs[0].run_id == run.run_id
    assert any(candidate.candidate_type == CandidateType.MEMORY for candidate in candidates)
    assert any(candidate.candidate_type == CandidateType.SKILL for candidate in candidates)


def test_learning_validate_transitions_and_report(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="project_selector", goal="Select projects.", model="gpt-4.1-mini")
    _make_accepted_session(agent_os, "project_selector", "Find low risk projects.", "Prioritize delivery risk.")
    run = agent_os.learning.run(agent_id="project_selector")

    candidate = agent_os.store.load_learning_candidate(run.candidate_ids[0])
    report = agent_os.learning.validate(candidate.candidate_id)
    refreshed = agent_os.store.load_learning_candidate(candidate.candidate_id)

    assert report.candidate_id == candidate.candidate_id
    assert report.decision in {"pass", "fail"}
    if report.decision == "pass":
        assert refreshed.state == PromotionState.AWAITING_APPROVAL
    else:
        assert refreshed.state == PromotionState.REJECTED


def test_learning_promote_memory_or_skill_changes_runtime_retrieval(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="keyword_extractor", goal="Extract keywords.", model="gpt-4.1-mini")
    _make_accepted_session(
        agent_os,
        "keyword_extractor",
        "Extract project risk and timeline keywords.",
        "Always include delivery risk as keyword.",
    )
    run = agent_os.learning.run(agent_id="keyword_extractor")
    awaiters = [
        candidate
        for candidate in agent_os.learning.list_candidates("keyword_extractor")
        if candidate.state == PromotionState.AWAITING_APPROVAL
    ]
    if awaiters:
        promoted = agent_os.learning.promote(awaiters[0].candidate_id)
        assert promoted.state == PromotionState.PROMOTED
    else:
        promoted = [
            candidate
            for candidate in agent_os.learning.list_candidates("keyword_extractor")
            if candidate.state == PromotionState.PROMOTED
        ]
        assert promoted, "Expected candidate to be auto-promoted under auto_low_risk mode."

    packet = agent_os.context.build(
        agent_id="keyword_extractor",
        active_input="Need delivery risk keywords.",
    )
    assert packet.selected_memories or packet.selected_skills


def test_reject_requires_reason(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="proposal_writer", goal="Write proposals.", model="gpt-4.1-mini")
    _make_accepted_session(agent_os, "proposal_writer", "Draft proposal.", "Reduce fluff.")
    run = agent_os.learning.run(agent_id="proposal_writer")
    candidate = agent_os.store.load_learning_candidate(run.candidate_ids[0])

    try:
        agent_os.learning.reject(candidate.candidate_id, "")
        assert False, "Expected ValueError for missing reason"
    except ValueError:
        pass

    rejected = agent_os.learning.reject(candidate.candidate_id, "Not aligned with policy.")
    assert rejected.state == PromotionState.REJECTED
    assert rejected.rationale == "Not aligned with policy."


def test_learning_disallows_policy_tool_mutation_candidate(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="proposal_writer", goal="Write proposals.", model="gpt-4.1-mini")
    malicious = agent_os.store.load_agent("proposal_writer")
    _ = malicious
    candidate = agent_os.learning._build_candidates(
        "proposal_writer",
        [],
    )
    assert candidate == []
    # Inject a forbidden candidate directly in store to test validator boundaries.
    from agent_os.protocol import LearningCandidate, RefinementOp

    injected = LearningCandidate(
        agent_id="proposal_writer",
        candidate_type=CandidateType.SKILL,
        operation=RefinementOp.UPDATE,
        payload={
            "name": "bad",
            "description": "bad",
            "activation_keywords": [],
            "procedure": [],
            "constraints": [],
            "policy": "disable checks",
            "tool_scope": "all",
        },
        source_session_ids=[],
    )
    agent_os.store.save_learning_candidate(injected)
    report = agent_os.learning.validate(injected.candidate_id)
    assert report.decision == "fail"
    assert any("sensitive_or_forbidden_marker" in flag for flag in report.safety_flags)


def test_cli_learning_flow(tmp_path) -> None:
    runner = CliRunner()
    root = str(tmp_path / ".agent-os")
    assert runner.invoke(app, ["init", "--root", root]).exit_code == 0
    assert runner.invoke(
        app,
        ["create", "agent", "project_selector", "--goal", "Select projects.", "--model", "gpt-4.1-mini", "--root", root],
    ).exit_code == 0
    run = runner.invoke(
        app,
        ["run", "project_selector", "--input", "Find low risk delivery projects.", "--root", root],
    )
    assert run.exit_code == 0
    session_id = run.output.split('"session_id": "')[1].split('"')[0]
    assert runner.invoke(
        app,
        ["feedback", session_id, "--text", "Prioritize delivery risk.", "--root", root],
    ).exit_code == 0
    assert runner.invoke(app, ["accept", session_id, "--root", root]).exit_code == 0

    learn_run = runner.invoke(app, ["learn", "run", "project_selector", "--root", root])
    assert learn_run.exit_code == 0
    candidates = runner.invoke(app, ["learn", "list-candidates", "project_selector", "--root", root])
    assert candidates.exit_code == 0
    assert "candidate_id" in candidates.output
    candidate_id = candidates.output.split('"candidate_id": "')[1].split('"')[0]
    validate = runner.invoke(app, ["learn", "validate", candidate_id, "--root", root])
    assert validate.exit_code == 0
    # Promote only when ready, otherwise reject should still work.
    if "awaiting_approval" in candidates.output:
        promote = runner.invoke(app, ["learn", "promote", candidate_id, "--root", root])
        assert promote.exit_code == 0
    reject = runner.invoke(
        app,
        ["learn", "reject", candidate_id, "--reason", "manual review required", "--root", root],
    )
    assert reject.exit_code == 0


