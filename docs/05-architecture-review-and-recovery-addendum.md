# Architecture Review and Recovery Addendum

## 1) Review Summary
The current architecture is directionally sound: LangGraph-first, Python-first, MCP-mediated tools, explicit session states, confidence-gated outputs, and post-accept reflection. The main risks are not in the high-level structure; they are in operational edge cases and feedback-driven learning.

Keep the v1 scope narrow:
- one orchestrator: `LangGraph`
- one provider: `OpenAI`
- one external integration type: MCP project database
- read-only MCP access first
- no autonomous production code or permission changes

## 2) Main Weaknesses Found
| Area | Weakness | Why It Can Go Wrong | Required Fix |
|---|---|---|---|
| Session protocol | Replay or duplicate `accept` messages | Can trigger duplicate reflection or false completion | Enforce `message_id`, `nonce`, `state_version`, idempotency records |
| Feedback loop | Bad feedback can poison future behavior | Accepted sessions are treated as learning signals | Quarantine changes and require eval pass before promotion |
| Context handling | Important constraints may be compressed away | Agent may forget latest feedback or unresolved requirements | Hard-pin latest feedback, open questions, constraints, and accepted snapshots |
| MCP integration | Tool output may contain prompt injection | Agent may treat database text as instructions | Treat MCP output as data only and sanitize instruction-like text |
| Tool availability | MCP/database outages block sessions | Agent may fail without recoverable state | Add checkpoints, bounded retries, circuit breakers, and `error_retryable` |
| Confidence | LLM self-confidence may be wrong | Hallucinations may appear reliable | Compute confidence from retrieval/tool/verifier signals and calibrate with outcomes |
| Memory | Learned memory may become stale or sensitive | Wrong facts or private data affect future runs | Store provenance, TTL, confidence, revocation metadata, and deletion support |
| Framework choice | Adding Semantic Kernel too early adds maintenance load | One engineer must operate two abstractions | Keep Semantic Kernel as phase-2 only after concrete repeated pain appears |

## 3) Recovery Design
Every failure class must have a defined recovery path.

| Failure | Agent Output | Recovery Behavior |
|---|---|---|
| Temporary model failure | `error_retryable` | Retry with backoff, preserve checkpoint, then ask user to retry if budget exhausted |
| MCP server unavailable | `error_retryable` | Preserve session, skip reflection, resume from checkpoint when MCP recovers |
| MCP permission denied | `error_policy` | Explain blocked action and request approved input/action |
| Prompt injection detected | `error_policy` or sanitized continuation | Ignore malicious segment, log event, add case to red-team set |
| Missing user data | `question` | Ask one targeted question and wait for `feedback` |
| Low confidence | `question` or manual review | Do not emit `final` until missing evidence is resolved |
| Bad reflection candidate | no user-facing output | Reject candidate, keep current config, add failure to eval set |
| Sensitive data in memory/logs | operator alert | Quarantine record, redact, audit, and update filters |

## 4) Improved Context Strategy
The context assembler must be deterministic and testable.

Required input buckets:
- `system_invariants`
- `active_user_feedback`
- `unresolved_requirements`
- `accepted_output_snapshot`
- `session_summary`
- `retrieved_evidence`
- `recent_tool_results`

Priority order under token pressure:
1. keep `system_invariants`
2. keep latest `active_user_feedback`
3. keep `unresolved_requirements`
4. keep `accepted_output_snapshot`
5. compress `session_summary`
6. trim `retrieved_evidence` by relevance
7. drop old raw tool payloads

Test requirement:
- Build regression tests where old feedback conflicts with new feedback.
- Latest feedback must always win unless policy blocks it.

## 5) Improved Reflection Strategy
Reflection should not directly modify production behavior.

Reflection output should be a candidate patch:
```json
{
  "agent_id": "project_selector",
  "candidate_type": "prompt|retrieval|routing|policy_tuning",
  "proposed_change": {},
  "evidence": {
    "accepted_session_ids": [],
    "feedback_patterns": [],
    "expected_metric_change": {}
  },
  "risk_level": "low|medium|high",
  "promotion_status": "quarantined"
}
```

Promotion gates:
- eval pass
- no safety regression
- no confidence calibration regression
- approval for medium/high risk
- rollback config prepared before promotion

## 6) Improved Confidence Strategy
Do not expose raw LLM self-rating as the platform confidence.

Recommended formula inputs:
- retrieval coverage
- source quality
- unresolved requirements
- tool success
- verifier agreement
- historical acceptance rate

Minimum policy:
- `confidence_score < 0.55`: no final output
- `0.55 <= confidence_score < 0.80`: final allowed only with verification flag
- `confidence_score >= 0.80`: final allowed

These thresholds must be recalibrated from real acceptance and correction data.

## 7) Implementation Priorities
Build in this order:
1. Session protocol and state machine.
2. MCP tool gateway with read-only project database access.
3. Context assembler with deterministic token budget.
4. Project selection agent.
5. Confidence scoring and verifier.
6. Audit log and idempotency records.
7. Reflection worker in quarantine-only mode.
8. Eval harness and promotion gates.

## 8) Decision Updates
- Keep `LangGraph` as the v1 runtime.
- Keep `Semantic Kernel` out of v1 runtime orchestration.
- Use MCP as the only external tool path in v1.
- Treat accepted sessions as learning evidence, not automatic truth.
- Treat all external data, including internal database text, as untrusted model input.
