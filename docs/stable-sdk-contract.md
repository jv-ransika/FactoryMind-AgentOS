# Stable SDK Contract (`v1.3.0`)

FactoryMind AgentOS `v1.3.0` defines a stable external contract for memory-only self-learning agents with FLAME temporary-memory reflection and optional structured JSON outputs.

## Stable Core Surface

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
- `AgentTier` (`basic_agent | self_learning_agent`)

## Stable Core Models

- `AgentDefinition`
- `Session`
- `SessionEvent`
- `AgentOutput`
- `MemoryItem`
- `LearningRun`
- `PoolItem`
- `ReflectionBatchRun`
- `ToolManifest`
- `ToolCallResult`
- `ModelCapability`
- `UsageRecord`
- `CostRecord`
- `AgentStatus`

## Compatibility Rules

- Stable Core follows semantic-versioning compatibility.
- Non-core APIs are experimental and may change.
- `v1.0.0` is a breaking change from beta: skill-based learning and skill-based context behavior are removed from stable core behavior.
- `v1.2.0` is a breaking change from `v1.1.x`: candidate-era learning APIs are removed (`evaluate`, `promote`, `reject`, `rollback`, `list_candidates`).
- `AgentOS.learning.run(...)` remains as a one-release compatibility alias dispatching to FLAME trigger.
- `v1.3.0` adds additive output-contract fields:
  - `AgentDefinition.output_mode: "text" | "json_schema"`
  - `AgentDefinition.output_schema: object | null`
  - `AgentOutput.content_json: object | null`

## Tier Rules

- `basic_agent`: session-only context.
- `self_learning_agent`: session + long-term memory retrieval + memory-learning.

## Migration Note

Legacy agents/sessions remain readable. Legacy skill artifacts are ignored by stable runtime/learning behavior.
