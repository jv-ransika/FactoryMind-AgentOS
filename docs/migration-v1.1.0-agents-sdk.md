# Migration: v1.1.0 Agents SDK Runtime Cutover

## What changed
- Runtime path now supports `openai_agents_sdk` as the primary engine.
- Session run responses include runtime metadata fields:
  - `runtime_engine`
  - `sdk_run_id` (when available)
  - full `runtime_metadata` in typed output payload

## Configuration
Set runtime engine in `.agent-os/runtime.json`:

```json
{
  "mode": "openai",
  "runtime_engine": "openai_agents_sdk"
}
```

Or via environment:

- `AGENT_OS_RUNTIME_ENGINE=openai_agents_sdk`

## Notes
- If the Agents SDK package is not installed, runtime falls back to legacy OpenAI Responses path and records `fallback_reason=agents_sdk_unavailable` in runtime metadata.
- This cutover does not change AgentOS learning governance (memory-only promotion gates + rollback remain unchanged).
- This cutover does not change service authz/tenant boundaries.

## Operational checks
1. Verify dependency is installed: `pip show openai-agents`
2. Run runtime config validation: `agent-os runtime validate-config --runtime-mode openai`
3. Run session and inspect run payload for `runtime_engine`.
