from __future__ import annotations

import json
from pathlib import Path

from agent_os import AgentOS, ToolManifest, ToolScope


def main() -> None:
    """Expected output contract:
    {
      "agent_id": str,
      "session_id": str,
      "output_type": "question|final|error",
      "tool_status": "success|error|timeout|denied|invalid"
    }
    """
    root = Path(".agent-os-example-keywords")
    app = AgentOS.load(root=root, runtime_mode="local")
    app.create_agent(
        agent_id="keyword-agent",
        goal="Extract decision-critical keywords from user text.",
        model="gpt-4.1-mini",
        tenant_id="default",
    )
    skill = app.skills.create(
        name="keyword_extraction",
        description="Extract concise keyword set from task statement.",
        owner_agent_id="keyword-agent",
        activation_keywords=["keyword", "extract", "terms"],
        procedure=["Read text", "Extract core nouns and intent words", "Return concise list"],
        constraints=["Do not invent terms not present in the input."],
    )
    app.skills.bind("keyword-agent", skill.skill_id)

    tool = app.tools.register(
        ToolManifest(
            name="keyword_audit",
            scope=ToolScope.READ,
            input_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
                "additionalProperties": False,
            },
            output_schema={"type": "object"},
        )
    )
    app.tools.bind("keyword-agent", tool.tool_id)

    session = app.sessions.init("keyword-agent", "Extract keywords from: AI governance for project selection.")
    output = app.sessions.run(session.session_id)
    result, _audit = app.tools.call(
        agent_id="keyword-agent",
        session_id=session.session_id,
        tool_id=tool.tool_id,
        args={"text": "AI governance for project selection"},
    )
    print(
        json.dumps(
            {
                "agent_id": "keyword-agent",
                "session_id": session.session_id,
                "output_type": output.type.value,
                "tool_status": result.status.value,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
