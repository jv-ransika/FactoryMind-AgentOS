# Iteration 11: Cloud Rollout Hardening

## Deployment Targets
- ECS/Fargate service task: `deploy/ecs/service-task.json`
- ECS/Fargate worker task: `deploy/ecs/worker-task.json`

## Production Requirements
- `AGENT_OS_ENV=prod`
- `AGENT_OS_POSTGRES_DSN` set and reachable
- `AGENT_OS_REDIS_URL` set and reachable
- migrations must include tenant/auth fields (`0002_tenant_auth_fields`)
- no local JSON-only storage allowed in prod mode

## OTEL OTLP
- Set:
  - `OTEL_SERVICE_NAME`
  - `OTEL_EXPORTER_OTLP_ENDPOINT`
- OTEL initialization is best-effort if package/exporter unavailable.

## Backup and Recovery Runbook
1. Postgres backup: run managed snapshot or logical dump on interval.
2. Redis recovery: treat queue as recoverable operational state; restart workers and replay pending jobs.
3. Migration rollback:
   - stop service traffic
   - `agent-os migrate downgrade <revision>`
   - verify dependency check `agent-os ops check-deps`
4. Incident checklist:
   - confirm `/healthz`
   - confirm `/readyz` with ops token
   - verify DB/Redis connectivity
   - inspect dead-letter and auth failure counters

## RPO/RTO Targets
- Suggested baseline:
  - RPO: <= 15 minutes
  - RTO: <= 60 minutes
