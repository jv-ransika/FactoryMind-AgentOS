# Agent Runtime and Session Engine Research

Access date: 2026-05-01

## 1) Question
How should the FactoryMind AgentOS handle sessions, runtime execution, pause/resume, checkpoints, retries, and human feedback loops?

This block answers whether we should:
- build the session engine ourselves
- use LangGraph directly
- use Microsoft Agent Framework
- use Temporal or another durable workflow engine
- use an MCP-native framework such as `mcp-agent`
- hide the runtime behind an adapter so the FactoryMind AgentOS can change runtime later

## 2) Short Answer
Do not build the full session engine from scratch.

Recommended v1 approach:

```text
FactoryMind AgentOS Session API
  -> AgentRuntimeAdapter interface
  -> LangGraphRuntimeAdapter first
  -> Postgres checkpoint/audit storage
  -> optional TemporalRuntimeAdapter later for long-running industrial jobs
```

Meaning:
- FactoryMind AgentOS owns the public protocol: `init`, `feedback`, `accept`, `final`, `question`, typed errors.
- FactoryMind AgentOS owns learning, policy, tool governance, audit, and promotion.
- LangGraph handles the first runtime implementation: state graph, checkpoints, interrupts, pause/resume.
- Temporal is not the first runtime, but should be researched as a phase-2 durability backend for long-running jobs.

## 3) What The Runtime Must Do
The runtime/session engine must support:

| Capability | Requirement |
|---|---|
| Session identity | Every run belongs to a durable `session_id` |
| Message ordering | `message_id`, `state_version`, and idempotency records |
| Pause/resume | Agent can stop and wait for human feedback |
| Checkpoints | Agent state can survive crash/restart |
| Typed outputs | `final`, `question`, `error_retryable`, `error_policy`, `error_tool`, `error_fatal` |
| Tool orchestration | Calls MCP tools through FactoryMind AgentOS gateway only |
| Retry control | Model/tool calls have bounded retries and timeout budgets |
| Auditability | Every state transition and tool call becomes an event |
| Learning handoff | `accept` triggers reflection job after session completion |
| Runtime portability | Runtime should be replaceable behind adapter |

## 4) Candidate Systems
### LangGraph
What it gives:
- graph-based state machine
- persistence/checkpointing
- threads and state history
- interrupts for human-in-the-loop
- replay/time-travel style debugging
- self-hosted standalone agent server option
- LangSmith integration for tracing, deployment, and evals

Why it fits:
- It maps naturally to our session loop.
- It is Python-friendly.
- It can pause on `question` and resume on `feedback`.
- It gives checkpoint primitives we should not rebuild.

Risks:
- LangGraph should be kept behind our adapter to avoid product lock-in.
- LangGraph Platform/LangSmith deployment may introduce managed-platform dependency if used too early.
- Checkpoint state is not the same as business memory; we still need our own memory and audit schema.

Verdict:
- Best v1 runtime foundation.

### Microsoft Agent Framework
What it gives:
- agents, tools, conversations, memory/persistence, workflows
- Python and .NET support
- workflow builder and executor model
- Microsoft/Azure alignment
- migration path from AutoGen/Semantic Kernel direction

Why it may help:
- Strong candidate for enterprise Microsoft ecosystems.
- Good to keep as a future adapter if customers are Azure/Microsoft-heavy.

Risks:
- Newer ecosystem compared with LangGraph for this exact Python-first use case.
- Adds framework weight before we have proven the FactoryMind AgentOS abstraction.
- Our first integration is MCP/project DB, not Microsoft 365/Azure-native workflows.

Verdict:
- Do not use as v1 core.
- Revisit as `MicrosoftAgentRuntimeAdapter` later.

### Temporal
What it gives:
- durable workflow execution
- crash recovery
- activity retries
- workflow history
- signals/queries for human interaction
- strong production reliability model

Why it matters:
- Temporal is stronger than agent frameworks for industrial durability.
- Good fit for long-running sessions, delayed approvals, background reflection, and promotion workflows.

Risks:
- Not agent-native; it does not solve prompts, tools, memory, or LLM behavior.
- Requires deterministic workflow design discipline.
- Adds operational complexity for a one-engineer v1.

Verdict:
- Not v1 core runtime.
- Strong phase-2 backend for durable jobs:
  - reflection pipeline
  - promotion pipeline
  - long-running agents
  - scheduled evaluation jobs

### mcp-agent
What it gives:
- MCP-native agent framework
- composable agent patterns
- MCP server lifecycle management
- Temporal-backed durable agents
- model-agnostic workflows

Why it is interesting:
- It is much closer to our MCP-first direction than many other frameworks.
- It may reduce work in the tool/MCP layer and durable execution layer.
- It supports Temporal without changing agent code, based on its documentation.

Risks:
- Need deeper evaluation before trusting it as FactoryMind AgentOS foundation.
- It may overlap with our intended product surface.
- We need to verify maturity, licensing, extension points, security model, and how much control we retain.

Verdict:
- High-priority research candidate.
- Do not adopt before comparing it against LangGraph for our exact protocol and self-learning needs.

### OpenAI Agents SDK
What it gives:
- OpenAI-native agents, tools, handoffs, tracing patterns
- useful provider integration if OpenAI is the only model provider in v1

Why it may help:
- Could simplify OpenAI integration.
- Works well if we stay OpenAI-only.

Risks:
- Provider lock-in.
- Not an FactoryMind AgentOS runtime by itself.
- Does not own our self-learning, memory governance, or deployment layer.

Verdict:
- Use as an adapter/reference, not the core runtime.

### CrewAI Flows
What it gives:
- agents, crews, flows, memory, and task composition

Why it may help:
- Good reference for agent/team abstractions and developer ergonomics.

Risks:
- Less aligned with our strict session protocol and industrial self-learning layer.
- May be too application-builder oriented for an embeddable FactoryMind AgentOS package.

Verdict:
- Reference only for now.

## 5) Recommended Runtime Architecture
FactoryMind AgentOS should own the stable public interface and use runtime adapters internally.

```text
agent_os.runtime
  RuntimeAdapter
    start_session()
    continue_session()
    interrupt_session()
    resume_session()
    get_checkpoint()
    list_events()
    cancel_session()

  LangGraphRuntimeAdapter
  TemporalRuntimeAdapter later
  MicrosoftAgentRuntimeAdapter later
```

FactoryMind AgentOS session manager should sit above the runtime adapter:

```text
Client/App
  -> FactoryMind AgentOS Session API
  -> Session Manager
  -> Policy Precheck
  -> RuntimeAdapter
  -> Tool Gateway
  -> Audit Log
  -> Reflection Queue on accept
```

## 6) Session State Model
Recommended canonical states:

| State | Meaning |
|---|---|
| `NEW` | Session exists but has not started |
| `RUNNING` | Agent is executing |
| `WAITING_HUMAN` | Agent needs feedback, approval, or acceptance |
| `COMPLETED` | Human accepted final output |
| `FAILED` | Fatal unrecoverable error |
| `CANCELLED` | User/operator cancelled session |

Recommended transitions:

| Input/Event | From | To |
|---|---|---|
| `init` | `NEW` | `RUNNING` |
| `question` | `RUNNING` | `WAITING_HUMAN` |
| `final` | `RUNNING` | `WAITING_HUMAN` |
| `feedback` | `WAITING_HUMAN` | `RUNNING` |
| `accept` | `WAITING_HUMAN` | `COMPLETED` |
| `error_retryable` | `RUNNING` | `RUNNING` or `WAITING_HUMAN` |
| `error_policy` | `RUNNING` | `WAITING_HUMAN` |
| `error_fatal` | `RUNNING` | `FAILED` |
| `cancel` | any non-terminal | `CANCELLED` |

## 7) What FactoryMind AgentOS Must Own Separately From Runtime
Even if LangGraph handles checkpoints, FactoryMind AgentOS must still own:

- session protocol
- idempotency records
- state transition validation
- audit event schema
- tool permission policy
- typed error policy
- memory governance
- learning-mode configuration
- reflection trigger after `accept`
- versioning of agent config
- promotion and rollback records

Reason:
- Runtime checkpoint state is not enough for an industrial FactoryMind AgentOS.
- Runtime history is not the same as compliance audit history.
- Runtime memory is not the same as self-learning memory.

## 8) Handling Human Feedback
Use runtime interrupt/pause primitives for human-in-the-loop.

Flow:
1. User sends `init`.
2. Session Manager creates session and starts LangGraph thread.
3. Runtime executes until it can produce `final`, `question`, or typed error.
4. `question` or `final` pauses the session in `WAITING_HUMAN`.
5. User sends `feedback` or `accept`.
6. `feedback` resumes the same runtime thread with new input.
7. `accept` ends execution and queues reflection.

Important rule:
- `accept` should not directly mutate agent behavior.
- `accept` only creates a learning signal for the reflection pipeline.

## 9) Reliability Rules
The runtime/session layer must implement:

- idempotency by `message_id`
- optimistic concurrency by `state_version`
- per-session retry budgets
- per-tool timeout budgets
- checkpoint after every major runtime step
- audit event for every state transition
- cancellation support
- dead-letter handling for failed background jobs
- replay support for debugging

## 10) Runtime Decision Matrix
| Candidate | Session Durability | Human Loop | Self-Host | Adapter Fit | Complexity | v1 Fit |
|---|---:|---:|---:|---:|---:|---:|
| LangGraph | 5 | 5 | 4 | 5 | 3 | 5 |
| Microsoft Agent Framework | 4 | 4 | 4 | 4 | 4 | 3 |
| Temporal | 5 | 4 | 5 | 4 | 5 | 3 |
| mcp-agent | 4 | 4 | 4 | 4 | 3 | 4 |
| OpenAI Agents SDK | 3 | 3 | 3 | 4 | 2 | 3 |
| CrewAI Flows | 3 | 3 | 4 | 3 | 3 | 2 |

Scoring:
- `1` weak
- `5` strong
- v1 fit considers Python-first, one-engineer implementation, MCP use, and FactoryMind AgentOS extensibility.

## 11) Recommendation
Use a runtime adapter architecture from day one, with LangGraph as the first implementation.

Recommended v1:

```text
FactoryMind AgentOS public protocol
  -> SessionManager
  -> LangGraphRuntimeAdapter
  -> Postgres checkpoint/audit store
  -> MCPGateway
  -> ReflectionQueue on accept
```

Recommended phase 2:

```text
FactoryMind AgentOS public protocol
  -> RuntimeAdapter
    -> LangGraph for agent-native graph sessions
    -> Temporal for long-running durable jobs
    -> mcp-agent adapter if research proves it reduces MCP/runtime work
```

Do not expose LangGraph concepts directly to users of FactoryMind AgentOS. Users should define agents using FactoryMind AgentOS concepts; LangGraph is an internal engine.

## 12) Open Questions For Next Research
These should be answered before implementation:

1. Should v1 use LangGraph checkpointers directly, or store our own session state and use LangGraph only for execution?
2. Should the first checkpoint store be Postgres, SQLite for local dev, or both?
3. Should FactoryMind AgentOS expose a REST session API in v1, or only a Python SDK?
4. Should `mcp-agent` replace our MCP gateway, or be only a reference?
5. Should Temporal be introduced only for reflection/eval jobs first, before agent sessions?
6. How much of LangSmith/Opik tracing should be optional vs built into the runtime adapter?

## 13) Sources
- LangGraph persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- LangGraph checkpoint reference: https://reference.langchain.com/python/langgraph/checkpoints/
- LangGraph human-in-the-loop interrupts: https://docs.langchain.com/oss/python/langgraph/human-in-the-loop
- LangGraph standalone self-hosted server: https://docs.langchain.com/langgraph-platform/deploy-standalone-server
- LangSmith deployment: https://docs.langchain.com/oss/python/langgraph/deploy
- LangSmith observability concepts: https://docs.langchain.com/langsmith/observability-concepts
- Microsoft Agent Framework docs: https://learn.microsoft.com/en-us/agent-framework/
- Microsoft Agent Framework workflows: https://learn.microsoft.com/en-us/agent-framework/workflows/workflows
- Microsoft AutoGen repository: https://github.com/microsoft/autogen
- Temporal docs: https://docs.temporal.io/
- mcp-agent repository: https://github.com/lastmile-ai/mcp-agent
- mcp-agent durable agents: https://docs.mcp-agent.com/mcp-agent-sdk/advanced/durable-agents
- mcp-agent workflows overview: https://docs.mcp-agent.com/workflows/overview

