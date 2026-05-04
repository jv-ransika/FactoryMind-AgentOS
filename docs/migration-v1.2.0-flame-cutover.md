# Migration Guide: `v1.1.x` -> `v1.2.0` (FLAME Cutover)

`v1.2.0` replaces candidate-era learning with FLAME temporary-memory reflection.

## Breaking Changes

- Removed SDK candidate APIs:
  - `learning.list_candidates(...)`
  - `learning.evaluate(...)`
  - `learning.validate(...)`
  - `learning.promote(...)`
  - `learning.reject(...)`
  - `learning.rollback(...)`
- Removed service candidate endpoints:
  - `/learning/candidates/*`
- Removed CLI candidate commands:
  - `learn list-candidates`
  - `learn evaluate`
  - `learn validate`
  - `learn promote`
  - `learn reject`
  - `learn rollback`

## New FLAME Surface

- SDK:
  - `AgentOS.flame.status(agent_id)`
  - `AgentOS.flame.list_pool(agent_id, state=None)`
  - `AgentOS.flame.list_runs(agent_id)`
  - `AgentOS.flame.trigger(agent_id=None, force=False)`
- Service:
  - `GET /flame/pool`
  - `GET /flame/runs`
  - `POST /flame/trigger`
- CLI:
  - `agent-os flame pool <agent>`
  - `agent-os flame runs <agent>`
  - `agent-os flame trigger [--agent ...] [--force]`

## Behavior Changes

- Accept-flow for `self_learning_agent` now runs FLAME intake/extraction directly.
- Accepted sessions without feedback are stored as `experience` pool items.
- Accepted sessions with feedback are stored as `learning_point` items.
- Reflections are written to long-term memory with metadata:
  - `created_by=flame_reflection`
  - `reflection_id`
  - `derived_from`
  - `human_feedback_weighted`
  - `confidence`

## Compatibility Alias

- `AgentOS.learning.run(...)` is retained for one release and dispatches internally to FLAME trigger.
- Return shape remains `LearningRun`, but `candidate_ids` is always empty under FLAME cutover.

