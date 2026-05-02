# Evaluation and Promotion Gates Research

Access date: 2026-05-01

## 1) Research Question
How should FactoryMind AgentOS decide whether a learned memory or skill candidate is good enough to activate automatically?

This block defines the evaluation and promotion system for self-learning. It is the safety mechanism that makes automated memory/skill learning possible in v1.

## 2) Short Answer
FactoryMind AgentOS should own the promotion system and support multiple evaluation engines through adapters.

Recommended v1:

```text
CandidateStore
  -> EvalDatasetBuilder
  -> EvalRunner
       -> BuiltInEvalRunner first
       -> PromptfooAdapter for CI/red-team
       -> Opik/Phoenix/LangSmith adapter later
  -> SafetyGate
  -> PromotionGate
  -> RollbackRegistry
```

Do not let an external eval platform directly promote learned behavior. External systems can score, trace, optimize, and report. FactoryMind AgentOS must make the final promotion decision.

## 3) What Must Be Evaluated
For memory and skill self-learning, evaluate at four levels:

| Level | What Is Tested | Example |
|---|---|---|
| Candidate validity | Is the candidate well-formed and safe? | Skill has activation rules, no secrets, no policy conflict |
| Task quality | Does the candidate improve outputs? | Better proposal section or project ranking |
| Behavior safety | Does it avoid unsafe behavior? | No data leakage, no unsupported claims |
| Operational impact | Does it stay within cost/latency limits? | No excessive tool calls or token growth |

For skills specifically:
- Does the skill activate only when appropriate?
- Does it improve similar tasks?
- Does it harm unrelated tasks?
- Does it conflict with other active skills?
- Can it be rolled back without breaking sessions?

## 4) Evaluation Dataset Types
FactoryMind AgentOS should maintain multiple eval sets per agent.

| Dataset | Purpose | Source |
|---|---|---|
| Golden set | Known high-quality examples | Human-authored or approved sessions |
| Regression set | Past failures and edge cases | Rejected outputs, incidents, low-confidence sessions |
| Safety set | Prompt injection, privacy, policy tests | Red-team generator and manual tests |
| Activation set | Tests when a skill should/should not load | Skill usage history and synthetic cases |
| Holdout set | Prevents overfitting | Reserved accepted/rejected sessions |
| Live shadow set | Compare active vs candidate on real traffic without user impact | Production traces |

V1 minimum:
- golden set
- regression set
- safety set
- activation set for skills

## 5) Promotion Gate Model
Promotion should be a deterministic gate, not an LLM-only judgment.

```text
candidate
  -> schema validation
  -> privacy/redaction validation
  -> offline eval
  -> regression eval
  -> safety eval
  -> activation eval
  -> cost/latency check
  -> confidence calibration check
  -> rollback readiness check
  -> promote or reject
```

Every gate produces an auditable record.

## 6) Candidate Promotion States
```text
created
  -> validating
  -> evaluating
  -> awaiting_approval
  -> promoted
  -> rejected
  -> rolled_back
```

State rules:
- `created`: candidate exists but has not been tested.
- `validating`: schema/privacy/policy validation is running.
- `evaluating`: quality/safety/regression tests are running.
- `awaiting_approval`: passed tests but needs human approval.
- `promoted`: active for target agent/version.
- `rejected`: failed or manually rejected.
- `rolled_back`: was active and then reverted.

## 7) Recommended V1 Thresholds
These are defaults and should be configurable.

| Gate | Default |
|---|---|
| Minimum golden examples for `suggest` | 30 |
| Minimum golden examples for `auto_low_risk` | 100 |
| Critical regression failures | 0 allowed |
| Safety test failures | 0 allowed |
| Skill activation false-positive rate | <= 3% |
| Skill activation false-negative rate | <= 10% |
| Quality improvement | >= 3% over baseline or statistically meaningful win |
| Cost increase | <= 10% |
| Latency increase | <= 10% |
| Confidence calibration | No degradation vs baseline |
| Rollback target | Required before promotion |

For early v1, if the dataset is small, allow automation only in `suggest` mode. Move to `auto_low_risk` after enough evaluation history exists.

## 8) Automated Promotion Policy
Automated promotion is allowed only for low-risk memory/skill candidates.

Auto-promotable:
- memory additions with clear provenance and low privacy risk
- skill examples after redaction and deduplication
- skill procedure improvements that pass activation and regression tests
- skill activation metadata refinements inside safe bounds

Never auto-promote:
- tool permission changes
- safety policy changes
- runtime code changes
- model fine-tuning
- changes involving regulated/sensitive data without approval
- high-impact skills that affect external actions or business decisions

## 9) Evaluation Engines Researched
### Built-In Eval Runner
Role:
- lightweight local evaluator owned by FactoryMind AgentOS.

Strengths:
- no external dependency
- easiest to integrate with candidate schema
- good for deterministic checks, JSON schema checks, activation tests, and simple scoring

Limitations:
- needs us to build dashboards/reporting
- weaker for advanced trace analysis unless extended

Recommendation:
- implement first.

### Promptfoo
Role:
- local-first CLI/library for prompt, agent, RAG, and red-team evals.

Strengths:
- open source and CI-friendly
- assertion-based tests
- red-team and vulnerability testing
- can test HTTP APIs and agent workflows

Limitations:
- Node-centric tooling may add stack complexity
- FactoryMind AgentOS must translate candidate/session data into Promptfoo configs

Recommendation:
- strong v1 adapter for CI and red-team gates.

### Opik
Role:
- open-source LLM evaluation, tracing, and optimization platform.

Strengths:
- traces, experiments, prompt/agent optimization workflows
- good fit for learning candidate evidence
- can serve as observability/eval backend

Limitations:
- requires deployment/operation decision
- FactoryMind AgentOS still needs its own promotion ledger

Recommendation:
- strong candidate for v1/v2 eval and observability backend.

### Phoenix / Arize
Role:
- open-source tracing, datasets, experiments, and evaluation.

Strengths:
- OpenTelemetry-friendly
- evaluates traces, datasets, and experiments
- built-in explanations and model-agnostic adapters
- strong for debugging why a candidate passed/failed

Limitations:
- production monitoring may push toward Arize managed products
- FactoryMind AgentOS must still own learning/promotion decisions

Recommendation:
- strong research candidate, especially for observability + evals.

### LangSmith
Role:
- LangGraph/LangChain-native tracing, datasets, experiments, and evals.

Strengths:
- natural fit if LangGraph is v1 runtime
- supports trace/dataset workflows and experiment analysis
- useful for debugging runtime behavior

Limitations:
- stronger ecosystem lock-in
- not ideal as the only FactoryMind AgentOS evidence store

Recommendation:
- useful optional adapter, not required core.

### OpenAI Evals / Agent Evals
Role:
- OpenAI-native evaluation tooling for model and agent quality.

Strengths:
- aligned with OpenAI provider
- supports reproducible agent evals and trace grading
- useful while v1 is OpenAI-only

Limitations:
- provider lock-in
- not sufficient as self-hosted FactoryMind AgentOS promotion system

Recommendation:
- use for OpenAI-specific evals, not core promotion ledger.

### Ragas
Role:
- RAG/retrieval metrics.

Strengths:
- useful for memory and retrieval quality checks
- supports metrics for RAG and agentic workflows

Limitations:
- some metrics can be opaque or noisy
- should not be the only gate

Recommendation:
- use as a diagnostic component for memory/retrieval evaluation.

### DeepEval
Role:
- local-first Python evaluation framework with pytest-style assertions.

Strengths:
- Python-friendly
- agent, tool-use, safety, RAG, and conversational metrics
- useful for CI-friendly testing

Limitations:
- shared dashboards/monitoring may require external service
- still needs integration with FactoryMind AgentOS candidate ledger

Recommendation:
- strong alternative to Promptfoo if we want Python-only v1.

## 10) Recommended V1 Architecture
Use an FactoryMind AgentOS-owned eval/promotion layer with pluggable eval engines.

```text
CandidateStore
  -> EvaluationPlanBuilder
  -> BuiltInEvalRunner
       -> deterministic checks
       -> skill activation checks
       -> schema/privacy checks
  -> OptionalExternalEvalAdapters
       -> PromptfooAdapter
       -> DeepEvalAdapter
       -> OpikAdapter
       -> PhoenixAdapter
       -> LangSmithAdapter
  -> GateAggregator
  -> PromotionGate
  -> RollbackRegistry
```

V1 should start with:
- built-in deterministic evaluator
- Python test runner or DeepEval-style interface
- Promptfoo adapter for red-team later if Node tooling is acceptable

## 11) Eval Record Schema
Every evaluation run should produce a record:

```json
{
  "eval_run_id": "uuid",
  "candidate_id": "uuid",
  "agent_id": "project_selector",
  "agent_version": "1.2.0",
  "candidate_version": "1.3.0-candidate.1",
  "dataset_ids": ["golden", "regression", "safety", "activation"],
  "metrics": {
    "quality_score": 0.0,
    "safety_pass_rate": 1.0,
    "regression_failures": 0,
    "activation_false_positive_rate": 0.0,
    "activation_false_negative_rate": 0.0,
    "confidence_calibration_delta": 0.0,
    "latency_delta": 0.0,
    "cost_delta": 0.0
  },
  "gate_results": [
    {
      "gate": "safety",
      "status": "pass",
      "reason": "string"
    }
  ],
  "decision": "promote|reject|requires_approval",
  "created_at": "RFC3339"
}
```

## 12) Skill Evaluation
Skill candidates need special evals.

Evaluate:
- activation precision: does the skill load only when it should?
- activation recall: does the skill load when needed?
- task improvement: does output improve when skill is used?
- conflict: does it contradict higher-priority skills?
- safety: does it introduce unsupported claims or policy violations?
- context cost: does it consume too many tokens?

Skill promotion rule:
- a skill must improve target tasks without harming unrelated tasks.

## 13) Memory Evaluation
Memory candidates need different evals.

Evaluate:
- provenance exists
- privacy class is acceptable
- memory is not duplicate
- memory is not stale or contradicted
- memory improves similar future tasks
- memory does not override explicit user input

Memory rule:
- latest explicit user feedback beats long-term memory.

## 14) Rollback Design
Every promotion must create a rollback target.

Rollback triggers:
- live acceptance rate drops below baseline
- low-confidence outputs increase
- safety/policy incidents occur
- activation false positives spike
- cost/latency exceeds threshold
- operator manually rolls back

Rollback action:
- mark candidate as `rolled_back`
- restore previous active skill/memory version
- preserve audit record
- add rollback case to regression set

## 15) Evaluation Risks
| Risk | Control |
|---|---|
| LLM judge variance | Use deterministic checks where possible, repeat judge runs, require explanations |
| Eval overfitting | Holdout sets, rotating regression sets, live shadow tests |
| Bad metrics | Multiple metrics and human review for high-impact cases |
| Dataset contamination | Split train/eval/holdout and track source sessions |
| Safety blind spots | Red-team suite and prompt injection tests |
| Eval platform lock-in | Adapter interface and FactoryMind AgentOS-owned eval records |

## 16) Build-vs-Wrap Decision
Build:
- candidate states
- promotion gates
- rollback registry
- eval record schema
- deterministic skill/memory validators
- gate aggregation logic

Wrap:
- Promptfoo for red-team and CI checks
- DeepEval for Python-native metrics
- Opik/Phoenix/LangSmith for tracing/experiments
- Ragas for memory/retrieval diagnostics
- OpenAI evals for OpenAI-specific agent tests

Do not outsource:
- final promotion decision
- candidate versioning
- rollback decision
- learning mode enforcement

## 17) Final Recommendation
For FactoryMind AgentOS v1, implement an internal evaluation and promotion layer first, then connect external eval engines through adapters.

Recommended v1 stack:

```text
BuiltInEvalRunner
  + pytest-style deterministic tests
  + DeepEval or Promptfoo adapter
  + FactoryMind AgentOS PromotionGate
  + RollbackRegistry
```

If we want Python-only v1:
- prefer `DeepEval` style integration first.

If we want strongest red-team/CI support:
- add `Promptfoo` adapter early.

If we want observability + eval dashboard:
- research `Opik` and `Phoenix` in the observability block before choosing.

## 18) Sources
- OpenAI Agent Evals: https://platform.openai.com/docs/guides/agent-evals
- OpenAI Evals API: https://platform.openai.com/docs/api-reference/evals
- Promptfoo FAQ: https://www.promptfoo.dev/docs/faq/
- Promptfoo red team quickstart: https://www.promptfoo.dev/docs/red-team/quickstart/
- Promptfoo assertions and metrics: https://www.promptfoo.dev/docs/configuration/expected-outputs/
- Promptfoo GitHub: https://github.com/promptfoo/promptfoo
- Opik Agent Optimizer: https://www.comet.com/docs/opik/development/optimization-runs/overview
- Phoenix evaluation docs: https://arize.com/docs/phoenix/evaluation/llm-evals
- Phoenix overview: https://arize.com/docs/phoenix
- MLflow GenAI overview: https://mlflow.org/docs/latest/genai/
- MLflow prompt evaluation: https://mlflow.org/docs/latest/genai/eval-monitor/running-evaluation/prompts/
- DeepEval docs: https://deepeval.com/docs/introduction
- Ragas metrics: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/
- RAGAS paper: https://arxiv.org/abs/2309.15217
- Eval Factsheets paper: https://arxiv.org/abs/2512.04062
- RAGVUE paper: https://arxiv.org/abs/2601.04196

Research inference:
- External eval tools are valuable, but FactoryMind AgentOS must own the promotion gate because promotion is a product safety decision, not just a score.

