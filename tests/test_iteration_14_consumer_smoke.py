from __future__ import annotations

import json
from pathlib import Path

from agent_os import AgentOS


def test_consumer_embedded_app_smoke(tmp_path: Path) -> None:
    root = tmp_path / ".agent-os"
    out_file = tmp_path / "agent_output.json"
    app = AgentOS.load(root=root, runtime_mode="local")
    app.create_agent(
        agent_id="consumer-a1",
        goal="consumer smoke",
        model="gpt-4.1-mini",
        tenant_id="default",
    )
    session = app.sessions.init("consumer-a1", "hello consumer")
    output = app.sessions.run(session.session_id)
    out_file.write_text(json.dumps(output.model_dump(mode="json"), indent=2), encoding="utf-8")
    assert out_file.exists()
    loaded = json.loads(out_file.read_text(encoding="utf-8"))
    assert loaded["type"] in {"question", "final", "error"}
