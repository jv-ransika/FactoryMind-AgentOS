# Migration to `v1.0.0` Memory-Only Learning

## What Changed

- Stable learning is now memory-only.
- Stable runtime/context no longer uses skills.
- Stable API adds model capabilities and usage/cost monitoring.

## Required Actions

1. Keep existing agent IDs and session data; they are still readable.
2. Stop relying on skill-based candidate generation/promotion.
3. For learning, run `self_learning_agent` agents and rely on memory candidates.
4. Update integrations to read monitoring endpoints:
   - `GET /agents/{id}/status`
   - `GET /agents/{id}/usage`
   - `GET /agents/{id}/costs`

## Behavior Differences

- `basic_agent` rejects learning operations (`tier_forbids_learning`).
- `self_learning_agent` learning is auto-triggered on session acceptance.
- Low-risk passing memory candidates can auto-promote based on policy.
- Cost is computed only when model pricing exists in the capability catalog; otherwise `cost_status=unsupported`.
