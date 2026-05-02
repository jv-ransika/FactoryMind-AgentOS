from __future__ import annotations

import json
from pathlib import Path

from agent_os import AgentOS, McpServerConfig, ToolScope


def main() -> None:
    """Expected output contract:
    {
      "agent_id": str,
      "registered_mcp_tool_id": str,
      "bound": bool,
      "note": str
    }
    """
    root = Path(".agent-os-example-project-selection")
    app = AgentOS.load(root=root, runtime_mode="local")
    app.create_agent(
        agent_id="project-selection-agent",
        goal="Select best-fit project using MCP-backed project database queries.",
        model="gpt-4.1-mini",
        tenant_id="default",
    )

    # MCP-backed query pattern: register server + map tool manifest to remote MCP tool.
    app.tools.mcp.add(
        McpServerConfig(
            name="project-db",
            endpoint="http://localhost:9010",
            transport="http",
            enabled=True,
        )
    )
    manifest = app.tools.register_mcp_tool(
        name="query_projects",
        mcp_server="project-db",
        mcp_tool_name="projects.query",
        scope=ToolScope.READ,
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
    )
    app.tools.bind("project-selection-agent", manifest.tool_id)
    print(
        json.dumps(
            {
                "agent_id": "project-selection-agent",
                "registered_mcp_tool_id": manifest.tool_id,
                "bound": True,
                "note": "MCP mapping registered. Run against live MCP service in deployment.",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
