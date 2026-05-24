# FLAME External Memory System

FLAME is now a separate repository and package:

- Repository: `https://github.com/jv-ransika/flame-memory`
- Distribution package: `flame-memory`
- Python import package: `flame_memory`

AgentOS consumes FLAME as its memory system while keeping the AgentOS SDK surface stable.

## Current Dependency

AgentOS depends on a tagged FLAME release:

```toml
flame-memory @ git+https://github.com/jv-ransika/flame-memory.git@v0.1.0
```

This is defined in `pyproject.toml`.

## Public AgentOS API

Users should continue using:

```python
app.flame.memory.create(...)
app.flame.memory.retrieve(...)
app.flame.trigger(...)
```

The old `AgentOS.memory` public API is not part of the v2 direction.

## Internal Boundary

AgentOS imports FLAME from the external package:

```python
from flame_memory import FlameManager, FlameMemorySystem
```

AgentOS keeps compatibility shims under `agent_os.flame`, but new code should treat `flame_memory` as the source of truth.

## AgentOS-Owned Adapters

AgentOS owns adapters that translate AgentOS internals into FLAME ports:

- `AgentOSFlameStoreAdapter`
- `AgentOSFlameRuntimeAdapter`
- `AgentOSFlameUsageRecorder`

These adapters stay in AgentOS because they depend on AgentOS storage, runtime, metrics, and cost tracking.

## Dependency Direction

Correct direction:

```text
AgentOS -> flame_memory
```

FLAME must not import AgentOS.

This lets FLAME be reused later by:

- LangChain-style integrations
- HTTP services
- MCP/tool adapters
- custom agent systems

## Updating FLAME

When FLAME changes:

1. Make and test the change in `jv-ransika/flame-memory`.
2. Tag the FLAME repo, for example `v0.2.0`.
3. Update AgentOS `pyproject.toml` to point at the new tag.
4. Run:

```bash
python -m pip install -e ".[dev]"
python -m compileall -q src scripts
python -m pytest -q
python scripts\release\build_dist.py
```

## Storage Compatibility

AgentOS storage remains in AgentOS. FLAME reaches it through adapter ports.

The current AgentOS storage layout remains compatible:

- `.agent-os/memories/...`
- `.agent-os/flame/pool/...`
- `.agent-os/flame/runs/...`

## Next FLAME Work

The next FLAME-owned features should happen in the FLAME repo first:

- memory taxonomy
- retention and forgetting policies
- retrieval scoring
- memory confidence
- HTTP API
- LangChain adapter
