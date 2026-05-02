# Beta Release Checklist (v0.1.0-beta.3)

## Go/No-Go Gates
- [ ] `python -m pytest -q` passes.
- [ ] Beta smoke workflow passes (`python scripts/beta_smoke.py`).
- [ ] `healthz` and `readyz` checks validated in docker deployment.
- [ ] Secret fail-closed behavior validated:
  - [ ] missing secret returns deterministic failure for impacted operation.
  - [ ] reload restores operation.
- [ ] Changelog and beta scope docs updated.
- [ ] Known issues and pilot feedback templates published.

## Release Outputs
- [ ] Tag `v0.1.0-beta.3`.
- [ ] Docker image `factorymind-agentos:0.1.0-beta.3`.
- [ ] Published docs:
  - [ ] `docs/20-beta-release.md`
  - [ ] `docs/beta-runbook.md`
  - [ ] `docs/future-production/README.md`

