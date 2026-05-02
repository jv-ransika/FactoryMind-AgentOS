from __future__ import annotations

import json
from pathlib import Path

from agent_os import AgentOS


def main() -> None:
    """Expected output contract:
    {
      "agent_id": str,
      "session_id": str,
      "output_type": "question|final|error",
      "output_preview": str
    }
    """
    root = Path(".agent-os-example-proposal")
    app = AgentOS.load(root=root, runtime_mode="local")
    app.create_agent(
        agent_id="proposal-agent",
        goal="Draft client-ready proposals.",
        model="gpt-4.1-mini",
        tenant_id="default",
    )
    session = app.sessions.init("proposal-agent", "Write a short proposal for warehouse automation.")
    output = app.sessions.run(session.session_id)
    app.sessions.feedback(session.session_id, "Keep total length under 250 words.")
    app.sessions.accept(session.session_id, note="Approved for proposal template.")
    print(
        json.dumps(
            {
                "agent_id": "proposal-agent",
                "session_id": session.session_id,
                "output_type": output.type.value,
                "output_preview": output.content[:120],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
