# Spiral Development Plan: Iteration 2

Access date: 2026-05-01

## 1) Purpose
Iteration 2 adds local-first memory, skills, and context assembly to the FactoryMind AgentOS package.

The goal is to prove the reusable memory/skill contract before adding OpenAI, LangGraph, MCP, Postgres, Redis, or automatic learning.

## 2) Scope
Implemented capabilities:
- typed `MemoryItem`, `SkillDefinition`, `ContextPacket`, and retrieval result models
- local JSON storage under `.agent-os/memory/` and `.agent-os/skills/`
- SDK managers for memory, skills, and context assembly
- CLI commands for creating/listing memory and skills
- explicit skill binding from shared skill library to agents
- CLI command for inspecting assembled context
- deterministic keyword-overlap retrieval
- context packet passed into the local runtime
- local runtime output includes selected memory/skill counts

Still out of scope:
- embeddings
- vector search
- LLM summarization
- OpenAI calls
- LangGraph runtime
- MCP tool gateway
- Postgres/Redis
- automatic learning or promotion

## 3) Implemented Commands
```text
agent-os create memory <agent> --content "..."
agent-os create skill <name> --description "..."
agent-os bind skill <agent> <skill_id>
agent-os list memories <agent>
agent-os list skills <agent>
agent-os list skill-library
agent-os context <agent> --input "..."
```

## 4) Retrieval Rules
Iteration 2 retrieval is intentionally simple:
- match by `agent_id`
- include only `active` items
- exclude `deprecated`, `revoked`, `rejected`, and `candidate` items
- score by case-insensitive keyword overlap
- current input and latest feedback form the retrieval query
- missing memory or skills do not fail the session

## 5) Verification
Verified:
- `python -m pytest -q` passes with 10 tests
- CLI smoke flow passes for `init`, `create agent`, `create memory`, `create skill`, `list memories`, `list skills`, `context`, and `run`

## 6) Next Iteration Gate
Iteration 3 should add the MCP/tool gateway only after this memory/skill/context boundary is accepted.

Recommended Iteration 3 focus:
- registered tool manifest
- local mock tool adapter
- per-agent tool allowlist
- tool call audit events
- no write tools by default

