# Stable SDK Contract (`v2.0.0`)

FactoryMind AgentOS `v2.0.0` defines a breaking stable contract where FLAME is the primary memory system for memory-only self-learning agents, feedback reflection, and context retrieval.

## Stable Core Surface

- `AgentOS`
- `AgentOS.load(...)`
- `AgentOS.create_agent(...)`
- `AgentOS.sessions`
- `AgentOS.learning`
- `AgentOS.flame`
- `AgentOS.flame.memory`
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
- `MemoryWriteRequest`
- `MemoryWriteResult`
- `MemoryRetrievalRequest`
- `MemoryRetrievalResult`
- `MemoryEvent`
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
- `sessions.run(...)` may perform one confidence repair retry before storing the returned `AgentOutput` event when enabled in runtime config.
- `v2.0.0` removes `AgentOS.memory` from the stable public surface. Use `AgentOS.flame.memory`.

## FLAME Memory System

FLAME owns memory operations for AgentOS and future external agent clients.

Primary SDK calls:

- `app.flame.memory.create(...)`
- `app.flame.memory.list(...)`
- `app.flame.memory.retrieve(...)`
- `app.flame.memory.write(MemoryWriteRequest(...))`
- `app.flame.memory.retrieve_for_context(MemoryRetrievalRequest(...))`
- `app.flame.memory.ingest_event(MemoryEvent(...))`

Storage adapters remain unchanged in this step. FLAME memory uses the existing `DomainStore` memory persistence underneath.

## Tier Rules

- `basic_agent`: session-only context.
- `self_learning_agent`: session + long-term memory retrieval + memory-learning.

## Confidence Contract

Every `AgentOutput` includes `confidence.level`, `confidence.score`, `confidence.basis`, `confidence.uncertainties`, and `confidence.requires_human_check`.

Runtime config defaults:

- `confidence_repair_enabled: true`
- `confidence_threshold: 0.60`
- `confidence_repair_max_attempts: 1`

When a `final` output is below the threshold, `sessions.run(...)` reruns the same agent once with a repair instruction. The repaired output may be another `final` or a `question` asking for missing information. `question` and `error` outputs do not trigger repair.

The first low-confidence output is not stored as a separate `AGENT_OUTPUT` event. The returned output includes repair trace fields in `runtime_metadata`.

## Migration Note

Legacy agents/sessions remain readable. Legacy skill artifacts are ignored by stable runtime/learning behavior. Update memory integrations from `AgentOS.memory` to `AgentOS.flame.memory`.
