# Policy, Security, and Governance Research

Access date: 2026-05-01

## 1) Research Question
What default policy, security, and governance layer should FactoryMind AgentOS provide so companies can safely run self-learning agents in commercial/industrial environments?

The answer must cover:
- memory/skill learning
- MCP tool use
- data privacy
- approval gates
- auditability
- commercial governance expectations

## 2) Short Answer
FactoryMind AgentOS should ship with a default policy pack and a pluggable policy engine.

Recommended v1:

```text
PolicyEngine
  -> DataPolicy
  -> ToolPolicy
  -> SkillPolicy
  -> MemoryPolicy
  -> LearningPolicy
  -> ApprovalPolicy
  -> AuditPolicy
```

Policy decisions must be deterministic system decisions, not LLM judgments.

## 3) Governance Principles
FactoryMind AgentOS should enforce these principles by default:

| Principle | Meaning |
|---|---|
| Least agency | Agents only get the autonomy required for the task |
| Least privilege | Tools/data are scoped per agent and user |
| Explicit trust boundaries | Tool outputs, memory, and user input are labeled by trust level |
| Human accountability | High-risk actions and learning changes require approval |
| Versioned behavior | Active skills, memory, prompts, and policies are versioned |
| Reversible learning | Every promoted learned change has rollback |
| Audit by default | Sessions, tools, memory updates, and promotions are logged |
| Privacy by design | Sensitive data is classified before storage/model use |
| No silent permission growth | Learning cannot expand tools or permissions |

## 4) Default Policy Decision Interface
```json
{
  "decision_id": "uuid",
  "subject": {
    "agent_id": "project_selector",
    "user_id": "string",
    "tenant_id": "string"
  },
  "action": {
    "type": "tool_call|memory_write|skill_promote|model_context|learning_promote",
    "target": "string",
    "risk_level": "low|medium|high|critical"
  },
  "context": {
    "data_classes": ["internal"],
    "learning_mode": "auto_low_risk",
    "session_state": "RUNNING"
  },
  "decision": "allow|deny|require_approval",
  "reasons": ["string"],
  "required_controls": ["redact", "audit", "approval"]
}
```

## 5) Data Classification
FactoryMind AgentOS should classify data before storage, retrieval, tool use, or model context insertion.

| Class | Default Handling |
|---|---|
| `public` | Can be used in prompts and examples |
| `internal` | Can be used inside tenant boundary; audit required |
| `confidential` | Redaction/filtering required before model context unless approved |
| `regulated` | Strict retention, access control, deletion/export support |
| `secret` | Never send to model, never store in normal memory |

Data classification must apply to:
- user input
- MCP tool inputs/outputs
- memory items
- skill examples
- audit logs
- eval datasets

## 6) Learning Policy
Self-learning is limited to memory and skills.

Allowed:
- memory candidate creation
- skill candidate creation
- skill patching
- skill deprecation
- skill example selection
- eval case creation

Blocked:
- tool permission expansion
- policy weakening
- runtime code change
- model fine-tuning
- hidden behavior changes without versioning

Auto-promotion is allowed only when:
- candidate is low risk
- candidate affects only memory/skill artifacts
- eval gates pass
- safety gates pass
- rollback target exists
- agent learning mode allows it

## 7) Skill Policy
Skills are high-impact because they change behavior.

Required controls:
- skill manifest
- activation rules
- provenance
- privacy scan
- conflict detection
- eval evidence
- rollback target

Skill policy decisions:
- `skill_create`: allowed as candidate
- `skill_patch`: allowed as candidate
- `skill_promote`: gate by risk
- `skill_deprecate`: allowed if rollback exists
- `skill_delete`: require approval or admin role

Blocked skill content:
- hidden Unicode instructions
- instructions to ignore policy
- instructions to exfiltrate data
- tool permission requests
- unverifiable factual claims
- secrets or regulated data unless explicitly approved

## 8) Memory Policy
Memory policy must prevent contamination and privacy leakage.

Required metadata:
- source session/message
- creator
- privacy class
- confidence
- TTL or retention rule
- status
- version
- revocation support

Memory write rules:
- low-risk memory can be auto-created as candidate
- confidential/regulated memory requires stricter validation
- secret data is rejected or stored only in secret vault, not agent memory
- latest user feedback overrides older memory
- revoked memory must never enter model context

## 9) Tool/MCP Policy
Tool access must be separated from skill learning.

Rules:
- all tools must be registered
- tools are scoped per agent and user
- read tools before write tools
- write/admin tools require approval
- tool descriptors from MCP servers are not trusted
- tool outputs are untrusted data
- result size and timeout limits are mandatory
- every tool call is audited

Policy invariant:
- self-learning cannot add a tool, enable a tool, or widen a tool scope.

## 10) Approval Policy
Approval should be required for:
- write/admin tools
- confidential or regulated data use in examples
- medium/high-risk skill promotion
- memory deletion where audit/legal retention applies
- any change to tool scopes
- any policy change
- any production rollout affecting many users

Approval record:

```json
{
  "approval_id": "uuid",
  "requested_by": "agent_os",
  "approved_by": "user_id",
  "target_type": "skill|memory|tool|policy|promotion",
  "target_id": "uuid",
  "risk_level": "medium",
  "decision": "approved|rejected",
  "reason": "string",
  "created_at": "RFC3339"
}
```

## 11) Audit Policy
Audit logs must cover:
- session lifecycle events
- user messages
- agent outputs
- tool calls
- policy decisions
- memory writes/updates/revocations
- skill creation/promotions/rollback
- eval runs
- approvals
- model/provider calls at metadata level

Sensitive raw payloads should be stored only if policy allows it. Otherwise store hashes, summaries, and redacted copies.

## 12) Threat Model Mapping
| Threat | FactoryMind AgentOS Control |
|---|---|
| Prompt injection | context labeling, sanitizer, skill/tool separation |
| Tool poisoning | manifest-owned tool descriptions, MCP scanning, version pinning |
| Memory poisoning | candidate state, provenance, eval gates, revocation |
| Skill poisoning | skill scanning, conflict detection, activation tests |
| Excessive agency | learning modes, approval gates, tool scopes |
| Data exfiltration | classification, redaction, egress limits, audit |
| Overreliance | confidence gates, source requirements, human review |
| Supply chain risk | approved registries, dependency scanning, signed releases |
| Rogue behavior drift | eval replay, live monitoring, rollback |
| Human approval spoofing | authenticated approvals, idempotency, audit chain |

## 13) Standards and Frameworks Researched
### OWASP LLM Top 10 / GenAI Security Project
Use for:
- LLM app security baseline
- prompt injection, sensitive data disclosure, supply chain, excessive agency, overreliance

FactoryMind AgentOS implication:
- implement default controls, not just documentation.

### OWASP Agentic AI Threats and Mitigations
Use for:
- autonomy, tool misuse, agent trust, memory poisoning, cascading effects

FactoryMind AgentOS implication:
- policy must understand agent behavior, not only API calls.

### OWASP Agentic Skills Top 10
Use for:
- skill-specific threats like poisoned skills, insecure metadata, hidden instructions

FactoryMind AgentOS implication:
- skills need manifests, scanning, provenance, and activation gates.

### NIST AI RMF and GenAI Profile
Use for:
- governance structure: govern, map, measure, manage
- risk evidence and evaluation practices

FactoryMind AgentOS implication:
- every learned change should generate evidence.

### ISO/IEC 42001
Use for:
- organization-level AI management system expectations
- lifecycle governance and continuous improvement

FactoryMind AgentOS implication:
- support evidence export and governance hooks.

### CSA MAESTRO
Use for:
- agentic threat modeling across layers
- CI/CD-style threat modeling and risk classification

FactoryMind AgentOS implication:
- include a threat model checklist per agent/template.

### MCP Security Guidance
Use for:
- secure MCP server/client practices
- authorization, validation, consent, monitoring

FactoryMind AgentOS implication:
- MCP gateway is a required security boundary.

## 14) Recommended V1 Policy Pack
Ship a default policy pack:

```text
policies/
  data_policy.yaml
  tool_policy.yaml
  skill_policy.yaml
  memory_policy.yaml
  learning_policy.yaml
  approval_policy.yaml
  audit_policy.yaml
```

V1 policy engine can be simple Python rules first.
Later, add an OPA/Rego adapter or another external policy engine.

## 15) Build-vs-Wrap Decision
Build:
- default policy pack
- policy decision interface
- policy audit records
- skill/memory/tool-specific gates
- approval records
- data classification hooks

Wrap later:
- OPA/Rego
- enterprise IAM/RBAC systems
- DLP scanners
- SIEM/log platforms
- secret managers

Do not outsource:
- learning mode enforcement
- skill/memory promotion policy
- final tool permission decision
- data-to-model boundary decision

## 16) Final Recommendation
For FactoryMind AgentOS v1:
- implement a simple internal policy engine
- ship default policy packs
- enforce policy before model context assembly, memory write, skill promotion, and tool calls
- map controls to OWASP/NIST/ISO concepts for commercial credibility
- keep external policy engines as adapters later

The minimum industrial-ready posture:
- no unregistered tools
- no secret data in model context
- no automatic policy or permission changes
- no unversioned skill/memory promotion
- audit everything important
- rollback every promoted learning change

## 17) Sources
- OWASP Top 10 for LLM Applications: https://owasp.org/www-project-top-10-for-large-language-model-applications
- OWASP LLM Top 10 latest: https://genai.owasp.org/llm-top-10/
- OWASP Agentic AI Threats and Mitigations: https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/
- OWASP Agentic Skills Top 10: https://owasp.org/www-project-agentic-skills-top-10/
- OWASP Secure MCP Server Development: https://genai.owasp.org/resource/a-practical-guide-for-secure-mcp-server-development/
- OWASP AIVSS / AIUC crosswalk: https://aivss.owasp.org/aiuc-aivss-crosswalk
- AWS mapping to OWASP Top 10 for LLM Applications: https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-security/owasp-top-ten.html
- NIST AI RMF: https://www.nist.gov/itl/ai-risk-management-framework
- NIST AI RMF Generative AI Profile: https://www.nist.gov/itl/ai-risk-management-framework
- ISO/IEC 42001: https://www.iso.org/standard/42001
- CSA MAESTRO overview: https://cloudsecurityalliance.org/articles/agentic-ai-threat-modeling-framework-maestro
- CSA MAESTRO lab: https://labs.cloudsecurityalliance.org/maestro/
- MAESTRO GitHub: https://github.com/CloudSecurityAlliance/MAESTRO
- Authenticated Workflows paper: https://arxiv.org/abs/2602.10465
- Agentic AI runtime supply chain paper: https://arxiv.org/abs/2602.19555
- ASTRIDE threat modeling paper: https://arxiv.org/abs/2512.04785

Research inference:
- FactoryMind AgentOS needs a policy layer because memory, skills, and MCP tools create a combined behavior surface that normal app security does not cover by itself.

