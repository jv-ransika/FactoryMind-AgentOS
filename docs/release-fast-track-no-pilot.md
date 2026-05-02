# Fast-Track Release Workflow (No Pilot): `beta.3 -> rc.1`

## Purpose

Deliver a stable candidate quickly without running a formal pilot cohort, using strict internal evidence gates.

## Scope Freeze

- Allowed in `v0.1.0-beta.3`:
  - reliability fixes
  - security fixes
  - critical developer-experience defects that block adoption
- Not allowed:
  - feature expansion
  - API-surface expansion
  - non-blocking refactors

## Blocker Rubric

- `P0`: release blocking, security/data-integrity/critical reliability failure.
  - SLA: same-day fix
- `P1`: high-priority blocker for stable candidate readiness.
  - SLA: next-day fix
- Any open `P0/P1` blocks `v1.0.0-rc.1`.

## Required Gate Runner

Run:

```bash
python scripts/release/run_fast_track_validation.py --json-out .agent-os/release/fast_track_validation.json
```

All steps must pass before `rc.1` is considered.

## Sequence

1. Cut and stabilize `v0.1.0-beta.3` (fixes-only).
2. Run full fast-track validation runner.
3. Triage and fix any `P0/P1` until runner is green.
4. Complete `docs/release-checklist-rc1.md`.
5. Record evidence in `docs/stable-readiness-report-template.md`.
6. Cut `v1.0.0-rc.1`.
