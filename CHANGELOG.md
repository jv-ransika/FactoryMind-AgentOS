# Changelog

## v0.1.0-beta.3 (2026-05-02)

### Fast-Track Stabilization Scope
- No-pilot release track for rapid stable-candidate evaluation.
- Fixes-only policy for reliability, security, and critical DX blockers.
- Added strict release gate runner and RC readiness artifacts.

### Included Additions
- `scripts/release/run_fast_track_validation.py` single-command gate runner.
- `docs/release-fast-track-no-pilot.md` workflow and blocker rubric.
- `docs/release-checklist-rc1.md` immutable `rc.1` gates.
- `docs/stable-readiness-report-template.md` go/no-go decision artifact.
- `docs/templates/release-blocker-intake-template.md` blocker intake and SLA template.
- `docs/beta3-fix-log.md` auditable blocker-fix register.

### Release Policy
- Only approved blocker fixes are allowed in `beta.3`.
- `rc.1` is blocked by any open `P0/P1`.

## v0.1.0-beta.2 (2026-05-02)

### Beta Scope
- Library-consumer readiness increment for internal SDK adoption.
- Stable core API contract documentation and guardrail tests.
- Private-index packaging workflow and install verification automation.
- Three canonical SDK integration examples.

### Included Additions
- Stable SDK contract docs and experimental boundary notes.
- Release scripts: build dist, verify install, publish to private index.
- Consumer docs: quickstart, config guide, integration checklist, migration guide.
- Canonical example apps:
  - proposal writing
  - project selection (MCP-backed query pattern)
  - keyword extraction

### Known Constraints
- Compatibility guarantee applies only to stable core API.
- Advanced/non-core APIs remain experimental during beta.
- Private index publication requires managed internal credentials.

## v0.1.0-beta.1 (2026-05-02)

### Beta Scope
- Internal pilot release for FactoryMind AgentOS with Iterations 1-12 complete.
- Docker-first release packaging and pilot runbook assets.
- Local-mode default runtime path for controlled beta rollout.

### Included Capabilities
- Typed session lifecycle: `init`, `run`, `feedback`, `accept`.
- Memory/skill/context assembly and retrieval.
- Suggest-only learning pipeline with validation/evaluation/promotion/rollback.
- Secure tool gateway with MCP support, allowlists, sanitization, and audit.
- FastAPI service mode, worker jobs, idempotency, health/readiness, metrics.
- OpenAI runtime path with context budgeting and uncertainty signaling.
- JWT auth, tenant isolation, RBAC, and audit chain fields.
- Portable secrets with manual reload and fail-closed impacted operations.

### Known Constraints
- Release channel is beta for internal pilot usage.
- Local storage/in-process queue is the default beta profile.
- Production hardening backlog remains tracked in `docs/future-production/`.

### Upgrade Notes
- Package version moved from `0.1.0` to `0.1.0-beta.1`.
- Service metadata version now reports `0.1.0-beta.1`.

