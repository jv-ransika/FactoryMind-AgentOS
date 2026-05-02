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
  "openai_timeout_ms": 20000
}
```

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
