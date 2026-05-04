# v1.3.0 Release Validation Report

Date: 2026-05-04  
Status: Go

## Automated Regression

- Command: `PYTHONPATH=src pytest -q`
- Result: `105 passed, 3 skipped`
- Gate: Pass

## Smoke Validation

- Command: `PYTHONPATH=src python scripts/beta_smoke.py`
- Result:
  - Agent/session run succeeded
  - Feedback + accept succeeded
  - FLAME reflection run created long-term reflection memory
  - Tool call + audit succeeded
- Gate: Pass

## Practical Validation

### Structured Output Practical

- Scenario: `output_mode="json_schema"` agent with required fields (`title`, `decision`)
- Result:
  - `AgentOutput.type="final"`
  - `AgentOutput.content_json` present and valid object
  - `AgentOutput.content` populated with canonical JSON string
- Gate: Pass

### Vector Retrieval Practical

- Backend: Postgres + pgvector (local instance on `127.0.0.1:55432`)
- Scenario: create memory with residual-risk phrasing, retrieve via semantic query
- Result:
  - non-empty retrieval (`hits 1`)
  - top match is expected memory
- Gate: Pass

## Release Notes Consistency

- Updated package/service/protocol versions to `1.3.0`.
- Updated README stable status/install and v1 docs pointers.
- Added migration note: `docs/migration-v1.3.0-structured-output.md`.
- Updated stable SDK contract and changelog.

## Known Limitations

- Structured output mode relies on provided schema quality; invalid schemas are rejected at agent-definition validation.
- Local runtime structured output is deterministic placeholder behavior (for development/testing), not model-generated semantics.

