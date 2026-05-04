# Beta.3 Fix Log (`v0.1.0-beta.3`)

Use this log for approved blocker-only changes.

| Fix ID | Linked Blocker ID | Severity | Area | Summary | Owner | Date | Verification |
|---|---|---|---|---|---|---|---|
| FIX-001 |  |  |  |  |  |  |  |
| FIX-002 | N/A (`v1.0.0` stabilization) | P1 | Learning trigger | Reflection enqueue now requires at least one feedback event in accepted session. | Codex | 2026-05-02 | `python -m pytest -q` and manual local install smoke run |

## Rules

- Each entry must link to a blocker record.
- Only reliability/security/critical DX blocker fixes are allowed.
- Any non-blocking enhancement is deferred until post-`rc.1`.
