# FactoryMind AgentOS Main Goal, Alignment Review, and Existing Platform Research

Access date: 2026-05-01

## 1) Main Goal
The goal is to build an installable library/package that acts as an **FactoryMind AgentOS**.

This is not a single agent. It is the reusable operating layer that lets developers and companies:
- define agents
- attach tools and MCP servers
- run agents reliably
- scale agents in production
- observe and audit agent behavior
- turn self-learning on or off per agent
- improve agents over time in a controlled, trackable, reversible way

The package should let a user install it into their own system and create specialized agents such as:
- proposal writing agents
- project selection agents
- keyword extraction agents
- company-personalized workflow agents

The platform must be suitable for industrial and commercial usage, not only demos or experiments.

## 2) Core Product Ambition
The FactoryMind AgentOS should provide these built-in platform layers:

| Layer | Purpose |
|---|---|
| Agent definition SDK | Standard way to declare an agent, its purpose, tools, memory, policy, output schema, and learning mode |
| Runtime engine | Executes agent sessions with state, checkpoints, retries, and human feedback loops |
| Tool/MCP gateway | Controlled interface for all tools and external systems |
| Memory system | Short-term session memory, long-term agent memory, feedback memory, and provenance metadata |
| Self-learning engine | Converts feedback and outcomes into candidate improvements |
| Eval and promotion system | Tests candidate improvements before activation |
| Policy and safety layer | Enforces permissions, approvals, data boundaries, and action rules |
| Observability and audit | Full traces, tool logs, version history, and explainable improvement records |
| Deployment adapters | Local, Docker, and AWS/self-hosted deployment paths |

## 3) Self-Learning Definition
Self-learning must not mean uncontrolled self-modification.

For this platform, self-learning means:
- the agent collects feedback and outcomes
- the system extracts improvement candidates
- improvements are evaluated against tests and historical failures
- safe changes can be promoted according to policy
- every change is versioned, auditable, and reversible

Allowed learning artifacts:
- prompts
- examples/few-shot demonstrations
- retrieval rules
- ranking weights
- tool routing rules
- memory summaries
- procedural recipes
- evaluation datasets

Not allowed in v1:
- autonomous production code rewrite
- autonomous permission expansion
- autonomous safety policy weakening
- unreviewed model fine-tuning on sensitive data

## 4) Learning Modes Per Agent
Each agent should have a configurable learning mode:

| Mode | Behavior |
|---|---|
| `off` | No learning, only normal execution |
| `collect_only` | Store feedback and traces, but do not create changes |
| `suggest` | Generate improvement candidates, but require approval |
| `auto_low_risk` | Auto-promote low-risk prompt/retrieval changes only after eval pass |
| `manual_high_risk` | High-risk changes always require human approval |

Default for industrial usage:
- `collect_only` during initial rollout
- `suggest` after eval coverage exists
- `auto_low_risk` only after confidence calibration and rollback are proven

## 5) Current Plan Alignment Review
The current documents are partially aligned, but they still read too much like an application platform for a few agents. They need to be reframed as an installable FactoryMind AgentOS package.

| Area | Current Alignment | Gap |
|---|---|---|
| Runtime architecture | Strong | Needs package/library API boundaries |
| LangGraph-first execution | Strong | Should be an internal runtime option, not the product identity |
| MCP gateway | Strong | Needs formal tool contract and plugin registry |
| Session protocol | Strong | Needs SDK-level schemas and lifecycle hooks |
| Self-learning | Medium | Needs a dedicated learning engine design with modes, promotion rules, and rollback |
| Memory | Medium | Needs memory schema, provenance, TTL, revocation, and what can/cannot be learned |
| Industrial reliability | Medium-strong | Needs concrete SLOs, deployment adapters, and operator controls |
| Security/compliance | Medium-strong | Needs package-level defaults: secrets, RBAC hooks, audit persistence, redaction |
| Existing platform analysis | Medium | Needs deeper distinction between orchestration tools and self-learning systems |
| Product packaging | Weak | Needs installable SDK/API design, CLI, templates, and extension points |

Conclusion:
- The plan is architecturally useful.
- It is not yet fully aligned with the FactoryMind AgentOS ambition.
- The next step should be a package-oriented specification: SDK, runtime contracts, learning engine, storage adapters, and deployment adapters.

## 6) Existing Platform Research Summary
No reviewed platform fully matches the desired FactoryMind AgentOS with reliable, industrial self-learning as a first-class built-in capability.

Most existing platforms fall into four categories:
- agent orchestration frameworks
- visual app/agent builders
- observability/evaluation platforms
- research systems for self-improvement

Your opportunity is to combine these ideas into a reliable installable runtime with self-learning controls.

## 7) Platform Comparison Against FactoryMind AgentOS Goal
| Platform/System | What It Provides | Self-Learning Fit | Industrial Fit | Assessment |
|---|---|---|---|---|
| LangGraph / LangSmith | Stateful agent orchestration, durable execution, human-in-the-loop, observability/evals | Low-medium: supports the runtime needed for learning, but does not provide a full self-learning OS | High | Best runtime foundation, not a full FactoryMind AgentOS by itself |
| Microsoft Agent Framework / Semantic Kernel / AutoGen path | Enterprise-oriented agent framework, multi-agent orchestration, Microsoft ecosystem path | Low-medium: useful abstractions, not a complete autonomous learning layer | High in Microsoft/Azure contexts | Useful later, not v1 core |
| CrewAI | Agents, crews, flows, memory, knowledge, enterprise console | Medium for memory/agent composition, low for controlled self-learning promotion | Medium-high | Good concepts, but not enough for your reliable self-learning OS goal |
| Dify | Open-source visual platform for agentic workflows, tools, knowledge, deployment | Low-medium: more app builder than self-learning OS | Medium | Good reference for UX/platform packaging, not core library foundation |
| Flowise | Visual builder, agentflows, MCP, evaluations, HITL, teams/workspaces | Low-medium: strong builder features, self-learning not primary | Medium | Useful reference for builder UX, but not ideal as secure core runtime |
| AutoGPT Platform | Autonomous agent platform and marketplace concept | Low-medium: autonomy focus, less evidence of industrial self-learning controls | Medium | Useful historical reference, not enough for reliable FactoryMind AgentOS core |
| SuperAGI | Autonomous agent framework/platform | Low-medium: agent management and tools, not rigorous learning promotion | Medium | Reference only |
| OpenAI Agents SDK | Lightweight agent SDK, tools, handoffs, tracing, OpenAI-native evals | Low-medium: strong execution primitives, not self-hosted FactoryMind AgentOS | Medium-high if OpenAI-only is acceptable | Useful provider/runtime option, not full OS |
| DSPy | Optimizes LM programs/prompts against metrics | High for learning engine component | Medium | Strong candidate for controlled prompt/example optimization |
| Opik | Open-source LLM observability, evals, optimization, tracing | High for eval/optimization layer | High | Strong candidate for learning and monitoring subsystem |
| Promptfoo | Prompt and LLM app evals, CI-friendly tests | Medium-high for eval gates | Medium-high | Strong lightweight eval gate option |
| Reflexion / Self-Refine / TextGrad | Research patterns for self-feedback and improvement | High conceptually | Low as production platform | Useful algorithms, not deployable platform |
| AgentFactory / AgentDevel / SEAgent / AgentEvolver | Research on self-evolving agents | High research relevance | Low-medium today | Important design inspiration, not production dependency |

## 8) Self-Learning Research Findings
The self-learning part should be treated as release engineering, not magic.

Key findings:
- Reflexion shows that agents can improve by converting feedback into verbal memory for future attempts.
- Self-Refine shows iterative feedback and refinement can improve outputs without model training.
- TextGrad and DSPy show that prompts/programs can be optimized using textual feedback and metrics.
- AgentDevel is especially aligned with industrial needs because it frames self-evolving agents as auditable release engineering.
- AgentFactory is relevant because it stores successful solutions as reusable executable subagents, but this is higher risk and should not be v1 behavior.

Industrial conclusion:
- The reliable path is not "agent changes itself directly."
- The reliable path is "agent proposes a versioned improvement, evals test it, policy gates it, rollout promotes it, rollback can undo it."

## 9) Recommended FactoryMind AgentOS Architecture Direction
The FactoryMind AgentOS should be built as a package with these modules:

```text
agent_os/
  sdk/                 # Agent definitions, schemas, decorators
  runtime/             # LangGraph-backed session execution
  protocol/            # init/feedback/accept and output contracts
  tools/               # MCP gateway, tool registry, permissions
  memory/              # session, long-term, feedback, provenance stores
  learning/            # reflection, candidate generation, DSPy/TextGrad-style optimizers
  evals/               # regression tests, replay, scoring, confidence calibration
  policy/              # action gates, approvals, redaction, data rules
  observability/       # traces, audit logs, metrics
  adapters/            # OpenAI, Postgres, Redis, AWS, local Docker
  cli/                 # create-agent, run-agent, eval-agent, promote-candidate
```

The product API should feel like:

```python
from agent_os import Agent, LearningMode, tool

project_selector = Agent(
    name="project_selector",
    goal="Select the best project using company criteria",
    learning_mode=LearningMode.SUGGEST,
    tools=["project_db.search", "project_db.get_project"],
    memory_policy="company_confidential",
)
```

## 10) Required Industrial Guarantees
The FactoryMind AgentOS should provide these guarantees by default:
- every session is traceable
- every tool call is logged
- every learned change is versioned
- every promoted change has eval evidence
- every promoted change has rollback
- every agent has scoped tool permissions
- every memory item has provenance and retention policy
- sensitive data can be redacted or blocked before model calls
- self-learning can be disabled per agent

## 11) Main Weaknesses in the Current Plan
| Weakness | Improvement Needed |
|---|---|
| It still talks like a platform/app, not a library/package | Add SDK, CLI, adapter, and extension contracts |
| Self-learning is described but not formalized | Add learning modes, candidate schema, promotion pipeline |
| Memory is too generic | Define memory item schema with provenance, confidence, TTL, revocation |
| Industrial reliability is high-level | Define SLOs, retries, queues, checkpoint storage, deployment templates |
| Evaluation is mentioned but not productized | Add eval dataset format, replay runner, promotion threshold |
| Tool/MCP controls are not concrete enough | Define tool manifest, scopes, timeout, result-size limits, data classification |
| Existing platforms are treated as possible foundations | Clarify they are components/references, not complete replacements |

## 12) Open Questions Before Implementation
1. Should the first deliverable be a Python package only, or a package plus a small web control plane?
2. Should LangGraph be a hard dependency or hidden behind a runtime adapter interface?
3. Should self-learning v1 support DSPy optimization, custom reflection only, or both?
4. What is the minimum storage requirement: Postgres only, or Postgres plus Redis?
5. Should the package ship with a built-in eval store, or integrate with Opik/Promptfoo?
6. Should memory be local-first by default, or cloud-ready by default?
7. What learning artifacts can auto-promote in v1?
8. What confidence threshold blocks final answers by default?
9. What is the first commercial-grade deployment target: Docker Compose, ECS, or Kubernetes?
10. Should a visual agent designer be part of v1, or should v1 be code-first?

## 13) Recommended Updated Roadmap
### Phase 1: FactoryMind AgentOS Core Package
- SDK for agent definition
- protocol contracts
- LangGraph runtime adapter
- OpenAI model adapter
- MCP tool gateway
- local/Postgres audit log
- basic confidence scoring

### Phase 2: Reliable Learning Engine
- feedback capture
- candidate improvement schema
- reflection engine
- eval runner
- promotion/rollback registry
- learning modes per agent

### Phase 3: Industrial Runtime
- queue-backed execution
- distributed checkpoints
- RBAC hooks
- secrets integration
- OpenTelemetry traces
- AWS deployment adapter

### Phase 4: Agent Design Platform
- templates
- CLI scaffolding
- optional web UI/control plane
- agent marketplace/private registry

## 14) Dedicated Research Plan
The next step is not implementation. The next step is structured research by system block.

Research plan file:
- `docs/06-agent-os-research-plan.md`

That plan divides research into:
- runtime/session engine
- self-learning engine
- evaluation and promotion gates
- memory/context system
- tool/MCP gateway
- policy/security/governance
- observability/audit
- SDK/package/CLI
- deployment/operations
- build-vs-wrap final recommendation

The research should decide what to reuse, what to wrap, what to build, and what to avoid as a core dependency.

## 15) Sources
Primary and official sources used:
- LangGraph overview and durable execution: https://docs.langchain.com/oss/python/langgraph
- LangGraph durable execution: https://docs.langchain.com/oss/python/langgraph/durable-execution
- LangGraph human-in-the-loop: https://docs.langchain.com/oss/python/langgraph/human-in-the-loop
- LangSmith observability concepts: https://docs.langchain.com/langsmith/observability-concepts
- Microsoft Agent Framework overview: https://learn.microsoft.com/en-gb/agent-framework/overview/agent-framework-overview
- Microsoft AutoGen repository: https://github.com/microsoft/autogen
- CrewAI docs: https://docs.crewai.com/core-concepts/Agents/
- CrewAI memory docs: https://docs.crewai.com/en/concepts/memory
- Dify docs: https://docs.dify.ai/
- Flowise docs: https://docs.flowiseai.com/
- AutoGPT docs: https://docs.agpt.co/
- SuperAGI docs: https://superagi.com/docs/
- OpenAI Agents SDK: https://platform.openai.com/docs/guides/agents-sdk/
- OpenAI agent evals: https://platform.openai.com/docs/guides/agent-evals
- DSPy docs: https://dspy.ai/
- DSPy paper: https://arxiv.org/abs/2310.03714
- Opik docs: https://www.comet.com/docs/opik/
- Promptfoo docs: https://www.promptfoo.dev/docs/intro/
- Reflexion paper: https://arxiv.org/abs/2303.11366
- Self-Refine paper: https://arxiv.org/abs/2303.17651
- TextGrad paper: https://arxiv.org/abs/2406.07496
- AgentFactory paper: https://arxiv.org/abs/2603.18000
- AgentDevel paper: https://arxiv.org/abs/2601.04620
- SEAgent paper: https://arxiv.org/abs/2508.04700
- AgentEvolver paper: https://arxiv.org/abs/2511.10395

Research inference:
- Existing tools provide strong pieces, but no reviewed project cleanly provides an installable, industrial, self-learning FactoryMind AgentOS with per-agent learning modes, eval-gated promotion, auditability, and rollback as core product primitives.

