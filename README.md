# FactoryMind AgentOS

FactoryMind AgentOS is a Python library for building reusable, reliable, self-improving agents with a typed runtime contract.

Current status: `v1.3.0` (stable).

## Install

```bash
pip install agent-os==1.3.0
```

For local repo usage:

```bash
pip install -e .
```

## Stable Core API

- `AgentOS`
- `AgentOS.load(...)`
- `AgentOS.create_agent(...)`
- `AgentOS.sessions`
- `AgentOS.memory`
- `AgentOS.learning`
- `AgentOS.flame`
- `AgentOS.tools`
- `AgentOS.capabilities`
- `AgentOS.monitor`
- Core models: `AgentDefinition`, `Session`, `SessionEvent`, `AgentOutput`, `MemoryItem`, `LearningRun`, `ToolManifest`, `ToolCallResult`, `ModelCapability`, `UsageRecord`, `CostRecord`, `AgentStatus`, `PoolItem`, `ReflectionBatchRun`

Breaking change in `v1.2.0`: candidate-era learning APIs are removed from stable surface. FLAME temporary-memory reflection is the authoritative learning path.

`v1.3.0` adds dual output modes per agent:
- `output_mode="text"` (default)
- `output_mode="json_schema"` with `output_schema` and typed `AgentOutput.content_json`

## Agent Capability Tiers

- `basic_agent`: short-term session context only, no long-term memory retrieval, no learning
- `self_learning_agent`: short-term + long-term memory (agent-owned memory only) + learning

Example:

```python
from agent_os import AgentTier

app.create_agent(
    agent_id="project-selector",
    goal="Select best project",
    model="gpt-4.1-mini",
    agent_tier=AgentTier.BASIC_AGENT,
)
```

## Library Quickstart

```python
from pathlib import Path
from agent_os import AgentOS

root = Path(".agent-os")
app = AgentOS.load(root=root, runtime_mode="local")
app.create_agent(
    agent_id="proposal-agent",
    goal="Draft project proposals",
    model="gpt-4.1-mini",
    tenant_id="default",
    output_mode="text",
)

session = app.sessions.init("proposal-agent", "Draft a proposal for Project Orion")
output = app.sessions.run(session.session_id)
print(output.type.value, output.content)

app.sessions.feedback(session.session_id, "Make it concise and include delivery timeline.")
app.sessions.accept(session.session_id, note="Accepted")
```

## Learning and Tools

```python
# learning.run remains as a compatibility alias and dispatches to FLAME trigger.
run = app.learning.run(agent_id="proposal-agent", window_size=20)
runs = app.flame.list_runs("proposal-agent")
pool = app.flame.list_pool("proposal-agent")
```

```python
from agent_os import ToolManifest, ToolScope

tool = app.tools.register(
    ToolManifest(
        name="project_lookup",
        scope=ToolScope.READ,
        input_schema={"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]},
        output_schema={"type": "object"},
    )
)
app.tools.bind("proposal-agent", tool.tool_id)
result, audit = app.tools.call("proposal-agent", session.session_id, tool.tool_id, {"q": "orion"})
```

## Canonical Examples

- `examples/proposal_agent_app.py`
- `examples/project_selection_agent_app.py`
- `examples/keyword_extraction_agent_app.py`

## v1 Docs

- `docs/stable-sdk-contract.md`
- `docs/migration-v1-memory-only.md`
- `docs/migration-v1.2.0-flame-cutover.md`
- `docs/migration-v1.3.0-structured-output.md`

