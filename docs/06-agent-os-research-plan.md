# FactoryMind AgentOS Research Plan

Access date: 2026-05-01

## 1) Research Objective
Research how to build an installable **FactoryMind AgentOS** package by reusing stable existing systems where possible, then building the unique self-learning, governance, and packaging layer on top.

The research should answer:
- Which existing systems can safely handle sessions, state, execution, tracing, memory, and evals?
- Which parts must be built by us because existing systems do not provide them well?
- How should the self-learning layer work in an industrial, auditable, reversible way?
- What should the v1 architecture reuse, wrap, or avoid?

## 2) Research Principle
Do not assume everything must be built from scratch.

The target design should be:

```text
FactoryMind AgentOS SDK and control layer
  -> existing runtime/session engine where suitable
  -> existing eval/observability engine where suitable
  -> existing optimization/self-learning algorithms where suitable
  -> our governance, promotion, packaging, and adapter layer
```

The research must separate:
- systems we can use directly
- systems we can wrap through adapters
- systems we should only learn from
- systems we should avoid as core dependencies

## 3) Research Blocks
### Block A: Agent Runtime and Session Engine
Purpose:
- Find the best existing engine for sessions, state transitions, checkpoints, retries, interrupts, human-in-the-loop, and durable execution.

Systems to research:
- LangGraph
- LangGraph Platform / LangSmith Deployment
- Microsoft Agent Framework
- CrewAI Flows
- Temporal as a non-agent durable workflow engine
- OpenAI Agents SDK

Research questions:
- Does it support durable session state?
- Can execution pause and resume after human feedback?
- Can we persist checkpoints outside the vendor platform?
- Can we run it self-hosted?
- Can it support our `init`, `feedback`, `accept` protocol?
- How easy is it to wrap behind an `AgentRuntimeAdapter`?
- What are the failure modes and operational risks?

Expected output:
- runtime comparison matrix
- recommended v1 runtime
- adapter interface proposal

### Block B: Self-Learning Engine
Purpose:
- Define how agents improve themselves over time without unsafe self-modification.

Systems and research ideas:
- Reflexion
- Self-Refine
- DSPy optimizers
- TextGrad
- AgentDevel
- AgentFactory
- SEAgent
- AgentEvolver
- Opik agent optimization

Research questions:
- What does each approach actually update: prompt, memory, examples, tool routing, code, model weights?
- Does it require labeled data?
- Can it run offline against eval sets?
- Can it produce auditable candidate changes?
- Can changes be rolled back?
- What failure modes are documented, such as reward hacking or evaluator drift?
- Which methods are production-safe enough for v1?

Expected output:
- learning method taxonomy
- v1 self-learning design
- candidate improvement schema
- promotion and rollback policy

### Block C: Evaluation and Promotion Gates
Purpose:
- Research how to decide whether a learned change is safe and better.

Systems to research:
- Opik
- Promptfoo
- LangSmith evals
- OpenAI agent evals
- Ragas for retrieval quality
- custom pytest-based evals

Research questions:
- Can it evaluate agent traces, not only single prompts?
- Can it run in CI/CD?
- Can it compare current config vs candidate config?
- Can it detect hallucination, tool misuse, and retrieval failures?
- Can it store datasets from real failed sessions?
- Is it open source or self-hostable?
- Does it support confidence calibration?

Expected output:
- eval platform comparison
- default eval dataset format
- promotion threshold proposal
- CI/CD integration plan

### Block D: Memory and Context System
Purpose:
- Define agent memory as an industrial subsystem, not just vector search.

Systems to research:
- CrewAI memory
- LangGraph persistence/checkpointing
- LangMem if relevant
- MemGPT / Letta
- LlamaIndex memory/RAG patterns
- Postgres + pgvector
- Redis session state

Research questions:
- What memory types are needed: session, semantic, episodic, procedural, feedback, policy?
- What metadata must every memory item carry?
- How do we support TTL, deletion, revocation, and provenance?
- How do we prevent bad feedback from contaminating long-term memory?
- How should the context assembler select and compress memory?
- What should be stored locally vs in external systems?

Expected output:
- memory taxonomy
- memory item schema
- context assembler algorithm
- storage adapter recommendation

### Block E: Tool and MCP Gateway
Purpose:
- Research how to safely expose external tools and MCP servers to agents.

Systems to research:
- MCP specification and SDKs
- LangGraph tool calling patterns
- OpenAI tool/function calling
- Flowise MCP support
- Dify tool/plugin model
- CrewAI tools

Research questions:
- How should tools be registered?
- How should per-agent permissions be declared?
- How do we validate tool input/output schemas?
- How do we sanitize MCP output as untrusted data?
- How do we enforce timeouts, size limits, rate limits, and scopes?
- How do we support read-only vs write-capable tools?
- How should tool calls appear in audit logs?

Expected output:
- tool manifest schema
- MCP gateway design
- permission model
- tool failure/recovery taxonomy

### Block F: Policy, Security, and Governance
Purpose:
- Define the rules that make the FactoryMind AgentOS safe enough for commercial systems.

Systems and standards to research:
- OWASP LLM Top 10
- NIST AI RMF and GenAI Profile
- SOC2 trust criteria
- GDPR privacy/security requirements
- Open Policy Agent
- guardrails libraries such as Guardrails AI, NeMo Guardrails, Llama Guard/Prompt Guard

Research questions:
- Which controls should ship as defaults in the package?
- Which controls should be hooks/adapters?
- How do we classify data before sending it to an LLM?
- How do we prevent prompt injection and tool abuse?
- How do we enforce human approval gates?
- What should be auditable for compliance?

Expected output:
- default policy pack
- redaction/data boundary strategy
- approval gate model
- compliance evidence checklist

### Block G: Observability, Audit, and Traceability
Purpose:
- Ensure every session, tool call, learning candidate, promotion, and rollback is traceable.

Systems to research:
- OpenTelemetry
- LangSmith traces
- Opik traces
- Phoenix / Arize
- custom audit event store

Research questions:
- What trace schema should FactoryMind AgentOS own?
- Can traces be exported to existing observability platforms?
- How do we make audit logs tamper-evident?
- How do we connect user feedback to exact agent versions and prompts?
- How do we debug learned regressions?

Expected output:
- trace event schema
- audit log schema
- observability adapter comparison
- debugging workflow

### Block H: SDK, Package, CLI, and Developer Experience
Purpose:
- Research how the FactoryMind AgentOS should be installed and used by developers.

Systems to study:
- LangChain/LangGraph SDK style
- CrewAI project structure
- Dify/Flowise template ideas
- FastAPI/Pydantic package patterns
- Python packaging best practices

Research questions:
- What should `pip install agent-os` provide?
- Should agents be Python classes, YAML manifests, or both?
- What CLI commands are needed?
- How should a developer create a new agent?
- How should adapters be registered?
- How do we version agent definitions?

Expected output:
- SDK design proposal
- CLI command list
- starter project template
- package module structure

### Block I: Deployment and Industrial Operations
Purpose:
- Determine how FactoryMind AgentOS can run reliably in local, Docker, and AWS/self-hosted production environments.

Systems to research:
- Docker Compose
- AWS ECS
- Kubernetes
- Postgres/RDS
- Redis/ElastiCache
- SQS/Celery/Temporal queues
- AWS Secrets Manager and KMS

Research questions:
- What is the minimum local deployment?
- What is the minimum production deployment?
- Which components must be stateless?
- Where are checkpoints stored?
- How do we scale workers?
- How do we handle secrets?
- What backup/restore guarantees are needed?

Expected output:
- local deployment reference
- AWS deployment reference
- production readiness checklist
- SLO proposal

### Block J: Existing Platform Build-vs-Wrap Decision
Purpose:
- Decide whether to build on top of an existing platform, wrap multiple components, or only borrow concepts.

Candidate base strategies:
- LangGraph runtime + our FactoryMind AgentOS layer
- LangGraph + Opik + DSPy + MCP gateway
- Dify/Flowise as app-builder base plus self-learning layer
- Microsoft Agent Framework base
- Temporal runtime plus custom agent layer

Research questions:
- Which base reduces work without locking us into the wrong product shape?
- Which base is library-friendly and embeddable?
- Which base supports self-hosted industrial use?
- Which base leaves enough control for self-learning and governance?
- What are the security and maintenance risks?

Expected output:
- build-vs-wrap recommendation
- preferred v1 stack
- fallback stack
- components to avoid as core dependencies

## 4) Research Deliverables
The research should produce these Markdown files:

1. `07-runtime-and-session-engine-research.md`
2. `08-self-learning-engine-research.md`
3. `09-evaluation-and-promotion-research.md`
4. `10-memory-and-context-research.md`
5. `11-tool-mcp-gateway-research.md`
6. `12-policy-security-governance-research.md`
7. `13-observability-audit-research.md`
8. `14-sdk-package-cli-research.md`
9. `15-deployment-operations-research.md`
10. `16-build-vs-wrap-final-recommendation.md`

## 5) Research Method
For each block:
- prioritize official docs, GitHub repos, papers, and standards
- identify what the system provides directly
- identify what it does not provide
- evaluate self-hosting and industrial readiness
- evaluate whether it can be wrapped behind an adapter
- record security and reliability risks
- end with a concrete recommendation

## 6) Scoring Criteria
Each candidate system should be scored from `1` to `5` on:
- embeddability as a library
- self-host readiness
- session durability
- human-in-the-loop support
- eval and optimization support
- observability
- security/governance hooks
- adapter friendliness
- operational complexity
- lock-in risk

## 7) Initial Hypothesis
The likely best direction is:

```text
FactoryMind AgentOS package
  -> LangGraph for runtime/session/checkpoint execution
  -> MCP gateway owned by us
  -> Opik or Promptfoo for eval/optimization support
  -> DSPy/TextGrad-inspired optimizer for learning candidates
  -> Postgres/pgvector + Redis for memory/state
  -> OpenTelemetry/custom audit log for traces
  -> our SDK, CLI, policy, promotion, rollback, and learning modes
```

This hypothesis must be validated by the research blocks before final architecture selection.

Status:
- Block A, Agent Runtime and Session Engine: documented in `docs/07-runtime-and-session-engine-research.md`.
- Block B, Self-Learning Engine: documented in `docs/08-self-learning-engine-research.md`.
- Block C, Evaluation and Promotion Gates: documented in `docs/09-evaluation-and-promotion-research.md`.
- Block D, Memory and Context System: documented in `docs/10-memory-and-context-research.md`.
- Block E, Tool and MCP Gateway: documented in `docs/11-tool-mcp-gateway-research.md`.
- Block F, Policy, Security, and Governance: documented in `docs/12-policy-security-governance-research.md`.
- Block G, Observability, Audit, and Traceability: documented in `docs/13-observability-audit-research.md`.
- Block H, SDK, Package, CLI, and Developer Experience: documented in `docs/14-sdk-package-cli-research.md`.
- Block I, Deployment and Industrial Operations: documented in `docs/15-deployment-operations-research.md`.
- Block J, Existing Platform Build-vs-Wrap Decision: documented in `docs/16-build-vs-wrap-final-recommendation.md`.

## 8) Key Decision Gates
These decisions are now answered by the research package:
- Runtime: `AgentRuntimeAdapter` from day one, with `LangGraphRuntimeAdapter` as the V1 implementation.
- Learning: custom memory/skill learning engine first; DSPy/TextGrad/Opik-style optimizers later as adapters after eval datasets exist.
- Eval: built-in deterministic eval runner first; Promptfoo and Opik adapters next; LangSmith/OpenAI evals optional.
- Memory: Postgres + pgvector for durable memory/skills; Redis for cache, queues, and locks.
- Packaging: Python code-first SDK plus YAML manifests for portability.
- Deployment: Docker Compose for local/single-server and AWS ECS/Fargate reference for production.
- UI: no UI in V1; CLI/API first, optional control plane later.

Research status: complete for architecture planning. Next step is implementation planning and package scaffolding.

