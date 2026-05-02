# Observability, Audit, and Traceability Research

Access date: 2026-05-01

## 1) Research Question
How should FactoryMind AgentOS trace, audit, and explain agent execution, memory/skill learning, tool use, evaluations, promotions, and rollbacks?

Observability is required for debugging. Auditability is required for industrial trust. They overlap, but they are not the same thing.

## 2) Short Answer
Use OpenTelemetry for portable traces, and keep an FactoryMind AgentOS-owned audit ledger for durable learning and governance evidence.

Recommended v1:

```text
FactoryMind AgentOS Runtime
  -> OpenTelemetry traces for execution visibility
  -> FactoryMind AgentOS Audit Ledger for durable governance records
  -> optional adapters: MLflow, Phoenix, Opik, LangSmith, OTLP backends
```

Do not rely on traces alone as the legal/audit source of truth. Traces may be sampled, redacted, retained for shorter periods, or stored in external systems.

## 3) Observability vs Audit
| Layer | Purpose | Example | Retention |
|---|---|---|---|
| Trace | Debug execution path | model call, tool call, retrieval span | short/medium |
| Metric | Monitor health | latency, cost, failure rate | medium |
| Log | Operational event | worker failed, retry exhausted | medium |
| Audit event | Durable governance evidence | skill promoted, approval granted, memory revoked | long |
| Evidence artifact | Explain why a change happened | eval report, promotion report | long |

FactoryMind AgentOS should support all five.

## 4) What Must Be Observable
Every agent session should expose:
- session lifecycle
- runtime state transitions
- model calls
- tool calls
- memory retrievals
- skill retrievals
- context assembly decisions
- confidence score inputs
- policy decisions
- eval runs
- candidate creation
- skill/memory promotions
- rollback events

If the agent gives a bad answer, we should be able to answer:
- What input did it receive?
- What memory did it retrieve?
- What skills did it load?
- What tools did it call?
- What policy decisions were made?
- What model/provider/version was used?
- What confidence basis was calculated?
- Which learned version was active?

## 5) Trace Architecture
Recommended trace hierarchy:

```text
session.invoke
  agent.run
    context.assemble
      memory.retrieve
      skill.retrieve
    model.call
    tool.call
    policy.check
    confidence.score
    output.emit
```

For learning:

```text
learning.run
  signal.extract
  memory.candidate.create
  skill.candidate.create
  eval.run
  safety.gate
  promotion.gate
  rollback.prepare
```

## 6) OpenTelemetry Strategy
Use OpenTelemetry as the vendor-neutral trace standard.

Why:
- portable
- widely supported
- works with existing observability backends
- GenAI semantic conventions now cover model, agent, tool, retrieval, and MCP-like spans

FactoryMind AgentOS should emit:
- normal service spans
- GenAI model spans
- agent invocation spans
- execute-tool spans
- retrieval spans
- custom FactoryMind AgentOS spans for memory/skill/promotion

Important:
- OpenTelemetry GenAI conventions are still evolving. FactoryMind AgentOS should follow them where possible, but keep internal audit schema stable.

## 7) FactoryMind AgentOS Audit Ledger
The audit ledger is the source of truth for governance and self-learning.

Required audit events:

| Event | When |
|---|---|
| `session.created` | new session starts |
| `session.state_changed` | state transition occurs |
| `agent.output_emitted` | final/question/error output emitted |
| `tool.called` | MCP/tool call attempted |
| `policy.decided` | policy decision made |
| `memory.candidate_created` | learning proposes memory |
| `memory.promoted` | memory becomes active |
| `memory.revoked` | memory blocked from future use |
| `skill.candidate_created` | learning proposes skill |
| `skill.promoted` | skill becomes active |
| `skill.rolled_back` | skill reverted |
| `eval.completed` | candidate eval finishes |
| `approval.requested` | human approval requested |
| `approval.decided` | approval accepted/rejected |
| `learning.promoted` | learning change activated |
| `learning.rolled_back` | learned behavior reverted |

## 8) Audit Event Schema
```json
{
  "event_id": "uuid",
  "event_type": "skill.promoted",
  "tenant_id": "string",
  "agent_id": "proposal_writer",
  "session_id": "uuid|null",
  "actor": {
    "type": "user|agent|system|learning_engine",
    "id": "string"
  },
  "target": {
    "type": "skill|memory|tool|policy|session|candidate",
    "id": "uuid",
    "version": "1.2.0"
  },
  "decision": "allow|deny|promote|reject|rollback|null",
  "risk_level": "low|medium|high|critical",
  "trace_id": "string",
  "span_id": "string",
  "payload_ref": "object_store_or_hash",
  "prev_event_hash": "sha256",
  "event_hash": "sha256",
  "created_at": "RFC3339"
}
```

Use hash chaining for tamper-evidence.

## 9) Payload Storage Rules
Do not put all raw content directly into traces or audit events.

Policy:
- traces can store redacted prompt/tool metadata
- audit events store hashes and references
- sensitive payloads go to encrypted object storage only if policy allows
- secrets should never be stored in trace or audit payloads
- model inputs/outputs must be redacted by data policy before long retention

## 10) Learning Traceability
For every active learned memory or skill, FactoryMind AgentOS must answer:
- Which sessions created it?
- Which feedback supported it?
- Which eval run approved it?
- Which policy gate allowed it?
- Which version did it replace?
- How can it be rolled back?
- When was it last used?
- Did it improve acceptance/confidence?

This requires linking:

```text
session_id
  -> feedback events
  -> candidate_id
  -> eval_run_id
  -> promotion_event_id
  -> active memory/skill version
```

## 11) Existing Observability Systems Researched
### OpenTelemetry
What it provides:
- vendor-neutral tracing, metrics, logs
- GenAI semantic conventions
- agent and tool span conventions
- OTLP export to many backends

Fit:
- best portable foundation

Gap:
- not an FactoryMind AgentOS audit ledger
- GenAI conventions are still evolving

Recommendation:
- use as default trace protocol.

### MLflow GenAI
What it provides:
- OpenTelemetry-compatible tracing
- prompt/version tracking
- evaluation and optimization support
- self-hostable open-source platform

Fit:
- strong for open-source, self-hosted observability/eval stack

Gap:
- FactoryMind AgentOS still needs own candidate/promotion ledger

Recommendation:
- strong adapter candidate.

### Phoenix / Arize
What it provides:
- OpenTelemetry-based LLM tracing
- datasets, experiments, evals
- model-agnostic evaluation and explanations

Fit:
- strong for trace debugging and eval workflow

Gap:
- FactoryMind AgentOS still owns learning governance

Recommendation:
- strong adapter candidate.

### Opik
What it provides:
- LLM tracing, evals, optimization runs
- open-source observability/eval tooling

Fit:
- strong match for learning/eval evidence

Gap:
- external system should not own final promotion

Recommendation:
- strong adapter candidate.

### LangSmith
What it provides:
- LangGraph/LangChain-native traces, datasets, experiments, evals

Fit:
- useful if LangGraph is runtime

Gap:
- lock-in risk if used as only trace/evidence store

Recommendation:
- optional adapter, not required core.

### OpenInference
What it provides:
- LLM tracing semantic conventions used by Phoenix ecosystem

Fit:
- useful reference for span attributes

Gap:
- another convention layer; avoid depending exclusively on it.

Recommendation:
- support through Phoenix/OpenTelemetry adapter.

## 12) Metrics
FactoryMind AgentOS should emit metrics for:

Runtime:
- sessions started/completed/failed
- retry count
- tool call success/failure
- model latency
- tool latency
- cost per session

Learning:
- candidates created
- candidates promoted/rejected
- rollback count
- skill activation rate
- memory retrieval hit rate
- acceptance rate by agent version
- confidence calibration error

Security:
- policy denials
- approval requests
- prompt injection detections
- sensitive data redactions
- unauthorized tool attempts

## 13) Incident Artifact
When a session fails badly, FactoryMind AgentOS should generate an incident artifact:

```json
{
  "incident_id": "uuid",
  "session_id": "uuid",
  "agent_id": "project_selector",
  "active_versions": {
    "agent": "1.3.0",
    "skills": [],
    "memory_snapshot": "hash"
  },
  "failure_type": "wrong_output|policy_violation|tool_failure|low_confidence|security",
  "trace_id": "string",
  "audit_event_ids": [],
  "retrieved_memory_ids": [],
  "activated_skill_ids": [],
  "tool_call_ids": [],
  "recommended_action": "rollback_skill|revoke_memory|add_eval_case|manual_review"
}
```

## 14) Build-vs-Wrap Decision
Build:
- audit ledger
- audit event schema
- learning traceability links
- incident artifact format
- metrics definitions
- redaction/payload storage rules

Wrap:
- OpenTelemetry SDK
- OTLP collectors/backends
- MLflow/Phoenix/Opik/LangSmith adapters

Do not outsource:
- audit source of truth
- learning evidence chain
- promotion/rollback evidence
- sensitive payload policy

## 15) Final Recommendation
For FactoryMind AgentOS v1:
- emit OpenTelemetry traces using GenAI conventions where possible
- store durable FactoryMind AgentOS audit events in Postgres
- hash-chain audit events for tamper evidence
- store raw sensitive payloads separately or not at all, according to policy
- include trace IDs in audit events
- support adapters to MLflow, Phoenix, Opik, LangSmith later

This split gives us:
- practical debugging now
- industrial audit trail
- vendor portability
- clear evidence for self-learning decisions

## 16) Sources
- OpenTelemetry GenAI semantic conventions: https://opentelemetry.io/docs/specs/semconv/gen-ai/
- OpenTelemetry GenAI client spans: https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/
- OpenTelemetry GenAI agent spans: https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/
- OpenTelemetry semantic conventions: https://opentelemetry.io/docs/concepts/semantic-conventions/
- OpenInference semantic conventions: https://arize-ai.github.io/openinference/spec/semantic_conventions.html
- MLflow OpenTelemetry integration: https://mlflow.org/docs/latest/genai/tracing/opentelemetry/
- MLflow tracing overview: https://mlflow.org/docs/latest/genai/tracing
- Phoenix tracing docs: https://arize.com/docs/phoenix/tracing/llm-traces
- LangSmith observability concepts: https://docs.langchain.com/langsmith/observability-concepts
- LangSmith evaluation concepts: https://docs.langchain.com/langsmith/evaluation-concepts
- Opik observability docs: https://www.comet.com/docs/opik/tracing/getting-started
- Mind the Metrics paper: https://arxiv.org/abs/2506.11019
- Eval Factsheets paper: https://arxiv.org/abs/2512.04062

Research inference:
- Observability tools can show what happened, but FactoryMind AgentOS needs its own audit ledger to prove why learned behavior changed and how to roll it back.

