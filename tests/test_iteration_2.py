from __future__ import annotations

from typer.testing import CliRunner

from agent_os import AgentOS, AgentTier, OutputType, ResourceStatus
from agent_os.cli.app import app


def test_memory_sdk_create_list_retrieve(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="project_selector", goal="Select projects.", model="gpt-4.1-mini")

    memory = agent_os.memory.create(
        agent_id="project_selector",
        content="Company prefers low-risk AI projects.",
        tags=["risk", "project"],
    )
    memories = agent_os.memory.list("project_selector")
    retrieved = agent_os.memory.retrieve("project_selector", "Find a low risk project")

    assert memories == [memory]
    assert retrieved == []


def test_skill_sdk_create_list_retrieve(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="proposal_writer", goal="Write proposals.", model="gpt-4.1-mini")

    skill = agent_os.skills.create(
        name="proposal_opening",
        description="Write proposal openings in company tone.",
        bind_agent_id="proposal_writer",
        activation_keywords=["proposal", "opening"],
        procedure=["Use client language.", "State the business problem."],
    )
    skills = agent_os.skills.list("proposal_writer")
    retrieved = agent_os.skills.retrieve("proposal_writer", "Draft a proposal opening")

    assert skills == [skill]
    assert retrieved[0].skill.skill_id == skill.skill_id
    assert "proposal" in retrieved[0].retrieval.matched_terms


def test_context_assembly_includes_active_matching_memory_and_skill(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(
        agent_id="keyword_extractor",
        goal="Extract keywords.",
        model="gpt-4.1-mini",
        agent_tier=AgentTier.SELF_LEARNING_AGENT,
    )
    active_memory = agent_os.memory.create(
        agent_id="keyword_extractor",
        content="Always include project delivery risk as a keyword.",
        tags=["delivery", "risk"],
    )
    inactive_memory = agent_os.memory.create(
        agent_id="keyword_extractor",
        content="Deprecated keyword guidance about budget.",
        status=ResourceStatus.DEPRECATED,
    )
    packet = agent_os.context.build(
        agent_id="keyword_extractor",
        active_input="Extract delivery risk keywords from this project.",
    )

    assert packet.active_input == "Extract delivery risk keywords from this project."
    assert packet.selected_memories == []
    assert inactive_memory.memory_id not in [item.item.memory_id for item in packet.selected_memories]


def test_context_preserves_latest_feedback(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(
        agent_id="project_selector",
        goal="Select projects.",
        model="gpt-4.1-mini",
        agent_tier=AgentTier.SELF_LEARNING_AGENT,
    )
    session = agent_os.sessions.init(agent_id="project_selector", input="Find a project.")
    agent_os.sessions.feedback(session.session_id, "Prefer lower delivery risk.")

    events = agent_os.sessions.events(session.session_id)
    packet = agent_os.context.build(
        agent_id="project_selector",
        active_input="Find a project.",
        events=events,
    )

    assert packet.latest_feedback == "Prefer lower delivery risk."
    assert packet.active_input == "Find a project."


def test_local_runtime_uses_context_counts(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(
        agent_id="project_selector",
        goal="Select projects.",
        model="gpt-4.1-mini",
        agent_tier=AgentTier.SELF_LEARNING_AGENT,
    )
    agent_os.memory.create(
        agent_id="project_selector",
        content="Company prefers low-risk projects.",
        tags=["risk"],
    )
    session = agent_os.sessions.init(agent_id="project_selector", input="Find a low risk project.")
    output = agent_os.sessions.run(session.session_id)

    assert output.type == OutputType.FINAL
    assert "Context selected 0 memory item(s)." in output.content
    assert output.confidence.requires_human_check is True


def test_cli_memory_skill_context_flow(tmp_path) -> None:
    runner = CliRunner()
    root = str(tmp_path / ".agent-os")

    assert runner.invoke(app, ["init", "--root", root]).exit_code == 0
    assert runner.invoke(
        app,
        ["create", "agent", "project_selector", "--goal", "Select projects.", "--model", "gpt-4.1-mini", "--root", root],
    ).exit_code == 0
    assert runner.invoke(
        app,
        [
            "create",
            "memory",
            "project_selector",
            "--content",
            "Prefer projects with low delivery risk.",
            "--tags",
            "risk,delivery",
            "--root",
            root,
        ],
    ).exit_code == 0
    memories = runner.invoke(app, ["list", "memories", "project_selector", "--root", root])
    context = runner.invoke(
        app,
        ["context", "project_selector", "--input", "Find low risk delivery projects.", "--root", root],
    )

    assert memories.exit_code == 0
    assert "Prefer projects with low delivery risk." in memories.output
    assert context.exit_code == 0
    assert "selected_memories" in context.output


def test_skill_reusable_across_agents(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="proposal_writer", goal="Write proposals.", model="gpt-4.1-mini")
    agent_os.create_agent(agent_id="project_selector", goal="Select projects.", model="gpt-4.1-mini")

    skill = agent_os.skills.create(
        name="risk_awareness",
        description="Apply risk-awareness guidance.",
        activation_keywords=["risk"],
    )
    agent_os.skills.bind("proposal_writer", skill.skill_id)
    agent_os.skills.bind("project_selector", skill.skill_id)

    proposal_skills = agent_os.skills.list("proposal_writer")
    project_skills = agent_os.skills.list("project_selector")
    assert proposal_skills[0].skill_id == skill.skill_id
    assert project_skills[0].skill_id == skill.skill_id


