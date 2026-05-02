# Future Production Hardening Backlog

This folder tracks post-beta work required for GA-grade production rollout.

## Iteration 13: Secret Rotation and Cloud Secret Adapters
- Add optional AWS/Vault-style adapters behind existing `SecretResolver`
- Add automated rotation/refresh with safe cutover strategy
- Add stale-secret detection metrics and alerts

## Iteration 14: Reliability and Failure Engineering
- Chaos/fault-injection test suite for service/worker/storage/tool/runtime paths
- SLO/SLA definition with error budget policy
- Recovery automation and runbook verification drills

## Iteration 15: Release Hardening and Security Assurance
- Pen-test/remediation cycle and threat model refresh
- Backup/restore and DR simulation sign-off
- Performance/capacity baseline and multi-tenant authorization audit
- GA readiness checklist and release gates
