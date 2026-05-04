# Migration to v1.3.0 (Structured Output + Final Stabilization)

## Summary

`v1.3.0` introduces first-class structured output mode for agents while preserving text output behavior.

## Additive API Changes

- `AgentDefinition.output_mode`:
  - `"text"` (default)
  - `"json_schema"`
- `AgentDefinition.output_schema`:
  - JSON schema object required when `output_mode="json_schema"`.
- `AgentOutput.content_json`:
  - Structured object for final outputs in `json_schema` mode.
  - `content` remains populated with canonical JSON string for compatibility.

## Action Required

1. For existing agents: no change needed (default remains `output_mode="text"`).
2. For structured-output agents:
   - set `output_mode="json_schema"`,
   - provide a valid `output_schema` object.
3. Update consumers to read `content_json` when available; keep `content` fallback for compatibility.

## Runtime Notes

- OpenAI runtime enforces schema-constrained JSON output and validates responses.
- Local runtime returns deterministic placeholder structured outputs for supported schema shapes.

## Related Hardening in v1.3.0

- FLAME content caps:
  - temporary extracted content: 320 chars,
  - reflection content: 280 chars.
- Non-local vector flows require vector-capable backend behavior (explicit failure on unsupported vector configuration).

