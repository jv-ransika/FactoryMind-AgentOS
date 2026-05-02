# FactoryMind AgentOS Beta Release

## Status
- Release channel: `beta`
- Current completion: Iterations 1-14 implemented
- Latest validation: see latest test run (`python -m pytest -q`)

## Included in Beta
- Agent/session runtime with typed protocol (`init`, `run`, `feedback`, `accept`)
- Memory/skill/context assembly contracts
- Suggest-only self-learning loop with validation and promotion controls
- Secure tool gateway with MCP transport support and audit trails
- Gate engine + replay evaluation + per-candidate rollback
- Service mode (FastAPI), durable local jobs, idempotency, health/readiness, metrics
- Storage abstraction with local and external-ready paths
- OpenAI runtime integration with context budgeting + hallucination soft controls
- JWT auth, tenant isolation, RBAC enforcement, immutable audit chain
- Cloud rollout artifacts and dependency-aware prod readiness checks
- Portable secret management with manual reload and fail-closed policy
- Stable core SDK contract for library consumers
- Private-index packaging and install verification workflow
- Canonical SDK examples for proposal, project-selection, and keyword extraction

## Beta Constraints
- Suitable for controlled beta usage and internal pilots
- Production hardening backlog is intentionally deferred (see `docs/future-production/`)
- No claim of final enterprise GA readiness in this release

## Recommended Beta Rollout Scope
- Controlled tenants/users
- Staged deployment with operator oversight
- Frequent backup and audit review during pilot

