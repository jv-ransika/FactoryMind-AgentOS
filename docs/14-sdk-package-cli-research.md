# SDK, Package, CLI, and Developer Experience Research

Access date: 2026-05-01

## 1) Research Question
How should FactoryMind AgentOS be packaged and exposed so developers can install it, define agents, attach skills/memory/tools, run sessions, and enable self-learning?

This block turns the architecture into an installable product.

## 2) Short Answer
FactoryMind AgentOS should be a Python package with:
- typed SDK
- Pydantic schemas
- Typer CLI
- optional FastAPI service
- templates for agents, skills, tools, and policies
- adapter interfaces for runtime, memory, eval, observability, and tools

Recommended v1:

```text
pip install agent-os

agent-os init
agent-os create agent project_selector
agent-os run project_selector
agent-os learn project_selector
agent-os eval project_selector
agent-os promote <candidate_id>
```

V1 should be code-first, not UI-first.

## 3) Package Structure
Use standard Python packaging with `pyproject.toml` and `src/` layout.

```text
agent-os/
  pyproject.toml
  README.md
  docs/
  examples/
  templates/
  tests/
  src/
    agent_os/
      __init__.py
      sdk/
      protocol/
      runtime/
      sessions/
      tools/
      memory/
      skills/
      learning/
      evals/
      policy/
      observability/
      storage/
      adapters/
      cli/
```

Why:
- `src/` layout prevents import mistakes during tests.
- `pyproject.toml` is the modern packaging standard.
- modular structure keeps the FactoryMind AgentOS installable and extensible.

## 4) Public SDK Shape
Agent definition should be simple.

```python
from agent_os import Agent, LearningMode, MemoryPolicy

project_selector = Agent(
    name="project_selector",
    goal="Select the best project using company criteria.",
    learning_mode=LearningMode.AUTO_LOW_RISK,
    memory_policy=MemoryPolicy.COMPANY_CONFIDENTIAL,
    tools=["project_db.search_projects", "project_db.get_project"],
    skills=["project_ranking", "risk_assessment"],
)
```

Session usage:

```python
from agent_os import AgentOS

os = AgentOS.load()

session = os.sessions.init(
    agent_id="project_selector",
    input={"query": "Find the best project for a Python AI team."},
)

result = os.sessions.run(session.session_id)
```

Feedback:

```python
os.sessions.feedback(
    session_id=session.session_id,
    feedback="The selected project is too risky. Prefer lower delivery risk.",
)
```

Acceptance:

```python
os.sessions.accept(session_id=session.session_id)
```

## 5) Agent Manifest
Support Python definitions first, but allow YAML manifests for portability.

```yaml
agent:
  id: project_selector
  goal: Select the best project using company criteria.
  runtime: langgraph
  learning_mode: auto_low_risk
  memory_policy: company_confidential
  tools:
    - project_db.search_projects
    - project_db.get_project
  skills:
    - project_ranking
    - risk_assessment
  output_schema: ProjectSelectionOutput
```

Recommendation:
- v1 supports Python SDK first.
- manifest support can be added for generated templates and CLI.

## 6) Skill Format
Skills should be first-class package assets.

```text
agents/
  project_selector/
    agent.yaml
    skills/
      project_ranking.skill.yaml
      risk_assessment.skill.yaml
```

Skill manifest:

```yaml
skill:
  id: project_ranking
  description: Rank projects using company criteria.
  activation:
    task_types: ["project_selection"]
    keywords: ["best project", "select project", "rank"]
  procedure:
    - Load candidate projects using allowed MCP tools.
    - Score each project using approved ranking criteria.
    - Explain ranking with evidence from project records.
  constraints:
    - Do not invent project facts.
    - Ask a question if ranking criteria are missing.
  status: active
```

## 7) CLI Design
Use Typer for CLI ergonomics.

Recommended commands:

| Command | Purpose |
|---|---|
| `agent-os init` | Initialize project |
| `agent-os create agent <name>` | Scaffold an agent |
| `agent-os create skill <agent> <name>` | Scaffold a skill |
| `agent-os create tool <name>` | Create tool manifest |
| `agent-os run <agent>` | Run local session |
| `agent-os feedback <session_id>` | Add feedback |
| `agent-os accept <session_id>` | Accept final output |
| `agent-os learn <agent>` | Run learning job |
| `agent-os eval <agent>` | Run evals |
| `agent-os candidates <agent>` | List learning candidates |
| `agent-os promote <candidate_id>` | Promote candidate |
| `agent-os rollback <agent>` | Roll back learned change |
| `agent-os audit <session_id>` | Show audit chain |
| `agent-os serve` | Start local FastAPI service |

## 8) Optional FastAPI Service
The package should include an optional service mode:

```text
agent-os serve
```

Endpoints:
- `POST /sessions/init`
- `POST /sessions/{id}/feedback`
- `POST /sessions/{id}/accept`
- `GET /sessions/{id}`
- `GET /sessions/{id}/audit`
- `GET /agents`
- `GET /agents/{id}/candidates`
- `POST /candidates/{id}/promote`
- `POST /agents/{id}/rollback`

Recommendation:
- v1 package should be usable as a library and CLI.
- FastAPI service can be included as optional runtime mode.

## 9) Adapter Interfaces
FactoryMind AgentOS should expose stable internal adapter interfaces:

```text
RuntimeAdapter
MemoryStore
SkillStore
ToolGateway
EvalRunner
PolicyEngine
TraceExporter
ModelProvider
```

This allows:
- LangGraph now, Temporal later
- Postgres now, Mem0/Zep/Cognee later
- Built-in eval now, Promptfoo/Opik/Phoenix later
- OpenAI now, other model providers later

## 10) Configuration
Use typed configuration.

Recommended:
- Pydantic settings
- environment variables
- `.env`
- `agent-os.yaml`

Example:

```yaml
runtime:
  adapter: langgraph

model:
  provider: openai
  model: gpt-4.1-mini

storage:
  postgres_url: ${DATABASE_URL}
  redis_url: ${REDIS_URL}

learning:
  default_mode: collect_only
  auto_low_risk_enabled: false

observability:
  otel_exporter: console
```

## 11) Project Templates
FactoryMind AgentOS should ship templates:

```text
templates/
  basic-agent/
  mcp-agent/
  self-learning-agent/
  project-selector/
  proposal-writer/
```

Template tools:
- built-in simple scaffolder first
- Cookiecutter/Copier compatibility later

Why:
- templates make the platform feel usable immediately
- they encode best practices
- they prevent users from bypassing policy/memory/gateway layers

## 12) Developer Experience Requirements
The first user experience should be:

```text
pip install agent-os
agent-os init
agent-os create agent project_selector
agent-os run project_selector
```

The developer should get:
- working local agent
- local SQLite/Postgres-compatible config
- sample skill
- sample eval
- sample memory
- audit output
- learning mode disabled or collect-only by default

## 13) Packaging and Dependency Strategy
Core install should stay small:

```text
agent-os
  core SDK
  Pydantic schemas
  CLI
  simple storage
  built-in evals
```

Optional extras:

```text
agent-os[langgraph]
agent-os[postgres]
agent-os[redis]
agent-os[fastapi]
agent-os[promptfoo]
agent-os[deepeval]
agent-os[opik]
agent-os[phoenix]
agent-os[aws]
```

Why:
- avoid forcing users to install the whole ecosystem
- keep adapters optional
- reduce dependency conflicts

## 14) Existing Tools Researched
### Python Packaging / pyproject.toml
Use for:
- modern package metadata
- dependencies and optional extras
- console scripts

Recommendation:
- use `pyproject.toml` from v1.

### src layout
Use for:
- catching packaging/import bugs
- clean installable library structure

Recommendation:
- use `src/agent_os`.

### Typer
Use for:
- Python CLI built from typed functions
- developer-friendly commands

Recommendation:
- use for v1 CLI.

### Pydantic / Pydantic Settings
Use for:
- SDK schemas
- config validation
- typed manifest loading

Recommendation:
- use heavily.

### FastAPI
Use for:
- optional service/control-plane mode
- OpenAPI docs for session API

Recommendation:
- optional extra, not required core.

### Cookiecutter / Copier
Use for:
- project scaffolding/templates

Recommendation:
- start with built-in templates, consider Copier/Cookiecutter later.

## 15) Build-vs-Wrap Decision
Build:
- SDK
- CLI
- manifest schemas
- adapter interfaces
- templates
- local service wrapper

Wrap:
- LangGraph
- FastAPI
- Pydantic Settings
- Cookiecutter/Copier if useful later

Do not outsource:
- Agent definition contract
- Skill contract
- Learning mode contract
- Candidate/promotion contract

## 16) Final Recommendation
For FactoryMind AgentOS v1:
- make it a Python package first
- use `pyproject.toml` and `src/` layout
- expose Python SDK and Typer CLI
- include optional FastAPI server
- define agents and skills with typed schemas
- ship templates for project selector and proposal writer
- keep adapters optional through package extras

This makes the product installable and usable before any web UI exists.

## 17) Sources
- Python `pyproject.toml` spec: https://packaging.python.org/specifications/declaring-project-metadata/
- Python guide to writing `pyproject.toml`: https://packaging.python.org/en/latest/guides/writing-pyproject-toml
- Python src layout discussion: https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/
- Pydantic Settings: https://docs.pydantic.dev/latest/api/pydantic_settings/
- Pydantic Settings repository: https://github.com/pydantic/pydantic-settings
- Cookiecutter docs: https://cookiecutter.readthedocs.io/
- Cookiecutter site: https://www.cookiecutter.io/
- Copier docs: https://copier.readthedocs.io/en/stable/generating/
- FastAPI OpenAPI docs: https://fastapi.tiangolo.com/

Research inference:
- A code-first Python SDK and CLI is the fastest way to validate FactoryMind AgentOS as a package. A UI/control plane should come after the core contracts stabilize.

