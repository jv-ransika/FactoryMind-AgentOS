# Stable Candidate Checklist (`v1.0.0-rc.1`)

## Immutable Gates (Must Pass)

- [x] Full test suite passes: `python -m pytest -q`
- [x] Packaging artifacts generated (wheel + sdist)
- [x] Clean-venv install verification passes
- [x] Canonical examples run successfully
- [x] Beta smoke workflow passes
- [x] Secret fail-closed/reload behavior validated
- [x] Auth/tenant/RBAC core checks pass
- [x] Service health/readiness checks pass
- [ ] No open `P0` or `P1` blockers

## Release Artifacts

- [ ] Tag `v0.1.0-beta.3` (fixes-only baseline)
- [x] Validation summary file attached
- [x] Stable readiness report completed
- [ ] Package distribution path completed (private index publish or wheel-only distribution record)
- [ ] Tag `v1.0.0-rc.1` created
