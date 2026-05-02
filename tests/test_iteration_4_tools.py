from __future__ import annotations

from typer.testing import CliRunner

from agent_os import AgentOS, ToolCallStatus, ToolManifest, ToolScope
from agent_os.cli.app import app


def _setup_agent(tmp_path):
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="project_selector", goal="Select projects.", model="gpt-4.1-mini")
    return agent_os


def test_tool_manifest_register_and_list(tmp_path) -> None:
    agent_os = _setup_agent(tmp_path)
    manifest = ToolManifest(
        name="project_db.search",
        scope=ToolScope.READ,
        input_schema={"type": "object", "required": ["query"], "properties": {"query": {"type": "string"}}},
        output_schema={"type": "object"},
    )
    created = agent_os.tools.register(manifest)
    all_tools = agent_os.tools.list()
    assert created.tool_id in [tool.tool_id for tool in all_tools]


def test_tool_allowlist_enforcement_denies_unbound(tmp_path) -> None:
    agent_os = _setup_agent(tmp_path)
    manifest = agent_os.tools.register_from_fields(name="project_db.search", scope=ToolScope.READ)
    result, audit = agent_os.tools.call(
        agent_id="project_selector",
        session_id=None,
        tool_id=manifest.tool_id,
        args={"query": "ai"},
    )
    assert result.status == ToolCallStatus.DENIED
    assert audit.error_code == "tool_not_bound"


def test_tool_scope_enforcement_write_denied_by_default(tmp_path) -> None:
    agent_os = _setup_agent(tmp_path)
    manifest = agent_os.tools.register_from_fields(name="project_db.update", scope=ToolScope.WRITE)
    agent_os.tools.bind("project_selector", manifest.tool_id)
    result, audit = agent_os.tools.call(
        agent_id="project_selector",
        session_id=None,
        tool_id=manifest.tool_id,
        args={"id": "p1", "status": "active"},
    )
    assert result.status == ToolCallStatus.DENIED
    assert audit.error_code == "write_scope_denied"


def test_tool_schema_validation_pass_and_fail(tmp_path) -> None:
    agent_os = _setup_agent(tmp_path)
    manifest = agent_os.tools.register_from_fields(
        name="project_db.search",
        scope=ToolScope.READ,
        input_schema={
            "type": "object",
            "required": ["query"],
            "properties": {"query": {"type": "string"}},
            "additionalProperties": False,
        },
    )
    agent_os.tools.bind("project_selector", manifest.tool_id)

    success, _ = agent_os.tools.call(
        agent_id="project_selector",
        session_id=None,
        tool_id=manifest.tool_id,
        args={"query": "healthcare ai"},
    )
    fail, _ = agent_os.tools.call(
        agent_id="project_selector",
        session_id=None,
        tool_id=manifest.tool_id,
        args={"unexpected": "x"},
    )

    assert success.status == ToolCallStatus.SUCCESS
    assert fail.status == ToolCallStatus.INVALID
    assert fail.error_code and fail.error_code.startswith("missing_required:")


def test_tool_timeout_and_output_sanitization(tmp_path) -> None:
    agent_os = _setup_agent(tmp_path)
    manifest = agent_os.tools.register_from_fields(
        name="project_db.search",
        scope=ToolScope.READ,
        input_schema={"type": "object", "properties": {}, "additionalProperties": True},
        timeout_ms=100,
    )
    agent_os.tools.bind("project_selector", manifest.tool_id)

    timeout_result, timeout_audit = agent_os.tools.call(
        agent_id="project_selector",
        session_id=None,
        tool_id=manifest.tool_id,
        args={"_sleep_ms": 1000},
    )
    sanit_result, sanit_audit = agent_os.tools.call(
        agent_id="project_selector",
        session_id=None,
        tool_id=manifest.tool_id,
        args={"_dangerous_output": True},
    )

    assert timeout_result.status == ToolCallStatus.TIMEOUT
    assert timeout_audit.error_code == "timeout"
    assert sanit_result.status == ToolCallStatus.SUCCESS
    assert sanit_result.sanitized_output is not None
    assert sanit_result.sanitized_output.get("note") == "[SANITIZED_TOOL_OUTPUT]"
    assert sanit_audit.sanitization_applied is True


def test_tool_audit_persistence_and_query(tmp_path) -> None:
    agent_os = _setup_agent(tmp_path)
    manifest = agent_os.tools.register_from_fields(name="project_db.search", scope=ToolScope.READ)
    agent_os.tools.bind("project_selector", manifest.tool_id)
    session = agent_os.sessions.init(agent_id="project_selector", input="find projects")
    agent_os.tools.call(
        agent_id="project_selector",
        session_id=session.session_id,
        tool_id=manifest.tool_id,
        args={"query": "risk"},
    )
    all_audits = agent_os.tools.audit("project_selector")
    session_audits = agent_os.tools.audit("project_selector", session_id=session.session_id)
    assert all_audits
    assert session_audits
    assert all(audit.agent_id == "project_selector" for audit in all_audits)


def test_tool_result_enters_context_as_summary_only(tmp_path) -> None:
    agent_os = _setup_agent(tmp_path)
    manifest = agent_os.tools.register_from_fields(name="project_db.search", scope=ToolScope.READ)
    agent_os.tools.bind("project_selector", manifest.tool_id)
    session = agent_os.sessions.init(agent_id="project_selector", input="find projects")
    agent_os.tools.call(
        agent_id="project_selector",
        session_id=session.session_id,
        tool_id=manifest.tool_id,
        args={"_dangerous_output": True},
    )
    events = agent_os.sessions.events(session.session_id)
    packet = agent_os.context.build(
        agent_id="project_selector",
        active_input="find projects",
        events=events,
    )
    assert packet.tool_evidence
    joined = str(packet.tool_evidence).lower()
    assert "ignore previous instructions" not in joined
    assert "result_keys" in joined


def test_learning_still_works_with_tool_enabled_sessions(tmp_path) -> None:
    agent_os = _setup_agent(tmp_path)
    manifest = agent_os.tools.register_from_fields(name="project_db.search", scope=ToolScope.READ)
    agent_os.tools.bind("project_selector", manifest.tool_id)
    session = agent_os.sessions.init(agent_id="project_selector", input="find projects")
    agent_os.tools.call(
        agent_id="project_selector",
        session_id=session.session_id,
        tool_id=manifest.tool_id,
        args={"query": "ai"},
    )
    agent_os.sessions.feedback(session.session_id, "prioritize low risk")
    agent_os.sessions.accept(session.session_id)
    run = agent_os.learning.run(agent_id="project_selector")
    assert run.experience_count >= 1
    assert run.candidate_ids


def test_cli_tools_flow(tmp_path) -> None:
    runner = CliRunner()
    root = str(tmp_path / ".agent-os")
    assert runner.invoke(app, ["init", "--root", root]).exit_code == 0
    assert runner.invoke(
        app,
        ["create", "agent", "project_selector", "--goal", "Select projects.", "--model", "gpt-4.1-mini", "--root", root],
    ).exit_code == 0
    created = runner.invoke(
        app,
        [
            "create",
            "tool",
            "project_db.search",
            "--scope",
            "read",
            "--input-schema",
            '{"type":"object","required":["query"],"properties":{"query":{"type":"string"}}}',
            "--output-schema",
            '{"type":"object"}',
            "--root",
            root,
        ],
    )
    assert created.exit_code == 0
    tool_id = created.output.split('"tool_id": "')[1].split('"')[0]
    assert runner.invoke(
        app,
        ["bind", "tool", "project_selector", tool_id, "--root", root],
    ).exit_code == 0
    listed = runner.invoke(app, ["list", "tools", "--root", root])
    assert listed.exit_code == 0
    assert "project_db.search" in listed.output
    call = runner.invoke(
        app,
        [
            "tool",
            "call",
            "project_selector",
            tool_id,
            "--args",
            '{"query":"ai"}',
            "--root",
            root,
        ],
    )
    assert call.exit_code == 0
    assert '"status": "success"' in call.output
    audit = runner.invoke(app, ["tool", "audit", "project_selector", "--root", root])
    assert audit.exit_code == 0
    assert "request_hash" in audit.output


