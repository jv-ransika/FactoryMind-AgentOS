# Memory and Context System Research

Access date: 2026-05-01

## 1) Research Question
How should FactoryMind AgentOS store, retrieve, govern, and assemble long-term memory and learned skills so agents can improve behavior reliably without changing tools, permissions, or code?

Memory is central to the FactoryMind AgentOS idea because our self-learning target is:
- long-term memory
- skills
- procedural behavior
- accepted examples
- task-specific heuristics

## 2) Short Answer
FactoryMind AgentOS should own the memory and skill contract, but support external memory engines through adapters.

Recommended v1:

```text
FactoryMind AgentOS Memory API
  -> MemoryStore interface
  -> SkillLibrary interface
  -> Postgres + pgvector first
  -> Redis for short-term/session cache
  -> optional adapters: Letta, Mem0, Zep, Cognee, MemOS later
```

Do not let any external memory engine directly decide what enters the model context. FactoryMind AgentOS should own context assembly.

## 3) Memory Types
FactoryMind AgentOS should separate memory into explicit types.

| Type | Meaning | Example | Stored Where |
|---|---|---|---|
| Session memory | Current run state and recent messages | latest user feedback, unresolved question | runtime/checkpoint + Redis |
| Episodic memory | Past interaction trace | accepted proposal session | Postgres |
| Semantic memory | Facts/preferences | company prefers concise proposals | Postgres + vector |
| Procedural memory | How-to behavior | steps for proposal opening | SkillLibrary |
| Skill memory | Versioned reusable skill package | `proposal_opening_section` | Postgres + files/vector |
| Feedback memory | Human ratings/corrections | "too generic, mention delivery risk" | Postgres |
| Safety memory | Known unsafe patterns | prompt injection signature | policy/eval store |
| Artifact memory | Outputs/documents generated | accepted proposal draft | object store/Postgres reference |

Important rule:
- Runtime checkpoints are not long-term memory.
- Audit logs are not prompt context.
- Memory is not policy.
- Skills are not tools.

## 4) Skill vs Memory vs Tool
FactoryMind AgentOS should use this distinction:

```text
Memory = what the agent knows
Skill = how the agent should behave
Tool = what the agent is allowed to call
Policy = what the agent must obey
```

Self-learning can update:
- memory
- skills
- skill activation metadata
- skill examples

Self-learning cannot update:
- tools
- permissions
- safety policy
- runtime code

## 5) Memory Item Schema
Every memory item needs governance metadata.

```json
{
  "memory_id": "uuid",
  "agent_id": "proposal_writer",
  "scope": "user|agent|company|global",
  "memory_type": "semantic|episodic|feedback|safety|artifact",
  "content": "string",
  "summary": "string",
  "embedding_ref": "string",
  "source": {
    "session_id": "uuid",
    "message_id": "uuid",
    "tool_call_id": "uuid",
    "created_by": "human|agent|learning_engine|system"
  },
  "privacy_class": "public|internal|confidential|regulated",
  "confidence": 0.0,
  "valid_from": "RFC3339",
  "valid_until": "RFC3339|null",
  "ttl_days": 90,
  "status": "candidate|active|deprecated|revoked",
  "version": "1.0.0",
  "tags": ["proposal", "tone"],
  "created_at": "RFC3339",
  "updated_at": "RFC3339"
}
```

Required behavior:
- latest explicit user input beats memory
- revoked memory must never be retrieved
- expired memory can remain in audit but not active context
- regulated memory requires stricter retrieval and redaction

## 6) Skill Schema
Skills should be stored as versioned procedural memory.

```json
{
  "skill_id": "uuid",
  "agent_id": "proposal_writer",
  "name": "proposal_opening_section",
  "description": "Drafts the opening section using company tone and client context.",
  "activation": {
    "task_types": ["proposal_writing"],
    "keywords": ["proposal", "opening", "introduction"],
    "required_context": ["client_name", "project_summary"]
  },
  "procedure": [
    "Identify the client's stated goal.",
    "State the business problem in the client's language.",
    "Connect company capability to the outcome.",
    "Ask a question if the client goal is missing."
  ],
  "examples": [],
  "constraints": [],
  "failure_modes": [],
  "provenance": {
    "source_sessions": [],
    "created_by": "learning_engine|human",
    "created_at": "RFC3339"
  },
  "quality": {
    "confidence": 0.0,
    "acceptance_rate": 0.0,
    "eval_score": 0.0,
    "last_eval_run_id": "uuid"
  },
  "status": "candidate|active|deprecated|rejected",
  "version": "1.0.0"
}
```

Skills should be compact enough for context use. Long skill documentation should be stored as an artifact and summarized before prompt insertion.

## 7) Context Assembly
FactoryMind AgentOS should build context deterministically.

```text
ContextAssembler
  -> system invariants
  -> active task input
  -> latest human feedback
  -> unresolved requirements
  -> selected active skills
  -> selected active memory
  -> retrieved evidence/tool results
  -> output schema
```

Priority under token pressure:
1. system invariants
2. active user input and latest feedback
3. unresolved requirements
4. applicable active skills
5. high-confidence active memory
6. recent relevant tool results
7. older episodic context

Drop first:
- old raw tool payloads
- duplicate drafts
- low-confidence memories
- low-relevance memories
- inactive/deprecated skills

## 8) Memory Retrieval Rules
Retrieval should combine filters and semantic search.

Required filters:
- `agent_id`
- `scope`
- `status=active`
- `privacy_class allowed`
- `valid_from <= now`
- `valid_until is null or valid_until > now`
- `not revoked`

Ranking signals:
- semantic similarity
- recency
- confidence
- source reliability
- historical usefulness
- skill/task match
- user/company scope priority

Hard rule:
- a high-similarity memory cannot override latest explicit feedback.

## 9) Skill Retrieval Rules
Skill retrieval should be more controlled than memory retrieval.

Retrieve a skill only when:
- task type matches
- required context exists or can be requested
- activation score exceeds threshold
- skill is active
- skill does not conflict with higher-priority skill
- skill token cost fits budget

Skill activation failure should produce:
- no skill loaded, or
- a `question` if required context is missing

## 10) Existing Memory Systems Researched
### Letta / MemGPT
What it provides:
- memory hierarchy
- core memory and archival memory
- self-editing memory tools
- context window management
- agent development environment with memory visibility

Fit:
- excellent conceptual match for memory as an OS concern
- useful reference for memory hierarchy and self-editing memory

Risk:
- giving agents direct memory-editing tools can be risky unless FactoryMind AgentOS policy gates every update
- may be more agent framework than embeddable memory backend for our exact product

Recommendation:
- use as architecture reference
- evaluate adapter later

### Mem0
What it provides:
- universal/self-improving memory layer
- user/session/agent memory
- managed and open-source options
- enterprise controls in managed offering

Fit:
- good memory backend candidate
- useful if we want memory quickly without building vector/graph stack

Risk:
- FactoryMind AgentOS still needs provenance, skill model, promotion gates, and context rules
- memory systems can become attack surfaces; security review is mandatory

Recommendation:
- adapter candidate, not core contract.

### Zep
What it provides:
- temporal knowledge graph memory
- fact invalidation
- entity/fact tracking over time
- memory context strings

Fit:
- strong for evolving facts and user/company state
- useful for memories that change over time

Risk:
- graph memory may be more than v1 needs
- managed dependency/operational choice must be evaluated

Recommendation:
- strong phase-2 adapter candidate for temporal/graph memory.

### Cognee
What it provides:
- graph-backed memory
- vector + graph + relational architecture
- remember/recall/improve/forget operations
- provenance and memory pipelines

Fit:
- strong match for memory as a structured system
- interesting for long-term company knowledge and trace-to-memory learning

Risk:
- must verify maturity, deployment, and control boundaries

Recommendation:
- high-priority research candidate for memory backend or inspiration.

### MemOS
What it provides:
- research direction for memory as an operating-system resource
- memory API/scheduling/storage layers
- memory lifecycle and orchestration concepts

Fit:
- very aligned with FactoryMind AgentOS ambition at concept level
- good inspiration for memory lifecycle design

Risk:
- may be research-grade or too broad for v1
- activation/parameter memory is out of scope for our first product

Recommendation:
- use as design inspiration, not v1 dependency.

### LlamaIndex Memory
What it provides:
- chat memory, fact extraction blocks, vector memory blocks
- customizable memory abstractions

Fit:
- useful reference for memory block design
- helpful if we use LlamaIndex components later

Risk:
- not enough by itself for skill governance and self-learning promotion

Recommendation:
- reference only for v1.

### LangGraph Memory/Persistence
What it provides:
- checkpointing and state persistence
- short-term and long-term memory primitives in LangGraph ecosystem

Fit:
- useful for runtime state and simple memory integration

Risk:
- runtime persistence should not become the whole memory system
- FactoryMind AgentOS still needs memory governance and skill library

Recommendation:
- use LangGraph persistence for runtime checkpoints, not as complete memory layer.

## 11) Recommended V1 Memory Architecture
V1 should start simple but governed.

```text
Postgres
  memories table
  skills table
  skill_versions table
  memory_events table
  skill_events table
  eval_cases table

pgvector
  memory embeddings
  skill embeddings

Redis
  active session cache
  recent context cache
```

Why:
- self-hostable
- inspectable
- easy to audit
- no early managed dependency
- enough for first version

Add adapters later:
- Mem0Adapter
- ZepAdapter
- CogneeAdapter
- LettaAdapter
- MemOSAdapter if mature/useful

## 12) Memory Lifecycle
```text
observed
  -> candidate
  -> validated
  -> active
  -> deprecated
  -> revoked or expired
```

Lifecycle rules:
- candidate memory cannot be used unless learning mode allows it
- active memory can be retrieved into context
- deprecated memory is searchable for audit but not injected
- revoked memory is blocked from retrieval
- expired memory is excluded from active context

## 13) Skill Lifecycle
```text
candidate
  -> evaluating
  -> active
  -> deprecated
  -> rejected
  -> rolled_back
```

Lifecycle rules:
- candidate skills are evaluated before activation
- active skills can be inserted into context
- deprecated skills remain for audit and rollback
- rejected skills cannot be activated automatically
- rolled-back skills create regression cases

## 14) Context Window Safeguards
The ContextAssembler must prevent memory from causing unsafe or stale behavior.

Controls:
- hard token budget
- deterministic priority ordering
- memory confidence threshold
- privacy filter before prompt construction
- skill conflict detection
- explicit user input override
- source labels for factual claims
- no revoked/deprecated memory injection

Required test cases:
- latest feedback conflicts with old memory
- sensitive memory is relevant but not allowed
- two skills conflict
- skill activation false positive
- context token pressure
- revoked memory attempted retrieval

## 15) Build-vs-Wrap Decision
Build:
- memory schema
- skill schema
- context assembler
- provenance model
- lifecycle states
- retrieval filters
- privacy gates
- skill activation rules

Wrap:
- vector store
- graph memory backend later
- external memory engines later

Do not outsource:
- context assembly decision
- skill activation policy
- memory privacy filtering
- memory/skill lifecycle
- revocation and rollback

## 16) Final Recommendation
For FactoryMind AgentOS v1:
- use Postgres + pgvector for long-term memory and skill storage
- use Redis for short-term/session cache
- build FactoryMind AgentOS memory and skill contracts ourselves
- make external memory systems adapters, not core dependencies
- use Letta/MemGPT, MemOS, Zep, Mem0, and Cognee as references and future adapter candidates

This aligns with the product goal:
- installable package
- self-hostable
- industrially auditable
- memory/skill self-learning
- no uncontrolled tool/code mutation

## 17) Sources
- Letta memory overview: https://docs.letta.com/guides/agents/memory
- Letta MemGPT architecture: https://docs.letta.com/guides/agents/architectures/memgpt
- Letta context engineering: https://docs.letta.com/guides/agents/context-engineering
- MemGPT paper: https://arxiv.org/abs/2310.08560
- LangGraph persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- LangGraph memory: https://docs.langchain.com/oss/python/langgraph/add-memory
- LlamaIndex memory docs: https://docs.llamaindex.ai/en/stable/module_guides/deploying/agents/memory/
- Mem0 docs: https://docs.mem0.ai/
- Zep agent memory: https://www.getzep.com/product/agent-memory/
- Zep key concepts: https://help.getzep.com/docs
- Cognee overview: https://docs.cognee.ai/core-concepts/overview
- Cognee memory architecture: https://www.cognee.ai/blog/fundamentals/how-cognee-builds-ai-memory
- MemOS paper page: https://huggingface.co/papers/2507.03724
- MemOS paper: https://arxiv.org/abs/2507.03724
- EverMemOS paper: https://arxiv.org/abs/2601.02163
- PersistBench paper: https://arxiv.org/abs/2602.01146
- LiCoMemory paper: https://arxiv.org/abs/2511.01448

Research inference:
- Existing memory systems are useful, but FactoryMind AgentOS needs its own memory and skill governance because self-learning depends on provenance, lifecycle, eval, and rollback.

