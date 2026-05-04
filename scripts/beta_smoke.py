from __future__ import annotations

import shutil
from pathlib import Path

from agent_os import AgentOS, AgentTier, ToolManifest, ToolScope


def run_smoke(root: Path) -> dict:
    if root.exists():
        shutil.rmtree(root)

    app = AgentOS.load(root=root, runtime_mode="local")
    agent = app.create_agent(
        agent_id="beta-agent",
        goal="Validate beta flow",
        model="gpt-4.1-mini",
        tenant_id="default",
        agent_tier=AgentTier.SELF_LEARNING_AGENT,
    )

    session = app.sessions.init(agent_id=agent.id, input="Write a short proposal for Project X")
    first_output = app.sessions.run(session.session_id)
    app.sessions.feedback(session.session_id, "Keep it concise and include expected timeline.")
    second_output = app.sessions.run(session.session_id)
    app.sessions.accept(session.session_id, note="Accepted for pilot smoke")

    learn_run = app.learning.run(agent_id=agent.id, window_size=10)
    runs = app.flame.list_runs(agent.id)
    if not runs:
        raise RuntimeError("No FLAME reflection run generated in smoke flow.")
    memories = app.memory.list(agent.id)
    reflected = [m for m in memories if m.metadata.get("created_by") == "flame_reflection"]
    if not reflected:
        raise RuntimeError("No reflected long-term memory created in smoke flow.")

    manifest = app.tools.register(
        ToolManifest(
            name="beta_read_tool",
            scope=ToolScope.READ,
            description="Smoke tool",
            input_schema={
                "type": "object",
                "properties": {"q": {"type": "string"}},
                "required": ["q"],
                "additionalProperties": False,
            },
            output_schema={"type": "object"},
        )
    )
    app.tools.bind(agent_id=agent.id, tool_id=manifest.tool_id)
    tool_result, tool_audit = app.tools.call(
        agent_id=agent.id,
        session_id=session.session_id,
        tool_id=manifest.tool_id,
        args={"q": "status"},
    )
    audits = app.tools.audit(agent_id=agent.id, session_id=session.session_id)
    if not audits:
        raise RuntimeError("No tool audit records found in smoke flow.")

    return {
        "agent_id": agent.id,
        "session_id": session.session_id,
        "first_output_type": first_output.type.value,
        "second_output_type": second_output.type.value,
        "learning_run_id": learn_run.run_id,
        "reflected_memory_id": reflected[0].memory_id,
        "tool_status": tool_result.status.value,
        "audit_id": tool_audit.audit_id,
    }


if __name__ == "__main__":
    result = run_smoke(Path(".agent-os-beta-smoke"))
    print(result)
