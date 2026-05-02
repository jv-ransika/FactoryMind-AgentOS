# Reliability + Security Controls Guide

## 1) Objective
Define the minimum control set required to operate a self-improving agent platform safely in enterprise environments, aligned with:
- OWASP Top 10 for LLM applications (latest project release stream)
- NIST AI RMF + Generative AI Profile
- SOC 2 trust services focus areas
- GDPR obligations

## 2) Threat Model (Agent-Specific)
| Threat Scenario | Preventive Controls | Detective Controls | Owner | Effort | Prerequisites |
|---|---|---|---|---|---|
| Prompt injection drives unsafe tool actions | Tool allowlists, strict tool schemas, context isolation, high-risk action approval | Prompt-attack detectors, anomalous tool-sequence alerts | Security Eng + Runtime Eng | M | Tool registry + policy engine |
| Tool abuse / privilege escalation | Per-tool RBAC scopes, short-lived credentials, network egress policies | Privilege escalation alerts, unusual permission graph detection | Security Eng | M | IAM + service identity |
| Data exfiltration via outputs or tools | Output DLP filters, redaction, retrieval guardrails, data domain tags | Sensitive-output detection, exfil pattern alerts | Data Gov + SecOps | M | Data classification |
| Excessive autonomy / runaway loops | Step budgets, token/tool-call budgets, risk-based halt conditions | Loop anomaly detection, budget breach alerts | Runtime Eng | M | Runtime metering |
| Supply-chain compromise | Signed artifacts, provenance checks, dependency policy, SLSA controls | SBOM drift detection, CVE monitoring | Platform + AppSec | M | CI/CD hardening |
| Model/output reliability failures | Eval gates, reference datasets, canary rollout, fallback policies | Live quality regression dashboards and incident triggers | Applied AI + SRE | M | Eval harness |

## 3) Control Catalog Mapped to OWASP/NIST/SOC2/GDPR
| Control | OWASP LLM Risk Family | NIST AI RMF Function | SOC 2 Area | GDPR Mapping |
|---|---|---|---|---|
| Human approval gates for risky actions | Prompt injection, excessive agency | Govern, Manage | Security, Processing Integrity | Art. 25, Art. 32 |
| Policy-as-code for tool invocation | Insecure output handling, excessive agency | Map, Manage | Security | Art. 5(1)(f), Art. 32 |
| Least-privilege service identities | Broken access control, data leakage | Govern, Manage | Security, Confidentiality | Art. 32 |
| Memory retention + deletion controls | Sensitive information disclosure | Govern, Map | Privacy, Confidentiality | Art. 5(1)(c), 5(1)(e), Art. 17 |
| Immutable audit trail | Insufficient monitoring | Measure, Manage | Processing Integrity, Security | Art. 5(2), Art. 30 |
| Offline + online eval gates | Hallucination / unreliable output risk | Measure, Manage | Availability, Processing Integrity | Art. 24 |
| Runtime abuse monitoring | Denial-of-service / abuse risk | Measure, Manage | Availability, Security | Art. 32 |
| Secure SDLC and provenance | Supply chain vulnerabilities | Govern, Manage | Security | Art. 25, Art. 32 |

## 4) Runtime Guardrails Baseline
Mandatory runtime policies:
- `P0`: block file/network/system-destructive actions unless explicit approval token is present.
- `P1`: require structured tool argument validation before tool execution.
- `P1`: enforce per-run budgets (max steps, max tool calls, max tokens, max wall clock).
- `P1`: quarantine unknown tool signatures and unregistered MCP endpoints.
- `P2`: enforce output redaction for regulated data classes.

Guardrail stack:
- Policy decision point (`allow`, `deny`, `require_approval`) before each high-impact action.
- Tool sandboxing and scoped execution identities.
- Continuous trace capture for all plan/tool/policy events.
- Red-team and regression test suites executed pre-release and periodically in production replay mode.

## 5) Day-0 to Day-90 Hardening Roadmap
### Day 0-15: Foundation
- Stand up centralized policy engine and signed tool registry.
- Instrument end-to-end tracing schema and immutable log storage.
- Define baseline SLOs and security event taxonomy.
- Deliverables: policy repo, trace schema, initial runbook.

### Day 16-45: Reliability and Safety Gates
- Add replayable evaluation harness with pass/fail gates.
- Enforce approval workflow for high-risk categories.
- Implement retry/circuit-breaker/checkpoint patterns in runtime.
- Deliverables: gated CI pipeline, canary deployment templates, rollback playbook.

### Day 46-75: Compliance and Data Governance
- Implement data classification + retention classes for memory.
- Add deletion/export workflows and auditable retention enforcement.
- Roll out IAM hardening and network egress controls.
- Deliverables: compliance evidence matrix, data lifecycle SOP.

### Day 76-90: Adversarial Validation and Operational Readiness
- Run prompt-injection/tool-abuse red-team exercises.
- Tune alert thresholds from production-like replay traffic.
- Perform tabletop incident response exercises for model/tool compromise.
- Deliverables: control effectiveness report, remediation backlog, go-live decision pack.

## 6) Measurable Success Metrics
| Domain | KPI | 90-Day Target |
|---|---|---:|
| Reliability | Successful resumed runs from checkpoints | >= 99.0% |
| Reliability | High-severity rollback time | <= 15 minutes |
| Security | Unauthorized high-risk tool actions | 0 |
| Security | Mean time to detect policy violation | <= 5 minutes |
| Quality | Eval gate pass rate for release candidates | >= 95% |
| Compliance | Traceable evidence coverage for critical controls | 100% |

## 7) Additional Vulnerabilities and Mitigations (v2 Update)
| Vulnerability | Why It Matters | Mitigation |
|---|---|---|
| Feedback poisoning in reflection loop | Malicious or noisy feedback can degrade future behavior | Use multi-signal promotion gates, anomaly scoring, and approval for high-impact changes |
| Acceptance spoofing or replay | Fake or duplicated `accept` can trigger unsafe learning updates | Authenticate message envelope, verify session ownership, enforce nonce and idempotency keys |
| Context window overflow | Model misses critical context, causing poor or unsafe output | Use structured context assembly and salience-based compression with hard keep/drop rules |
| Over-broad error handling | Recovery path is unclear and can loop indefinitely | Split `error` into `retryable`, `policy`, `tool`, and `fatal` classes |
| Log/memory leakage | Sensitive data may be exposed in traces and memory stores | Redact before persistence, encrypt by default, apply retention TTL and access controls |
| Confidence inflation | Model self-reported certainty may hide hallucinations | Compute confidence from objective signals and calibrate against acceptance outcomes |
| Eval undercoverage | Bad changes pass narrow tests and fail real tasks | Add reviewed failures to regression sets and track eval coverage per agent |
| Semantic memory contamination | Wrong or outdated learned facts affect future sessions | Store memory provenance, TTL, confidence, and revocation metadata |
| Denial-of-wallet from loops/tool calls | Model/tool costs grow unexpectedly | Enforce per-session budgets, rate limits, and cost alerts |
| Weak recovery from external outages | MCP/model outage blocks all work | Add retry budgets, circuit breakers, degraded modes, and clear user-facing errors |

## 8) Context-Window Hardening Pattern (v2 Update)
Required components:
- `ContextAssembler` service with explicit token budget and salience ranking.
- Rolling structured summary fields: `facts`, `decisions`, `constraints`, `open_questions`, `user_preferences`.
- Dual data paths:
  - Full immutable audit trail for compliance.
  - Compressed model context log for runtime prompting.

Keep always:
- latest human feedback
- unresolved requirements
- active policy constraints
- current accepted output snapshot

Drop first:
- old raw tool payloads
- repeated intermediate drafts
- verbose chain traces not needed for action

## 9) Confidence-Gated Anti-Hallucination Policy (v2 Update)
Every output contract must include:
- `confidence_score` (`0.0` to `1.0`)
- `confidence_band` (`low|medium|high`)
- `confidence_basis` (retrieval coverage, tool success, consistency checks)

Confidence policy:
- `high`: allow final response.
- `medium`: final response with verification notice.
- `low`: block final response and emit `question` or require human review.

For factual claims:
- Require source traceability to retrieved data/tool evidence.
- Enforce "no source, no claim" for high-impact outputs.

## 10) Recovery Playbooks (v2 Review Update)
| Incident | Immediate Response | Follow-Up |
|---|---|---|
| MCP server unavailable | Stop tool loop, emit `error_retryable`, preserve session checkpoint | Investigate MCP health, retry from checkpoint after recovery |
| Policy blocks required action | Emit `error_policy` with reason and allowed next step | Human/operator updates input, approval, or policy exception |
| Repeated low-confidence output | Emit `question` or require manual review | Add case to eval set and inspect missing data/tool coverage |
| Bad reflection candidate | Quarantine change and keep current config | Add failure to regression suite and review feedback labels |
| Sensitive data detected in memory/logs | Quarantine record and block retrieval | Redact, rotate affected secrets if needed, and record audit action |
| Prompt injection detected in tool output | Ignore malicious segment and continue from sanitized data | Add signature/example to adversarial test set |

## 11) Decision Boundaries for Self-Improvement
Allowed in v1:
- Prompt updates, retrieval strategy updates, and policy tuning through gated workflow.
- Tool configuration improvements in sandbox with approval.

Not allowed in v1:
- Autonomous direct production code rewrite/deploy by the agent without human approval.

## 12) Validation Checklist
- Every high-risk threat has at least one preventive and one detective control.
- Controls map to OWASP + NIST + SOC2 + GDPR viewpoints.
- Roadmap has dated milestones and measurable outcomes.
- Recommendations include owner type, effort, and prerequisites.

## 13) Sources (Primary) and Access Date
Accessed: `2026-04-30`.

1. OWASP Top 10 for LLM Applications project page: [https://owasp.org/www-project-top-10-for-large-language-model-applications](https://owasp.org/www-project-top-10-for-large-language-model-applications)
2. NIST AI RMF hub: [https://www.nist.gov/itl/ai-risk-management-framework](https://www.nist.gov/itl/ai-risk-management-framework)
3. NIST Generative AI Profile (AI 600-1): [https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence)
4. SLSA framework: [https://slsa.dev/](https://slsa.dev/)
5. AICPA SOC 2 overview: [https://www.aicpa-cima.com/topic/audit-assurance/audit-and-assurance-greater-than-soc-2](https://www.aicpa-cima.com/topic/audit-assurance/audit-and-assurance-greater-than-soc-2)
6. GDPR regulation text (reference URL): [https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32016R0679](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32016R0679)

Inference notes:
- The control catalog is an implementation mapping from standards and frameworks to practical platform controls; it is not legal advice.
