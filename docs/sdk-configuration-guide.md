# SDK Configuration Guide

## Defaults

- Default runtime mode: `local`
- Default root path: `.agent-os`
- Default learning mode: `collect_only`

## Runtime Config

Use `.agent-os/runtime.json` or env/secret references:

```json
{
  "mode": "openai",
  "openai_api_key": "secret://OPENAI_API_KEY",
  "openai_base_url": "secret://OPENAI_BASE_URL",
  "openai_timeout_ms": 20000,
  "confidence_repair_enabled": true,
  "confidence_threshold": 0.6,
  "confidence_repair_max_attempts": 1
}
```

### Confidence Repair

Every `AgentOutput` includes confidence metadata. By default, `sessions.run(...)` automatically retries one low-confidence `final` output when `confidence.score < 0.60`.

The repair retry gives the same agent a follow-up instruction to ask a clarifying question if the answer is uncertain, or to return a better-supported answer with updated confidence if the available context is enough.

Runtime config fields:

- `confidence_repair_enabled`: enables or disables the repair loop. Default: `true`.
- `confidence_threshold`: final outputs below this score trigger repair. Default: `0.60`.
- `confidence_repair_max_attempts`: maximum automatic repair attempts per session run. Default: `1`.

Repair metadata is added to the returned output under `runtime_metadata`, including `confidence_repair_attempted`, `confidence_repair_attempts`, `initial_confidence_score`, and `initial_confidence_basis`.

## Secrets

Resolution order:
1. direct value
2. `secret://...` resolver
3. env
4. `.env` / `.agent-os/secrets.env`
5. `.agent-os/secrets.json`

Manual reload:
- SDK: `agent_os.secrets.reload()`
- CLI: `agent-os secrets reload`
- Service: `POST /ops/secrets/reload`

## Auth Config (Service Mode)

Use `.agent-os/auth.json`:

```json
{
  "issuer": "secret://AGENT_OS_JWT_ISSUER",
  "audience": "secret://AGENT_OS_JWT_AUDIENCE",
  "jwks_url": "secret://AGENT_OS_JWT_JWKS_URL",
  "public_key_path": "secret://AGENT_OS_JWT_PUBLIC_KEY_PATH"
}
```
