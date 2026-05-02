# FactoryMind AgentOS

FactoryMind AgentOS is a Python library for building reusable, reliable, self-improving agents with a typed runtime contract.

Current status: `v0.1.0-beta.3` (internal beta).

## Install

```bash
# private-index path:
pip install agent-os==0.1.0-beta.3 \
  --index-url <your-private-index-url>

# or wheel-only path:
pip install dist/agent_os-0.1.0b3-py3-none-any.whl
```

For local repo usage:

```bash
pip install -e .
```

## Stable Core API (Beta Guarantee)

The compatibility guarantee in beta applies to:

- `AgentOS`
- `AgentOS.load(...)`
- `AgentOS.create_agent(...)`
- `AgentOS.sessions`
- `AgentOS.memory`
- `AgentOS.skills`
- `AgentOS.learning`
- `AgentOS.tools`
- Core models: `AgentDefinition`, `Session`, `SessionEvent`, `AgentOutput`, `MemoryItem`, `SkillDefinition`, `LearningRun`, `LearningCandidate`, `ToolManifest`, `ToolCallResult`

All other APIs are experimental and may change between beta versions.

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
)

session = app.sessions.init("proposal-agent", "Draft a proposal for Project Orion")
output = app.sessions.run(session.session_id)
print(output.type.value, output.content)

app.sessions.feedback(session.session_id, "Make it concise and include delivery timeline.")
app.sessions.accept(session.session_id, note="Accepted")
```

## Learning and Tools

```python
run = app.learning.run(agent_id="proposal-agent", window_size=20)
if run.candidate_ids:
    report = app.learning.evaluate(run.candidate_ids[0])
    if report.decision == "pass":
        app.learning.promote(run.candidate_ids[0])
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

## Beta Docs

- `docs/20-beta-release.md`
- `docs/stable-sdk-contract.md`
- `docs/sdk-configuration-guide.md`
- `docs/integration-checklist.md`
- `docs/migration-to-private-index.md`
- `docs/future-production/README.md`

