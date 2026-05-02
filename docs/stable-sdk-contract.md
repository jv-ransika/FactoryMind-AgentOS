# Stable SDK Contract (Beta.2)

FactoryMind AgentOS `v0.1.0-beta.2` defines a stable core contract for library consumers.

## Stable Core Surface

- `AgentOS`
- `AgentOS.load(...)`
- `AgentOS.create_agent(...)`
- `AgentOS.sessions`
- `AgentOS.memory`
- `AgentOS.skills`
- `AgentOS.learning`
- `AgentOS.tools`

## Stable Core Models

- `AgentDefinition`
- `Session`
- `SessionEvent`
- `AgentOutput`
- `MemoryItem`
- `SkillDefinition`
- `LearningRun`
- `LearningCandidate`
- `ToolManifest`
- `ToolCallResult`

## Compatibility Rule

- Stable Core is backward compatible across beta patch increments (`beta.x -> beta.y`) unless explicitly deprecated in changelog.
- Non-core APIs are experimental and may change without compatibility guarantees.
