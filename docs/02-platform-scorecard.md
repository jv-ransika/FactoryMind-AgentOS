# Top-8 Platform Scorecard (Open-Source Priority)

## 1) Scope and Method
This scorecard evaluates seven open-source platforms/frameworks plus one managed comparator bucket for gap analysis:
- LangGraph
- CrewAI
- Semantic Kernel
- OpenHands
- LlamaIndex
- Haystack
- PydanticAI
- Managed comparator bucket (Azure Foundry Agent Service, AWS Bedrock Agents, Vertex AI Agent Builder, OpenAI Agents toolkit)

Scoring model:
- Scale: `1` (weak) to `5` (strong).
- Weighted score formula: `sum((score/5) * weight)` => total out of `100`.
- Open-source-first policy is enforced by a high weight for self-host maturity.

## 2) Weighted Criteria
| Criterion | Weight | What It Measures |
|---|---:|---|
| Orchestration depth (`OD`) | 14 | Stateful control flow, multi-agent coordination, long-running workflows |
| Memory extensibility (`ME`) | 12 | Short/long-term memory patterns, pluggability, governance options |
| Tool/API integration (`TI`) | 12 | Native tool model, extensibility, integration breadth |
| Observability/evals (`OE`) | 11 | Tracing, evaluation, regression visibility |
| Security/governance (`SG`) | 15 | Access control, policy support, auditability posture |
| Self-host maturity (`SH`) | 14 | Practical self-host deployment and ops maturity |
| Ecosystem health (`EH`) | 9 | Community, docs, active maintenance signals |
| Operational complexity (`OC`) | 7 | Ease of operating at scale (higher is easier) |
| Total cost of ownership (`TCO`) | 6 | Infrastructure + engineering overhead efficiency |

Total weight: `100`.

## 3) Scoring Matrix
| Platform | OD | ME | TI | OE | SG | SH | EH | OC | TCO | Weighted Score |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LangGraph | 5 | 4 | 4 | 5 | 4 | 5 | 5 | 3 | 4 | **88.2** |
| Semantic Kernel | 4 | 4 | 5 | 4 | 5 | 5 | 4 | 3 | 4 | **86.8** |
| PydanticAI | 4 | 4 | 4 | 4 | 4 | 5 | 4 | 4 | 5 | **84.0** |
| Haystack | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | **80.0** |
| CrewAI | 4 | 3 | 5 | 4 | 4 | 4 | 5 | 3 | 3 | **79.2** |
| LlamaIndex | 4 | 4 | 4 | 4 | 3 | 4 | 5 | 4 | 4 | **78.8** |
| Managed comparator bucket | 4 | 4 | 5 | 5 | 5 | 1 | 5 | 4 | 2 | **78.6** |
| OpenHands | 3 | 3 | 3 | 4 | 3 | 3 | 5 | 3 | 3 | **65.8** |

## 4) Recommendation Short List
### Primary
- `LangGraph`:
  - Strongest fit for long-running, stateful agent orchestration and explicit human-in-the-loop control.
  - Best default for high-control, reliability-first workflows.
- `Semantic Kernel`:
  - Strong model-agnostic and enterprise-oriented capabilities with multi-agent and plugin abstractions.
  - Strong option when cross-runtime interoperability and enterprise governance are priority.

### Secondary
- `PydanticAI`:
  - Strong Python ergonomics, explicit multi-agent progression model, good for fast but controlled iteration.
- `Haystack`:
  - Balanced modularity and tooling for teams focused on retrieval-heavy assistant workloads.

### Avoid for Now (for this specific platform goal)
- `OpenHands`:
  - Excellent for AI-driven software development workflows, but less aligned as a neutral general-purpose agent platform core.
  - Keep as a specialized coding-agent subsystem candidate, not the platform backbone.

## 5) Managed Comparator Gap Analysis
Managed options are strong in hosted runtime operations and governance tooling, but create strategic tradeoffs:
- Strengths: quick production path, integrated observability, managed identity/networking, reduced ops burden.
- Tradeoffs: weaker self-host control, potential lock-in, higher long-term platform dependency risk.
- Decision: use as benchmark and optional hybrid extension, not as primary architecture anchor.

## 6) Reproducibility Notes
- Use fixed weights in Section 2.
- Keep `1-5` scoring scale unchanged.
- Re-run scorecard quarterly or when major releases materially change capability.
- Record change log with timestamp and score deltas.

## 7) Actionable Next Decisions
| Decision | Recommended Default | Owner | Effort | Prerequisites |
|---|---|---|---|---|
| Core orchestration framework | LangGraph (primary) + Semantic Kernel (parallel prototype) | Platform Architect | M | Python baseline, evaluation harness |
| Memory stack | Start with pluggable vector + metadata store behind memory abstraction | Platform + Data Eng | M | Data classification policy |
| Tool gateway pattern | Central signed tool registry with per-tool policy | Platform + Security | M | Policy engine |
| Managed integration strategy | Hybrid optional, not default | Architecture Board | L | Cost/risk model |

## 8) Sources (Primary) and Access Date
Accessed: `2026-04-30`.

1. LangGraph repository: [https://github.com/langchain-ai/langgraph](https://github.com/langchain-ai/langgraph)
2. CrewAI repository: [https://github.com/crewAIInc/crewAI](https://github.com/crewAIInc/crewAI)
3. CrewAI automations docs: [https://docs.crewai.com/en/enterprise/features/automations](https://docs.crewai.com/en/enterprise/features/automations)
4. Semantic Kernel repository: [https://github.com/microsoft/semantic-kernel](https://github.com/microsoft/semantic-kernel)
5. OpenHands repository: [https://github.com/OpenHands/OpenHands](https://github.com/OpenHands/OpenHands)
6. LlamaIndex workflow docs: [https://docs.llamaindex.ai/en/stable/module_guides/workflow/](https://docs.llamaindex.ai/en/stable/module_guides/workflow/)
7. Haystack agents docs: [https://docs.haystack.deepset.ai/docs/agents](https://docs.haystack.deepset.ai/docs/agents)
8. Pydantic AI multi-agent docs: [https://ai.pydantic.dev/multi-agent-applications/](https://ai.pydantic.dev/multi-agent-applications/)
9. Azure Foundry Agent Service overview: [https://learn.microsoft.com/azure/ai-foundry/agents/overview](https://learn.microsoft.com/azure/ai-foundry/agents/overview)
10. AWS Bedrock agents docs: [https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html](https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html)
11. Vertex AI Agent Builder docs: [https://cloud.google.com/agent-builder](https://cloud.google.com/agent-builder)
12. OpenAI Agents guide: [https://platform.openai.com/docs/guides/agents](https://platform.openai.com/docs/guides/agents)

Inference notes:
- Scores are structured inferences from official documentation, repository metadata, and explicit feature statements; they are not vendor-provided benchmark numbers.

## 9) Program-Specific Selection Decision (v2 Update)
Final recommendation for this program:
- Primary orchestration/runtime: `LangGraph`.
- Optional secondary framework: `Semantic Kernel` for selective plugin/memory integration patterns.
- Do not run dual orchestrators in v1.

Reasoning for this decision:
- You are a single Python engineer with an immediate timeline.
- The architecture requires explicit session state loops (`init`, `feedback`, `accept`) and durable checkpoints.
- The platform requires strong human-in-the-loop, approval gating, and reusable agent templates.

Decision for current scope:
- Build with LangGraph-first architecture now.
- Re-evaluate Semantic Kernel as a subsystem integration option after v1 stability and eval coverage are in place.
