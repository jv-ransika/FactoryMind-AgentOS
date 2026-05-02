# Self-Learning Engine Research

Access date: 2026-05-01

## 1) Research Question
How should the FactoryMind AgentOS let agents improve over time in a way that is reliable, auditable, reversible, and suitable for industrial/commercial use?

This is the most important block of the FactoryMind AgentOS. The platform should not simply run agents. It should provide a controlled self-learning engine that can be enabled or disabled per agent.

## 2) Short Answer
Do not implement "agent modifies itself directly" as the core self-learning model.

Recommended model:

```text
Observed session + human feedback
  -> learning signal extraction
  -> candidate improvement proposal
  -> offline eval/replay
  -> safety and regression checks
  -> approval or auto-promotion depending on risk
  -> versioned rollout
  -> monitoring and rollback
```

Self-learning should be treated as release engineering, not autonomous mutation.

## 3) Corrected Definition: Self-Learning Means Memory + Skills
In this FactoryMind AgentOS, self-learning means changing the agent's behavior through:
- long-term memory
- learned skills
- procedural instructions
- reusable examples
- task-specific heuristics

It does **not** mean changing:
- tools
- MCP permissions
- runtime code
- safety policies
- model weights

A skill is a reusable procedural capability: a compact "how to do this well" package that the agent can retrieve and apply when a similar task appears again.

Self-learning means the system can learn new skills, improve existing skills, retire weak skills, and update long-term memory from accepted sessions and feedback.

## 4) What Self-Learning Can Change
Self-learning means the FactoryMind AgentOS can improve these artifacts over time:

| Artifact | Example | v1 Risk | v1 Recommendation |
|---|---|---:|---|
| Long-term memory | Company preference, user preference, accepted facts | Medium | Allow with provenance, TTL, confidence, revocation |
| Procedural skill | "How to write our proposal opening section" | Medium | Allow candidate generation and eval-gated promotion |
| Skill examples | Accepted proposal/project-selection examples | Medium | Allow only with privacy checks and deduplication |
| Skill activation rules | When to use a skill | Medium | Allow after eval/replay |
| Skill quality notes | Failure modes, caveats, edge cases | Low-medium | Allow after validation |
| Eval datasets | Add accepted/failure cases to regression set | Low | Allow with review or automated sanitization |
| Prompt instructions | Base system prompt adjustments | Medium | Secondary target, not the main learning object |
| Retrieval rules | Memory/skill retrieval filters and ranking | Medium | Allow inside safe bounds |
| Tool routing rules | Choose when to use MCP tools | Medium-high | Require approval; not primary self-learning target |
| Code | Runtime/tool implementation | High | Disallow autonomous production changes in v1 |
| Permissions/policies | Tool scopes and safety rules | Critical | Never auto-weaken |
| Model weights | Fine-tuning | High | Out of scope for v1 |

## 5) Learning Modes
Each agent should declare a learning mode:

| Mode | Behavior |
|---|---|
| `off` | No learning data is used for improvement |
| `collect_only` | Store traces and feedback only |
| `suggest` | Generate candidate improvements but never promote automatically |
| `auto_low_risk` | Auto-promote low-risk changes after eval pass and rollback preparation |
| `manual_high_risk` | Human approval required for medium/high-risk changes |

Default commercial rollout:
- first 2-4 weeks: `collect_only`
- after eval coverage exists: `suggest`
- only after calibration: `auto_low_risk`

## 6) Research Taxonomy
### A) Reflection-Based Learning
Examples:
- Reflexion
- Self-Refine
- Generative Agents reflection/memory pattern

Core idea:
- The agent uses feedback or self-critique to create improved future behavior.

Fit:
- Strong for generating summaries, lessons, and candidate prompt improvements.
- Weak if used directly as truth without eval gates.

FactoryMind AgentOS use:
- Use reflection to generate candidate changes, not to directly update production config.

### B) Prompt/Program Optimization
Examples:
- DSPy
- TextGrad
- ProTeGi-style textual gradients

Core idea:
- Optimize prompts/programs against a metric or dataset.

Fit:
- Strong for controlled improvement when eval datasets exist.
- Requires good metrics and regression tests.

FactoryMind AgentOS use:
- Good candidate for the learning engine once we have eval datasets.
- Start with custom reflection; add DSPy/TextGrad-style optimizers as adapters.

### C) Memory-Based Learning
Examples:
- Reflexion verbal memory
- MemGPT/Letta-style memory systems
- long-term preference/procedure memory
- MemSkill
- ProcMEM
- LEGOMem

Core idea:
- Store useful lessons, preferences, failures, and successful procedures.

Fit:
- Strong for personalization and company-specific behavior.
- High risk for contamination, stale facts, and privacy leakage.

FactoryMind AgentOS use:
- Store memories with provenance, confidence, TTL, and revocation.
- Never treat memory as policy.

### D) Skill-Library Learning
Examples:
- Voyager skill library
- AutoSkill
- Memento-Skills
- ProcMEM procedural memory
- LEGOMem modular procedural memory
- Claude/OpenAI-style skill folders as packaging inspiration

Core idea:
- Convert repeated successful behavior into reusable procedural skills.

Fit:
- Very strong match for the FactoryMind AgentOS goal.
- Safer than tool/code mutation because skills can be stored as instructions, examples, activation rules, and constraints.

FactoryMind AgentOS use:
- Make "skills" the main self-learning artifact.
- Skills should be versioned, evaluated, scoped, and reversible.

### E) Self-Evolving Agent Systems
Examples from recent research:
- AgentDevel
- AgentFactory
- SEAgent
- AgentEvolver
- broader self-evolving agent survey work

Core idea:
- Agents improve their own components, tools, subagents, or workflows.

Fit:
- Important research direction.
- Risky for v1 industrial use.

FactoryMind AgentOS use:
- Borrow the release-engineering framing.
- Do not let agents directly rewrite production code or expand permissions.

### F) Evaluation-Driven Learning
Examples:
- Opik optimization/evaluation workflows
- Promptfoo eval gates
- LangSmith evals
- OpenAI agent evals

Core idea:
- Candidate changes are judged by test sets, traces, metrics, and regressions.

Fit:
- Most production-compatible path.

FactoryMind AgentOS use:
- Make eval-gated promotion mandatory for any learned behavior change.

## 7) Skill Model
The FactoryMind AgentOS should introduce first-class skills.

V1 skill format:

```json
{
  "skill_id": "uuid",
  "agent_id": "proposal_writer",
  "name": "proposal_opening_section",
  "description": "Drafts the opening section of proposals using company tone and client context.",
  "activation": {
    "task_types": ["proposal_writing"],
    "keywords": ["proposal", "opening", "introduction"],
    "required_context": ["client_name", "project_summary"]
  },
  "procedure": [
    "Identify client goal.",
    "State the business problem in the client's language.",
    "Connect company capability to the project outcome.",
    "Avoid unsupported claims."
  ],
  "examples": [],
  "constraints": [
    "Do not invent company experience.",
    "Ask a question if client goal is missing."
  ],
  "failure_modes": [],
  "provenance": {
    "source_sessions": [],
    "created_by": "learning_engine|human",
    "created_at": "RFC3339"
  },
  "quality": {
    "confidence": 0.0,
    "acceptance_rate": 0.0,
    "eval_score": 0.0
  },
  "status": "candidate|active|deprecated|rejected",
  "version": "1.0.0"
}
```

Skill properties:
- Skills are not tools.
- Skills do not grant new permissions.
- Skills can instruct the agent how to use already allowed tools.
- Skills must be retrieved only when activation conditions match.
- Skills must be short enough to fit into model context.
- Skills must have provenance and rollback.

## 8) Skill Lifecycle
```text
accepted sessions + feedback
  -> extract repeated successful pattern
  -> create candidate skill or skill patch
  -> evaluate against replay tasks
  -> promote to active skill if gates pass
  -> monitor usage and acceptance
  -> revise, deprecate, or rollback when needed
```

Skill operations:
- `create_skill_candidate`
- `patch_skill`
- `merge_skills`
- `split_skill`
- `deprecate_skill`
- `rollback_skill`

Skill promotion gates:
- activation is specific enough
- procedure is short and actionable
- no confidential data leakage
- improves replay/eval tasks
- does not conflict with policy
- does not require new tools or permissions

## 9) Candidate Improvement Schema
Every proposed self-learning change should be a versioned candidate:

```json
{
  "candidate_id": "uuid",
  "agent_id": "project_selector",
  "candidate_type": "skill_create|skill_patch|skill_deprecate|memory_upsert|memory_patch|eval_case",
  "source_sessions": ["uuid"],
  "learning_mode": "suggest",
  "proposed_change": {},
  "evidence": {
    "accepted_outputs": 12,
    "negative_feedback_patterns": [],
    "human_feedback_summary": "string",
    "tool_success_observations": []
  },
  "risk_level": "low|medium|high|critical",
  "privacy_classification": "public|internal|confidential|regulated",
  "eval_results": {
    "baseline_score": 0.0,
    "candidate_score": 0.0,
    "regressions": []
  },
  "promotion_status": "quarantined|approved|promoted|rejected|rolled_back",
  "rollback_target_version": "string"
}
```

## 10) Promotion Pipeline
Recommended promotion flow:

1. Capture session feedback and acceptance.
2. Extract learning signals.
3. Generate candidate improvement.
4. Classify risk and privacy.
5. Run offline evals and replay tests.
6. Run safety tests and prompt-injection tests.
7. Compare candidate against current version.
8. Prepare rollback target.
9. Promote according to learning mode and risk.
10. Monitor live outcomes.
11. Roll back if quality/security/cost metrics regress.

Required invariant:
- No candidate can affect production behavior without an eval record and rollback target.

## 11) Industrial Reliability Requirements
The self-learning engine must guarantee:
- every learned change is versioned
- every learned change is traceable to source sessions
- every promotion has eval evidence
- every promotion has rollback
- every memory item has provenance
- every skill has provenance, version, status, and rollback target
- unsafe policies cannot be weakened by learning
- tool permissions cannot be expanded by learning
- confidential data cannot be added to examples without privacy checks
- old behavior can be restored quickly

## 12) Key Failure Modes
| Failure Mode | Description | Required Control |
|---|---|---|
| Feedback poisoning | Bad feedback trains the agent toward worse behavior | Anomaly detection, eval gate, human approval |
| Reward hacking | Candidate optimizes metric but worsens real usefulness | Multiple metrics, human review, live monitoring |
| Eval overfitting | Candidate improves test set only | Holdout evals, rotating test sets, adversarial cases |
| Memory contamination | Wrong/stale memories affect future outputs | Provenance, TTL, confidence, revocation |
| Skill contamination | Bad learned procedure affects future behavior | Candidate quarantine, eval gates, rollback |
| Overbroad activation | Wrong skill is loaded for unrelated tasks | Activation tests, specificity thresholds |
| Skill conflict | Multiple skills give contradictory procedures | Conflict detection and priority rules |
| Privacy leakage | Accepted output becomes few-shot example with sensitive data | Redaction, privacy classification, approval |
| Unsafe tool behavior | Learning changes when tools are called | Tool-routing changes require higher risk gate |
| Policy erosion | System learns to bypass restrictions | Learning cannot weaken policy controls |
| Long-run drift | Small improvements accumulate into degraded behavior | Periodic baseline replay and rollback |

## 13) How To Treat Systems Like OpenFlow / Similar Agent Platforms
If a platform claims "self-learning" or "self-improving agents", we should verify exactly what that means.

Research questions for any such platform:
- Does it create versioned candidate changes?
- Does it run offline evals before promotion?
- Does it keep rollback targets?
- Can learning be disabled per agent?
- Can we inspect why the agent changed?
- Does it separate memory learning from prompt/config learning?
- Does it prevent policy or permission weakening?
- Does it support self-hosted industrial deployment?

If the answer is unclear, treat it as inspiration only, not a core dependency.

## 14) Finalized V1 Design
V1 should include automated self-learning, focused on long-term memory and learned skills.

Final v1 decision:
- automated learning is possible
- automated learning should be enabled per agent
- automated learning must produce versioned memory/skill candidates
- automated evaluation must run before promotion
- low-risk changes can auto-promote after passing gates
- medium/high-risk changes require human approval
- rollback must be prepared before any promotion

The v1 system should support three operational modes:

| Mode | What Happens | Recommended Use |
|---|---|---|
| `collect_only` | Store traces, feedback, accepted outputs, failures | New agent rollout |
| `suggest` | Generate and evaluate candidates, but require approval | Early production |
| `auto_low_risk` | Auto-promote low-risk memory/skill candidates after strict gates | Mature agents with eval coverage |

Recommended default:
- new agents start as `collect_only`
- move to `suggest` after enough traces exist
- move to `auto_low_risk` only after the agent has stable eval coverage and rollback has been tested

## 15) What Can Be Automated In V1
| Artifact | Automated Candidate Generation | Automated Promotion | Notes |
|---|---:|---:|---|
| Long-term memory | Yes | Yes, if low risk and provenance is clear | Main v1 learning target |
| Skill creation | Yes | Yes, only for low-risk procedural skills | Main v1 learning target |
| Skill patching | Yes | Yes, if eval/replay improves | Version and rollback required |
| Skill deprecation | Yes | Maybe | Auto-deprecate only after repeated failure evidence |
| Skill examples | Yes | Yes, if sanitized and deduplicated | Must pass privacy checks |
| Eval case creation | Yes | Yes, after sanitization | Add accepted/failure cases to regression sets |
| Memory retrieval ranking | Yes | Yes, if scoped and eval passes | No permission expansion |
| Tool routing rules | Yes | No in v1 | Require approval |
| Tool permissions | No | No | Never auto-expand |
| Safety policy | No | No | Never auto-weaken |
| Runtime code | No | No | Out of scope |
| Fine-tuning | No | No | Out of scope |

## 16) Finalized V1 Self-Learning Architecture
```text
Session completed with accept
  -> LearningSignalExtractor
  -> MemorySkillMiner
  -> SkillCandidateGenerator
  -> MemoryCandidateGenerator
  -> CandidateStore
  -> EvalRunner
  -> SafetyGate
  -> PromotionGate
  -> RollbackRegistry
  -> AgentConfigRegistry
```

Core modules:
- `LearningSignalExtractor`: extracts feedback, accepted output, rejected output, tool failures, and unresolved issues.
- `MemorySkillMiner`: detects repeated patterns worth storing as memory or procedural skill.
- `SkillCandidateGenerator`: creates new skills or skill patches from repeated successful traces.
- `MemoryCandidateGenerator`: creates long-term memory updates with provenance, confidence, and TTL.
- `CandidateStore`: stores versioned proposed changes.
- `EvalRunner`: tests candidates against baseline and regression cases.
- `SafetyGate`: checks privacy, prompt injection, policy regression, and permission changes.
- `PromotionGate`: enforces score thresholds, learning mode, approval, and rollback readiness.
- `RollbackRegistry`: stores previous active versions and rollback metadata.
- `AgentConfigRegistry`: stores active and historical agent versions.

## 17) Automated Learning Loop
V1 should run the learning loop as a background job.

Trigger options:
- after each accepted session, enqueue a learning signal
- nightly batch optimization per agent
- manual `agent-os learn <agent>` command

Recommended v1 behavior:
- run learning extraction continuously
- run optimization in scheduled batches
- promote low-risk changes only after gates pass

Automated loop:

```text
1. Collect accepted/rejected sessions.
2. Sanitize data and remove sensitive fields.
3. Build or update agent eval dataset.
4. Generate memory and skill candidates.
5. Replay baseline and candidate on same eval set.
6. Compare score, confidence calibration, latency, cost, and safety.
7. Promote if all gates pass and learning mode allows it.
8. Monitor live sessions.
9. Roll back automatically if regression threshold is hit.
```

## 18) Recommended Skill-Learning Strategy
Use a staged optimizer strategy instead of depending on one algorithm.

### Stage 1: Trace-to-Skill Miner
Build this ourselves first.

Purpose:
- analyze accepted/rejected sessions
- extract failure patterns
- extract repeated successful procedures
- propose memory updates and skill candidates
- produce human-readable rationale

Why:
- easiest to control
- auditable
- works before large datasets exist

### Stage 2: Skill Patch Optimizer
Add an optimizer that improves existing skills using eval feedback.

Why:
- skill procedures can be treated as optimizable text artifacts
- GEPA/DSPy-style reflective optimization can patch skill wording and examples
- the FactoryMind AgentOS still owns promotion and rollback

Use for:
- skill procedure text
- activation rules
- skill examples
- memory consolidation prompts

Do not use for:
- policies
- permissions
- production code

### Stage 3: Skill Library Quality Manager
Add automated skill maintenance.

Purpose:
- merge duplicate skills
- split overbroad skills
- deprecate low-performing skills
- detect conflicting skills
- tune retrieval/activation metadata

### Stage 4: Opik/Phoenix/MLflow-Style Optimization Adapter
Use this for experiment tracking, prompt versioning, and evaluation-driven prompt optimization.

Why:
- Opik supports agent optimization workflows and trace-level evidence.
- Phoenix supports prompt versioning, experiments, replay, and automated prompt learning.
- MLflow now exposes GEPA-style prompt optimization APIs.

V1 choice:
- build FactoryMind AgentOS interfaces so any of these can be plugged in
- do not hard-lock to one external platform until the evaluation block is researched

## 19) Promotion Gates For Automated V1
Low-risk auto-promotion is allowed only when all gates pass:

| Gate | Requirement |
|---|---|
| Minimum dataset | At least configured number of eval examples |
| Quality improvement | Candidate beats baseline by threshold |
| Regression limit | No critical regression cases fail |
| Safety | No policy, prompt-injection, or data-leakage regression |
| Confidence | Confidence calibration does not degrade |
| Cost | Cost increase stays within budget |
| Latency | Latency increase stays within budget |
| Scope | Candidate changes only approved artifact types |
| Skill activation | Candidate skill activates only on intended task family |
| Skill conflict | Candidate does not conflict with active higher-priority skills |
| Rollback | Previous version is available and tested |

Suggested v1 defaults:
- minimum eval examples: `30` for suggest mode, `100` for auto-low-risk mode
- quality improvement threshold: `+3%` absolute or configured metric
- critical regression tolerance: `0`
- auto rollback trigger: live score drops below baseline for two consecutive windows

These numbers are defaults and must be configurable.

## 20) Is Automated Memory/Skill Learning Possible?
Yes, but only if it is scoped correctly.

Possible in v1:
- automated long-term memory extraction
- automated skill creation from repeated successful traces
- automated skill patching from feedback
- automated skill example selection
- automated eval dataset expansion
- automated skill retrieval/activation improvement inside safe bounds

Not reliable enough for v1:
- automatic code generation into production
- automatic tool permission expansion
- automatic policy weakening
- automatic model fine-tuning on company data
- black-box self-learning without eval evidence

The reliable long-run design is:
- automated proposal
- automated testing
- automated low-risk promotion
- automatic rollback
- human approval for higher-risk changes

## 21) Can We Get Skills Here?
Yes. We can build skills into the FactoryMind AgentOS as a first-class self-learning layer.

The strongest direction is:

```text
Long-term memory = what the agent knows
Skills = how the agent should act
Tools = what the agent is allowed to call
Policies = what the agent must never violate
```

In v1, self-learning should update:
- memory
- skills
- skill examples
- skill activation metadata

In v1, self-learning should not update:
- tools
- permissions
- policies
- runtime code

Existing skill systems like Claude Skills, OpenAI/Codex skills, Warp skills, and Refly skills show that skills can be packaged as reusable instruction bundles. Research systems like Voyager, ProcMEM, AutoSkill, Memento-Skills, MemSkill, and LEGOMem show that skills/procedural memory can be learned from experience.

FactoryMind AgentOS should combine these two ideas:
- package skills like modern agent skill systems
- learn/patch skills like procedural memory research
- govern them with evals, provenance, and rollback

## 22) Why Existing "Self-Learning Agent Platforms" Are Not Enough
Platforms that advertise self-learning should be treated carefully unless they expose:
- exact learned artifact
- version history
- eval evidence
- approval policy
- rollback
- privacy controls
- per-agent learning mode
- failure/regression reports

If a platform only stores memory or adapts prompts invisibly, it is not reliable enough for industrial FactoryMind AgentOS use.

The FactoryMind AgentOS should therefore own the learning ledger and promotion process even if it uses external optimizers.

## 23) Existing Components To Consider
| Component | Possible Role | Recommendation |
|---|---|---|
| Claude/OpenAI-style skills | Skill package format inspiration | Strong format reference |
| Refly skills | Open-source skill builder reference | Research as skill authoring UX |
| Voyager | Lifelong skill-library learning inspiration | Strong conceptual reference, not direct dependency |
| ProcMEM | Reusable procedural memory from experience | Strong research reference |
| AutoSkill | Skill self-evolution from interaction traces | Strong research reference |
| Memento-Skills | Self-evolving skill repository | Research deeply before adoption |
| MemSkill | Learnable memory operation skills | Strong memory-skill reference |
| LEGOMem | Modular procedural memory for workflows | Strong multi-agent reference |
| DSPy MIPROv2 | Instruction and few-shot optimization | Strong v1/v2 optimizer adapter once eval data exists |
| DSPy GEPA | Trace/text-feedback reflective prompt evolution | Strong v1/v2 optimizer adapter for automated prompt evolution |
| TextGrad | Textual gradient prompt optimization | Research/phase-2 candidate |
| Phoenix Prompt Learning | Automated prompt optimization from eval feedback | Strong platform reference/adapter candidate |
| MLflow prompt optimization | GEPA-backed prompt optimization API | Strong experiment/versioning reference |
| Opik | Evals, traces, optimization workflows | Strong eval/observability candidate |
| Promptfoo | Lightweight eval/red-team gates | Strong CI/eval candidate |
| LangSmith evals | Eval and trace support if using LangGraph stack | Useful but avoid hard lock-in initially |
| OpenAI agent evals | Provider-native evals | Useful for OpenAI-specific testing |
| Reflexion/Self-Refine | Reflection algorithms | Use as design patterns |
| AgentDevel | Self-improvement as release engineering | Strong conceptual inspiration |

## 24) Finalized V1 Recommendation
The FactoryMind AgentOS v1 should include automated self-learning as memory and skill learning.

Final architecture:

```text
AgentRuntime
  -> TraceCollector
  -> FeedbackCollector
  -> LearningSignalExtractor
  -> MemorySkillMiner
  -> SkillCandidateGenerator
  -> MemoryCandidateGenerator
  -> SkillLibrary
  -> MemoryStore
  -> CandidateStore
  -> EvalRunner
  -> SafetyGate
  -> PromotionGate
  -> AgentConfigRegistry
  -> RollbackRegistry
```

Final v1 behavior:
- `collect_only`: fully automated collection
- `suggest`: automated memory/skill candidate generation and eval, manual promotion
- `auto_low_risk`: automated memory/skill candidate generation, eval, promotion, monitoring, and rollback

The first implementation should build the control layer ourselves and integrate optimizers through adapters.

## 25) Open Questions For Deeper Research
1. Should v1 skills be stored only as JSON/Markdown instructions, or also support optional scripts later?
2. Should evals be implemented with Promptfoo, Opik, LangSmith, or a custom pytest runner first?
3. What minimum eval dataset size is required before allowing `auto_low_risk`?
4. What skill types can be auto-promoted later without human approval?
5. How should we score feedback quality and detect noisy/adversarial feedback?
6. How should privacy classification work before accepted outputs become examples?
7. Should skills be per-agent only, or can agents share approved company-level skills?
8. How often should baseline replay run to detect long-run drift?
9. Should FactoryMind AgentOS support fine-tuning later, or intentionally stay config/prompt/memory based?
10. How should self-learning be explained to end users and operators?

## 26) Current Recommendation
The FactoryMind AgentOS should build its own skill and memory learning layer and use existing systems as references or optimizer/eval components.

Recommended direction:

```text
Own:
  - learning modes
  - skill schema
  - memory schema
  - candidate schema for skill/memory changes
  - promotion policy
  - rollback registry
  - memory provenance
  - skill provenance
  - safety gates

Wrap or integrate:
  - DSPy/TextGrad-style optimizers
  - Opik/Promptfoo/LangSmith evals
  - LangGraph traces/checkpoints

Do not rely on:
  - black-box "self-learning" claims
  - direct autonomous code mutation
  - memory-only learning without eval gates
```

## 27) Sources
Primary and research sources:
- Voyager paper: https://arxiv.org/abs/2305.16291
- Claude Skills docs: https://claude.com/docs/skills/overview
- OpenAI Skills resource: https://academy.openai.com/public/resources/skills
- OpenAI skills repository: https://github.com/openai/skills
- Refly docs: https://docs.refly.ai/
- Warp Skills docs: https://docs.warp.dev/agent-platform/capabilities/skills
- ProcMEM paper: https://arxiv.org/abs/2602.01869
- MemSkill paper: https://arxiv.org/abs/2602.02474
- AutoSkill paper: https://arxiv.org/abs/2603.01145
- LEGOMem paper: https://arxiv.org/abs/2510.04851
- SoK Agentic Skills paper: https://arxiv.org/abs/2602.20867
- SkillFlow benchmark: https://arxiv.org/abs/2604.17308
- Reflexion paper: https://arxiv.org/abs/2303.11366
- Self-Refine paper: https://arxiv.org/abs/2303.17651
- Generative Agents paper: https://arxiv.org/abs/2304.03442
- DSPy documentation: https://dspy.ai/
- DSPy paper: https://arxiv.org/abs/2310.03714
- DSPy MIPROv2 documentation: https://github.com/stanfordnlp/dspy/blob/main/docs/docs/api/optimizers/MIPROv2.md
- DSPy GEPA documentation: https://github.com/stanfordnlp/dspy/blob/main/docs/docs/api/optimizers/GEPA/overview.md
- TextGrad paper: https://arxiv.org/abs/2406.07496
- ProTeGi paper: https://arxiv.org/abs/2306.03495
- Opik documentation: https://www.comet.com/docs/opik/
- Opik Agent Optimizer: https://www.comet.com/docs/opik/development/optimization-runs/overview
- Promptfoo documentation: https://www.promptfoo.dev/docs/intro/
- LangSmith evaluation docs: https://docs.langchain.com/langsmith/evaluation
- OpenAI agent evals: https://platform.openai.com/docs/guides/agent-evals
- Phoenix prompt optimization: https://arize.com/docs/phoenix/prompt-engineering/tutorial/optimize-prompts-automatically
- Phoenix overview: https://arize.com/docs/phoenix
- MLflow prompt optimization: https://mlflow.org/prompt-optimization
- MLflow GenAI prompt optimization API: https://mlflow.org/docs/latest/api_reference/python_api/mlflow.genai.html
- Agentic Self-Learning paper: https://openreview.net/forum?id=GE1HgWQjIH
- Self-Evolving Agents survey: https://arxiv.org/abs/2508.07407
- AgentFactory paper: https://arxiv.org/abs/2603.18000
- AgentDevel paper: https://arxiv.org/abs/2601.04620
- SEAgent paper: https://arxiv.org/abs/2508.04700
- AgentEvolver paper: https://arxiv.org/abs/2511.10395
- Automated Self-Testing as a Quality Gate: https://arxiv.org/abs/2603.15676
- GEPA paper: https://arxiv.org/abs/2507.19457
- Reflection in the Dark critique: https://arxiv.org/abs/2603.18388
- DSPy declarative learning study: https://arxiv.org/abs/2604.04869

Research inference:
- Automated self-learning is feasible for prompt/example/retrieval artifacts when backed by evals, safety gates, versioning, and rollback.
- Current research is promising but still needs an industrial control layer around it.

