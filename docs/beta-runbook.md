# FactoryMind AgentOS Beta Runbook

## 1) Prerequisites
- Docker + Docker Compose
- Python 3.11+ (for local smoke script)

## 2) Bootstrap
1. Copy `.env.example` to `.env`.
2. Set `OPENAI_API_KEY`.
3. Keep `AGENT_OS_ENV=dev` for beta local mode.
4. Create workspace folder: `.agent-os/`.

## 3) Start Service and Worker
1. `docker compose -f docker-compose.beta.yml build`
2. `docker compose -f docker-compose.beta.yml up -d`
3. Check health:
   - `curl http://localhost:8000/healthz`
   - `curl -H "Authorization: Bearer <ops-token>" http://localhost:8000/readyz`

## 4) Stop / Restart
- Stop: `docker compose -f docker-compose.beta.yml down`
- Restart: `docker compose -f docker-compose.beta.yml restart`

## 5) Secret Reload Flow
- CLI local process: `agent-os secrets reload --root .agent-os`
- Service: `POST /ops/secrets/reload` with ops/admin JWT.
- Expected behavior: impacted operations fail closed while secrets are unavailable, then recover after reload.

## 6) Recovery and Rollback
- If service unhealthy, capture logs and run `agent-os ops check-deps`.
- For bad learning promotions, run `agent-os learn rollback <candidate_id> --reason "..."`
- For beta rollback at deployment level: redeploy prior image tag and restore `.agent-os` backup.

