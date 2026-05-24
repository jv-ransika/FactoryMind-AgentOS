# Changelog

## Unreleased

### v2.0.0 Breaking Changes
- Bumped package, service, protocol agent, and session version markers to `2.0.0`.
- Removed the old public `MemoryManager` implementation; FLAME memory is now the memory system boundary.

### FLAME Memory System
- Refactored FLAME into the primary in-repo memory system boundary through `app.flame.memory`.
- Split FLAME into the standalone import package boundary `flame_memory` while keeping `app.flame.memory` and `agent_os.flame` compatibility shims.
- Added Python port models for future universal integrations: `MemoryWriteRequest`, `MemoryWriteResult`, `MemoryRetrievalRequest`, `MemoryRetrievalResult`, and `MemoryEvent`.
- Removed `AgentOS.memory` from the stable public API direction; memory operations should use `AgentOS.flame.memory`.
- Routed AgentOS context assembly, CLI memory commands, monitoring, and FLAME reflection writes through FLAME memory.

### Runtime Reliability
- Added configurable confidence repair for `sessions.run(...)`: low-confidence `final` outputs below the configured threshold retry once by default, asking the agent to clarify missing information or return a better-supported answer.
- Added runtime config fields: `confidence_repair_enabled`, `confidence_threshold`, and `confidence_repair_max_attempts`.
- Added repair trace metadata on returned outputs: `confidence_repair_attempted`, `confidence_repair_attempts`, `initial_confidence_score`, and `initial_confidence_basis`.
- Normalized `postgresql://` DSNs to SQLAlchemy's `postgresql+psycopg://` dialect to match the project's `psycopg` dependency.

## v1.3.0 (2026-05-04)

### Stable Release Finalization
- Full regression gate passed: `105 passed, 3 skipped`.
- Beta smoke flow passed (`scripts/beta_smoke.py`) including sessions, feedback/accept, FLAME reflection, memory write, and tool audit.
- Practical validation passed for:
  - structured output mode (`output_mode=json_schema`) with typed `content_json`,
  - pgvector retrieval path on vector-capable Postgres backend.
- PyPI package published as `factorymind-agent-os` (`1.3.0`) to satisfy project-name uniqueness policy.

### Agent Output Contract
- Added dual output modes on `AgentDefinition`:
  - `output_mode: "text" | "json_schema"` (default `text`)
  - `output_schema: object | null` (required for `json_schema` mode)
- Added `AgentOutput.content_json: object | null` for typed structured final outputs.
- OpenAI runtime now supports schema-constrained structured outputs with validation and canonical JSON serialization in `content`.
- Local runtime now supports deterministic placeholder structured outputs for `json_schema` mode.
- CLI and service agent-creation surfaces now accept `output_mode` and `output_schema`.

### FLAME and Vector Hardening
- Added FLAME max character limits with truncate-and-continue policy:
  - temporary extracted content cap: 320 chars,
  - reflection content cap: 280 chars.
- Added truncation observability metrics:
  - `flame_temp_content_truncated`
  - `flame_reflection_content_truncated`
- Enforced pgvector-required behavior for non-local vector flows; unsupported vector backends fail explicitly.

### Test and Reliability Fixes
- Fixed release test collection/import stability for smoke script execution in test runtime contexts.
- Added and updated tests for structured output mode, FLAME truncation behavior, and vector policy enforcement.

### Usage/Cost Tracking Expansion
- Added first-class usage/cost operation buckets: `embedding`, `flame_extraction`, and `flame_reflection`.
- Added shared usage/cost recorder utility used by runtime, embedding, and FLAME paths.
- Added OpenAI embedding usage capture (`prompt_tokens`/`total_tokens`) and usage/cost persistence during memory embed calls.
- Added FLAME extraction/reflection OpenAI call usage/cost persistence with error-safe behavior.
- Added `text-embedding-3-small` capability catalog entry for deterministic embedding cost computation when available.

## v1.2.0 (2026-05-03)

### FLAME Temporary Memory Cutover
- Replaced candidate-era learning pipeline with FLAME temporary-memory reflection as the authoritative self-learning path.
- Added FLAME subsystem with intake, extraction, pool persistence, trigger checks, clustering, reflection synthesis, and long-term memory handoff.
- Accepted sessions without feedback now produce `experience` extracted items (not skipped).
- Reflection outputs are written into long-term memory with provenance/confidence metadata (`created_by=flame_reflection`).

### API and CLI Breaking Changes
- Removed candidate-era SDK methods: `list_candidates`, `validate`, `evaluate`, `promote`, `reject`, `rollback`.
- Removed service endpoints under `/learning/candidates/*`.
- Removed CLI commands `learn list-candidates|validate|evaluate|promote|reject|rollback`.
- Added FLAME surfaces:
  - SDK: `AgentOS.flame.status|list_pool|list_runs|trigger`
  - Service: `GET /flame/pool`, `GET /flame/runs`, `POST /flame/trigger`
  - CLI: `agent-os flame pool|runs|trigger`
- Kept `AgentOS.learning.run(...)` as one-release compatibility alias dispatching to FLAME trigger.

### Reliability and Ops
- Added FLAME pool/run persistence in local and Postgres adapters.
- Added FLAME job types for worker orchestration (`flame_extract_session`, `flame_reflect_batch`, `flame_trigger_scan`).
- Updated monitoring status logic to count FLAME-promoted memories from memory metadata.

## v1.1.0 (2026-05-03)

### Runtime Cutover
- Added OpenAI Agents SDK runtime engine path (`runtime_engine=openai_agents_sdk`) in `OpenAIRuntimeAdapter`.
- Added runtime metadata in typed outputs (`runtime_metadata`) with engine/session/run hints.
- Service `POST /sessions/{id}/run` now returns additive fields: `runtime_engine`, `sdk_run_id`.

### Compatibility and Safety
- Preserved typed output contract: `question | final | error` plus confidence.
- Preserved existing AgentOS governance boundaries (learning gates, rollback, RBAC/tenant, idempotency, retries).
- Added deterministic local fallback to legacy OpenAI Responses runtime when Agents SDK package is unavailable.

### Configuration
- Added `AGENT_OS_RUNTIME_ENGINE` support in runtime config loading.
- Added `openai-agents` dependency to package metadata for SDK-backed runtime.

## v1.0.0 (2026-05-02)

### Stable External Release
- Memory-only self-learning core for stable runtime behavior.
- OpenAI Responses API integration with strict typed outputs and deterministic error taxonomy.
- Model capability registry with fail-closed unknown-model handling.
- Context-window preflight controls with deterministic compaction/truncation notes.
- Usage and cost tracking with operation-bucket accounting.
- Agent status and usage/cost monitoring endpoints.

### Breaking Changes
- Skill-based learning and skill-based runtime context usage removed from stable core behavior.
- Stable API surface now emphasizes `memory`, `learning`, `tools`, `capabilities`, and `monitor`.

### Reliability and Security
- Self-learning agent acceptance triggers automatic reflection job enqueue.
- Reflection enqueue is feedback-gated: accepted sessions without feedback are skipped.
- Learning remains gate-based with low-risk auto-promotion only.
- Existing JWT/RBAC/tenant isolation and job retry/dead-letter behavior retained.

### Verification Notes
- Manual local-runtime smoke run completed in isolated install environment.
- Verified business logic paths:
  - accept without feedback => no reflection enqueue
  - accept with feedback => reflection enqueue and worker processing
  - memory-only candidate generation/promotion
  - tool denial and audit typed behavior
  - openai missing-key typed runtime error behavior

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

