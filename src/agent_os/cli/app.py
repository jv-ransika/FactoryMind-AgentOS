from __future__ import annotations

import json
import os

import typer
import uvicorn

from agent_os import (
    AgentOS,
    AgentTier,
    FlamePoolState,
    McpServerConfig,
    MemoryScope,
    MemoryType,
    PromotionMode,
    PromotionPolicy,
    PromotionState,
    ResourceStatus,
    ToolManifest,
    ToolScope,
)
from agent_os.service import create_service_app
from agent_os.storage import StorageMode
from agent_os.runtime import load_runtime_config
from agent_os.service.auth import load_auth_config
from agent_os.deploy import render_ecs_task, required_env_contract
from agent_os.ops.deps import check_dependencies
from agent_os.secrets import SecretManager, redact

app = typer.Typer(help="FactoryMind AgentOS development CLI.")
create_app = typer.Typer(help="Create FactoryMind AgentOS resources.")
list_app = typer.Typer(help="List FactoryMind AgentOS resources.")
bind_app = typer.Typer(help="Bind resources to agents.")
learn_app = typer.Typer(help="Learning pipeline commands.")
flame_app = typer.Typer(help="FLAME temporary-memory commands.")
tool_app = typer.Typer(help="Tool gateway commands.")
mcp_app = typer.Typer(help="MCP server registry commands.")
app.add_typer(create_app, name="create")
app.add_typer(list_app, name="list")
app.add_typer(bind_app, name="bind")
app.add_typer(learn_app, name="learn")
app.add_typer(flame_app, name="flame")
app.add_typer(tool_app, name="tool")
app.add_typer(mcp_app, name="mcp")
worker_app = typer.Typer(help="Background worker commands.")
app.add_typer(worker_app, name="worker")
migrate_app = typer.Typer(help="Database migration commands.")
storage_app = typer.Typer(help="Storage operations.")
runtime_app = typer.Typer(help="Runtime configuration commands.")
app.add_typer(migrate_app, name="migrate")
app.add_typer(storage_app, name="storage")
app.add_typer(runtime_app, name="runtime")
auth_app = typer.Typer(help="Auth configuration commands.")
app.add_typer(auth_app, name="auth")
deploy_app = typer.Typer(help="Deployment helpers.")
ops_app = typer.Typer(help="Operational checks.")
app.add_typer(deploy_app, name="deploy")
app.add_typer(ops_app, name="ops")
secrets_app = typer.Typer(help="Secret management commands.")
app.add_typer(secrets_app, name="secrets")


@app.command()
def init(root: str = ".agent-os") -> None:
    """Initialize a local FactoryMind AgentOS workspace."""
    AgentOS.load(root=root)
    typer.echo(f"Initialized FactoryMind AgentOS workspace at {root}")


@create_app.command("agent")
def create_agent(
    name: str,
    goal: str = typer.Option("A reusable FactoryMind AgentOS agent.", "--goal", "-g"),
    model: str = typer.Option(..., "--model"),
    tenant_id: str = typer.Option("default", "--tenant-id"),
    agent_tier: AgentTier = typer.Option(AgentTier.BASIC_AGENT, "--agent-tier"),
    output_mode: str = typer.Option("text", "--output-mode"),
    output_schema: str | None = typer.Option(None, "--output-schema"),
    root: str = ".agent-os",
) -> None:
    """Create an agent definition."""
    agent_os = AgentOS.load(root=root)
    schema_obj = _json_object(output_schema) if output_schema else None
    agent = agent_os.create_agent(
        agent_id=name,
        goal=goal,
        model=model,
        tenant_id=tenant_id,
        agent_tier=agent_tier,
        output_mode=output_mode,
        output_schema=schema_obj,
    )
    typer.echo(json.dumps(agent.model_dump(mode="json"), indent=2))


@create_app.command("memory")
def create_memory(
    agent: str,
    content: str = typer.Option(..., "--content", "-c"),
    summary: str = typer.Option("", "--summary", "-s"),
    tags: str = typer.Option("", "--tags"),
    scope: MemoryScope = MemoryScope.AGENT,
    memory_type: MemoryType = MemoryType.SEMANTIC,
    status: ResourceStatus = ResourceStatus.ACTIVE,
    confidence: float = typer.Option(0.5, min=0.0, max=1.0),
    root: str = ".agent-os",
) -> None:
    """Create a local memory item for an agent."""
    agent_os = AgentOS.load(root=root)
    memory = agent_os.memory.create(
        agent_id=agent,
        content=content,
        summary=summary,
        tags=_split_csv(tags),
        scope=scope,
        memory_type=memory_type,
        status=status,
        confidence=confidence,
    )
    typer.echo(json.dumps(memory.model_dump(mode="json"), indent=2))


@create_app.command("skill")
def create_skill(
    name: str,
    description: str = typer.Option(..., "--description", "-d"),
    owner_agent: str | None = typer.Option(None, "--owner-agent"),
    activation_keywords: str = typer.Option("", "--activation-keywords", "--keywords"),
    procedure: str = typer.Option("", "--procedure"),
    constraints: str = typer.Option("", "--constraints"),
    status: ResourceStatus = ResourceStatus.ACTIVE,
    confidence: float = typer.Option(0.5, min=0.0, max=1.0),
    root: str = ".agent-os",
) -> None:
    """Create a reusable local skill definition."""
    agent_os = AgentOS.load(root=root)
    skill = agent_os.skills.create(
        name=name,
        description=description,
        owner_agent_id=owner_agent,
        activation_keywords=_split_csv(activation_keywords),
        procedure=_split_csv(procedure),
        constraints=_split_csv(constraints),
        status=status,
        confidence=confidence,
    )
    typer.echo(json.dumps(skill.model_dump(mode="json"), indent=2))


@create_app.command("tool")
def create_tool(
    name: str,
    scope: ToolScope = ToolScope.READ,
    description: str = typer.Option("", "--description", "-d"),
    input_schema: str = typer.Option("{}", "--input-schema"),
    output_schema: str = typer.Option("{}", "--output-schema"),
    timeout_ms: int = typer.Option(2000, "--timeout-ms", min=1),
    max_input_bytes: int = typer.Option(8192, "--max-input-bytes", min=1),
    max_output_bytes: int = typer.Option(32768, "--max-output-bytes", min=1),
    enabled: bool = typer.Option(True, "--enabled/--disabled"),
    version: str = typer.Option("1.0.0", "--version"),
    root: str = ".agent-os",
) -> None:
    """Create a tool manifest in the registry."""
    agent_os = AgentOS.load(root=root)
    manifest = ToolManifest(
        name=name,
        scope=scope,
        description=description,
        input_schema=_json_object(input_schema),
        output_schema=_json_object(output_schema),
        timeout_ms=timeout_ms,
        max_input_bytes=max_input_bytes,
        max_output_bytes=max_output_bytes,
        enabled=enabled,
        version=version,
    )
    created = agent_os.tools.register(manifest)
    typer.echo(json.dumps(created.model_dump(mode="json"), indent=2))


@bind_app.command("skill")
def bind_skill(agent: str, skill_id: str, root: str = ".agent-os") -> None:
    """Bind an existing skill to an agent."""
    agent_os = AgentOS.load(root=root)
    agent_os.skills.bind(agent_id=agent, skill_id=skill_id)
    typer.echo(json.dumps({"agent_id": agent, "skill_id": skill_id, "bound": True}, indent=2))


@bind_app.command("tool")
def bind_tool(
    agent: str,
    tool_id: str,
    allow_write: bool = typer.Option(False, "--allow-write"),
    root: str = ".agent-os",
) -> None:
    """Bind a registered tool to an agent allowlist."""
    agent_os = AgentOS.load(root=root)
    agent_os.tools.bind(agent_id=agent, tool_id=tool_id, allow_write=allow_write)
    typer.echo(
        json.dumps(
            {
                "agent_id": agent,
                "tool_id": tool_id,
                "allow_write": allow_write,
                "bound": True,
            },
            indent=2,
        )
    )


@list_app.command("memories")
def list_memories(agent: str, root: str = ".agent-os") -> None:
    """List local memory items for an agent."""
    agent_os = AgentOS.load(root=root)
    memories = agent_os.memory.list(agent)
    typer.echo(json.dumps([memory.model_dump(mode="json") for memory in memories], indent=2))


@list_app.command("skills")
def list_skills(agent: str, root: str = ".agent-os") -> None:
    """List local skill definitions for an agent."""
    agent_os = AgentOS.load(root=root)
    skills = agent_os.skills.list(agent)
    typer.echo(json.dumps([skill.model_dump(mode="json") for skill in skills], indent=2))


@list_app.command("skill-library")
def list_skill_library(root: str = ".agent-os") -> None:
    """List all reusable skills in the local library."""
    agent_os = AgentOS.load(root=root)
    skills = agent_os.skills.list_library()
    typer.echo(json.dumps([skill.model_dump(mode="json") for skill in skills], indent=2))


@list_app.command("tools")
def list_tools(root: str = ".agent-os") -> None:
    """List all registered tools."""
    agent_os = AgentOS.load(root=root)
    tools = agent_os.tools.list()
    typer.echo(json.dumps([tool.model_dump(mode="json") for tool in tools], indent=2))


@list_app.command("agent-tools")
def list_agent_tools(agent: str, root: str = ".agent-os") -> None:
    """List tools currently bound to an agent."""
    agent_os = AgentOS.load(root=root)
    tools = agent_os.tools.list(agent_id=agent)
    typer.echo(json.dumps([tool.model_dump(mode="json") for tool in tools], indent=2))


@app.command()
def context(
    agent: str,
    input: str = typer.Option(..., "--input", "-i"),
    root: str = ".agent-os",
) -> None:
    """Build a deterministic local context packet."""
    agent_os = AgentOS.load(root=root)
    packet = agent_os.context.build(agent_id=agent, active_input=input)
    typer.echo(json.dumps(packet.model_dump(mode="json"), indent=2))


@app.command()
def run(
    agent: str,
    input: str = typer.Option(..., "--input", "-i"),
    runtime: str = typer.Option("local", "--runtime"),
    root: str = ".agent-os",
) -> None:
    """Start and run a local agent session."""
    agent_os = AgentOS.load(root=root, runtime_mode=runtime)
    session = agent_os.sessions.init(agent_id=agent, input=input)
    output = agent_os.sessions.run(session.session_id)
    typer.echo(
        json.dumps(
            {
                "session_id": session.session_id,
                "output": output.model_dump(mode="json"),
            },
            indent=2,
        )
    )


@app.command()
def feedback(
    session_id: str,
    text: str = typer.Option(..., "--text", "-t"),
    root: str = ".agent-os",
) -> None:
    """Append human feedback to a session."""
    agent_os = AgentOS.load(root=root)
    event = agent_os.sessions.feedback(session_id=session_id, feedback=text)
    typer.echo(json.dumps(event.model_dump(mode="json"), indent=2))


@app.command()
def accept(
    session_id: str,
    note: str | None = typer.Option(None, "--note", "-n"),
    root: str = ".agent-os",
) -> None:
    """Mark a session outcome as accepted."""
    agent_os = AgentOS.load(root=root)
    event = agent_os.sessions.accept(session_id=session_id, note=note)
    typer.echo(json.dumps(event.model_dump(mode="json"), indent=2))


@learn_app.command("run")
def learn_run(
    agent: str,
    window_size: int = typer.Option(50, "--window-size", min=1),
    root: str = ".agent-os",
) -> None:
    """Run suggest-only learning on recent accepted sessions."""
    agent_os = AgentOS.load(root=root)
    run = agent_os.learning.run(agent_id=agent, window_size=window_size)
    typer.echo(json.dumps(run.model_dump(mode="json"), indent=2))


@learn_app.command("list-runs")
def learn_list_runs(agent: str, root: str = ".agent-os") -> None:
    """List learning runs for an agent."""
    agent_os = AgentOS.load(root=root)
    runs = agent_os.learning.list_runs(agent_id=agent)
    typer.echo(json.dumps([run.model_dump(mode="json") for run in runs], indent=2))


policy_app = typer.Typer(help="Learning promotion policy commands.")
learn_app.add_typer(policy_app, name="policy")


@policy_app.command("get")
def learn_policy_get(agent: str, root: str = ".agent-os") -> None:
    """Get per-agent promotion policy."""
    agent_os = AgentOS.load(root=root)
    policy = agent_os.learning.get_policy(agent_id=agent)
    typer.echo(json.dumps(policy.model_dump(mode="json"), indent=2))


@policy_app.command("set")
def learn_policy_set(
    agent: str,
    mode: PromotionMode = typer.Option(PromotionMode.AUTO_LOW_RISK, "--mode"),
    max_safety_failures: int = typer.Option(0, "--max-safety-failures", min=0),
    max_regression_warnings: int = typer.Option(1, "--max-regression-warnings", min=0),
    min_confidence: float = typer.Option(0.60, "--min-confidence", min=0.0, max=1.0),
    min_quality_delta: float = typer.Option(0.02, "--min-quality-delta"),
    root: str = ".agent-os",
) -> None:
    """Set per-agent promotion policy."""
    agent_os = AgentOS.load(root=root)
    policy = PromotionPolicy(
        agent_id=agent,
        mode=mode,
        max_safety_failures=max_safety_failures,
        max_regression_warnings=max_regression_warnings,
        min_confidence=min_confidence,
        min_quality_delta=min_quality_delta,
    )
    updated = agent_os.learning.set_policy(agent_id=agent, policy=policy)
    typer.echo(json.dumps(updated.model_dump(mode="json"), indent=2))


@flame_app.command("pool")
def flame_pool(
    agent: str,
    state: FlamePoolState | None = typer.Option(None, "--state"),
    root: str = ".agent-os",
) -> None:
    """List FLAME temporary pool items for an agent."""
    agent_os = AgentOS.load(root=root)
    rows = agent_os.flame.list_pool(agent_id=agent, state=state)
    typer.echo(json.dumps([row.model_dump(mode="json") for row in rows], indent=2))


@flame_app.command("runs")
def flame_runs(agent: str, root: str = ".agent-os") -> None:
    """List FLAME reflection batch runs for an agent."""
    agent_os = AgentOS.load(root=root)
    runs = agent_os.flame.list_runs(agent_id=agent)
    typer.echo(json.dumps([run.model_dump(mode="json") for run in runs], indent=2))


@flame_app.command("trigger")
def flame_trigger(
    agent: str | None = typer.Option(None, "--agent"),
    force: bool = typer.Option(False, "--force"),
    root: str = ".agent-os",
) -> None:
    """Trigger FLAME reflection pass for one agent or all self-learning agents."""
    agent_os = AgentOS.load(root=root)
    runs = agent_os.flame.trigger(agent_id=agent, force=force)
    typer.echo(json.dumps([run.model_dump(mode="json") for run in runs], indent=2))


@tool_app.command("call")
def tool_call(
    agent: str,
    tool_id: str,
    args: str = typer.Option("{}", "--args"),
    session_id: str | None = typer.Option(None, "--session-id"),
    root: str = ".agent-os",
) -> None:
    """Execute a tool via the secure gateway."""
    agent_os = AgentOS.load(root=root)
    result, audit = agent_os.tools.call(
        agent_id=agent,
        session_id=session_id,
        tool_id=tool_id,
        args=_json_object(args),
    )
    typer.echo(
        json.dumps(
            {
                "result": result.model_dump(mode="json"),
                "audit": audit.model_dump(mode="json"),
            },
            indent=2,
        )
    )


@tool_app.command("audit")
def tool_audit(agent: str, session_id: str | None = typer.Option(None, "--session-id"), root: str = ".agent-os") -> None:
    """List tool audit events for an agent."""
    agent_os = AgentOS.load(root=root)
    audits = agent_os.tools.audit(agent_id=agent, session_id=session_id)
    typer.echo(json.dumps([audit.model_dump(mode="json") for audit in audits], indent=2))


@tool_app.command("register-mcp")
def tool_register_mcp(
    name: str,
    mcp_server: str = typer.Option(..., "--mcp-server"),
    mcp_tool_name: str = typer.Option(..., "--mcp-tool-name"),
    scope: ToolScope = ToolScope.READ,
    description: str = typer.Option("", "--description", "-d"),
    input_schema: str = typer.Option("{}", "--input-schema"),
    output_schema: str = typer.Option("{}", "--output-schema"),
    timeout_ms: int = typer.Option(2000, "--timeout-ms", min=1),
    max_input_bytes: int = typer.Option(8192, "--max-input-bytes", min=1),
    max_output_bytes: int = typer.Option(32768, "--max-output-bytes", min=1),
    enabled: bool = typer.Option(True, "--enabled/--disabled"),
    version: str = typer.Option("1.0.0", "--version"),
    root: str = ".agent-os",
) -> None:
    """Register a tool manifest mapped to an MCP remote tool."""
    agent_os = AgentOS.load(root=root)
    created = agent_os.tools.register_mcp_tool(
        name=name,
        mcp_server=mcp_server,
        mcp_tool_name=mcp_tool_name,
        scope=scope,
        description=description,
        input_schema=_json_object(input_schema),
        output_schema=_json_object(output_schema),
        timeout_ms=timeout_ms,
        max_input_bytes=max_input_bytes,
        max_output_bytes=max_output_bytes,
        enabled=enabled,
        version=version,
    )
    typer.echo(json.dumps(created.model_dump(mode="json"), indent=2))


server_app = typer.Typer(help="Manage MCP servers.")
mcp_app.add_typer(server_app, name="server")


@server_app.command("add")
def mcp_server_add(
    name: str,
    endpoint: str = typer.Option(..., "--endpoint"),
    transport: str = typer.Option("http", "--transport"),
    auth_env_var: str | None = typer.Option(None, "--auth-env-var"),
    timeout_ms: int = typer.Option(2000, "--timeout-ms", min=1),
    enabled: bool = typer.Option(True, "--enabled/--disabled"),
    root: str = ".agent-os",
) -> None:
    agent_os = AgentOS.load(root=root)
    if transport != "http":
        raise typer.BadParameter("Only transport=http is supported in this iteration.")
    cfg = McpServerConfig(
        name=name,
        endpoint=endpoint,
        transport="http",
        auth_env_var=auth_env_var,
        timeout_ms=timeout_ms,
        enabled=enabled,
    )
    created = agent_os.tools.mcp.add(cfg)
    typer.echo(json.dumps(created.model_dump(mode="json"), indent=2))


@server_app.command("list")
def mcp_server_list(root: str = ".agent-os") -> None:
    agent_os = AgentOS.load(root=root)
    servers = agent_os.tools.mcp.list()
    typer.echo(json.dumps([item.model_dump(mode="json") for item in servers], indent=2))


@server_app.command("remove")
def mcp_server_remove(name: str, root: str = ".agent-os") -> None:
    agent_os = AgentOS.load(root=root)
    removed = agent_os.tools.mcp.remove(name)
    typer.echo(json.dumps({"removed": removed, "name": name}, indent=2))


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port"),
    root: str = ".agent-os",
    runtime: str = typer.Option("local", "--runtime"),
    auth_enforced: bool = typer.Option(True, "--auth-enforced/--auth-disabled"),
) -> None:
    """Run FactoryMind AgentOS as a FastAPI service."""
    agent_os = AgentOS.load(root=root, runtime_mode=runtime)
    service = create_service_app(agent_os) if auth_enforced else create_service_app(agent_os)
    uvicorn.run(service, host=host, port=port, log_level="info")


@worker_app.command("run")
def worker_run(
    once: bool = typer.Option(False, "--once"),
    root: str = ".agent-os",
) -> None:
    """Run the local durable background worker loop."""
    agent_os = AgentOS.load(root=root)
    processed = agent_os.jobs.run_worker(once=once)
    typer.echo(json.dumps({"processed": processed}, indent=2))


@worker_app.command("tick")
def worker_tick(root: str = ".agent-os") -> None:
    """Process one pending job if available."""
    agent_os = AgentOS.load(root=root)
    job = agent_os.jobs.process_next()
    typer.echo(json.dumps({"processed": bool(job), "job": job}, indent=2, default=str))


def _split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _json_object(value: str) -> dict:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise typer.BadParameter("Expected a JSON object.")
    return parsed


@migrate_app.command("upgrade")
def migrate_upgrade(revision: str = typer.Argument("head"), root: str = ".agent-os") -> None:
    """Run Alembic upgrade."""
    agent_os = AgentOS.load(root=root)
    typer.echo(json.dumps({"result": agent_os.migrate.upgrade(revision)}, indent=2))


@migrate_app.command("downgrade")
def migrate_downgrade(revision: str, root: str = ".agent-os") -> None:
    """Run Alembic downgrade."""
    agent_os = AgentOS.load(root=root)
    typer.echo(json.dumps({"result": agent_os.migrate.downgrade(revision)}, indent=2))


@migrate_app.command("status")
def migrate_status(root: str = ".agent-os") -> None:
    """Show migration status."""
    agent_os = AgentOS.load(root=root)
    typer.echo(json.dumps({"result": agent_os.migrate.status()}, indent=2))


@storage_app.command("verify-shadow")
def storage_verify_shadow(
    agent: str | None = typer.Option(None, "--agent"),
    root: str = ".agent-os",
    postgres_dsn: str | None = typer.Option(None, "--postgres-dsn"),
    redis_url: str | None = typer.Option(None, "--redis-url"),
) -> None:
    """Verify dual-write parity."""
    agent_os = AgentOS.load(
        root=root,
        storage_mode=StorageMode.DUAL_WRITE,
        postgres_dsn=postgres_dsn,
        redis_url=redis_url,
    )
    typer.echo(json.dumps(agent_os.storage.verify_shadow(agent_id=agent), indent=2))


@storage_app.command("cutover")
def storage_cutover(
    read_source: str = typer.Option(..., "--read-source"),
    root: str = ".agent-os",
    postgres_dsn: str | None = typer.Option(None, "--postgres-dsn"),
    redis_url: str | None = typer.Option(None, "--redis-url"),
) -> None:
    """Switch read source in dual-write mode."""
    if read_source not in {"local", "postgres"}:
        raise typer.BadParameter("--read-source must be local or postgres")
    agent_os = AgentOS.load(
        root=root,
        storage_mode=StorageMode.DUAL_WRITE,
        postgres_dsn=postgres_dsn,
        redis_url=redis_url,
        read_source=read_source,
    )
    typer.echo(json.dumps({"mode": "dual_write", "read_source": read_source, "ok": bool(agent_os)}, indent=2))


@runtime_app.command("validate-config")
def runtime_validate_config(
    root: str = ".agent-os",
    runtime_mode: str = typer.Option("openai", "--runtime-mode"),
    openai_api_key: str | None = typer.Option(None, "--openai-api-key"),
    openai_base_url: str | None = typer.Option(None, "--openai-base-url"),
    openai_timeout_ms: int | None = typer.Option(None, "--openai-timeout-ms"),
) -> None:
    secrets = SecretManager(root=root)
    cfg = load_runtime_config(
        root=root,
        runtime_mode=runtime_mode,
        openai_api_key=openai_api_key,
        openai_base_url=openai_base_url,
        openai_timeout_ms=openai_timeout_ms,
        secrets=secrets,
    )
    ok = True
    errors: list[str] = []
    if cfg.mode == "openai" and not cfg.openai_api_key:
        ok = False
        errors.append("OPENAI_API_KEY is required for openai mode.")
    typer.echo(json.dumps({"ok": ok, "mode": cfg.mode, "errors": errors, "config": cfg.model_dump(mode='json')}, indent=2))


@auth_app.command("show-config")
def auth_show_config(root: str = ".agent-os") -> None:
    secrets = SecretManager(root=root)
    cfg = load_auth_config(root=root, secrets=secrets)
    typer.echo(json.dumps(redact(cfg.model_dump(mode="json")), indent=2))


@auth_app.command("validate-token")
def auth_validate_token(
    token: str = typer.Option(..., "--token"),
    root: str = ".agent-os",
) -> None:
    secrets = SecretManager(root=root)
    cfg = load_auth_config(root=root, secrets=secrets)
    try:
        if token.startswith("dev."):
            import base64

            payload = token.split(".", 1)[1]
            claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode("utf-8"))
        else:
            import jwt  # type: ignore

            if cfg.public_key_path:
                with open(cfg.public_key_path, "r", encoding="utf-8") as handle:
                    key = handle.read()
                claims = jwt.decode(token, key, algorithms=["RS256"], audience=cfg.audience, issuer=cfg.issuer)
            elif cfg.jwks_url:
                client = jwt.PyJWKClient(cfg.jwks_url)
                key = client.get_signing_key_from_jwt(token).key
                claims = jwt.decode(token, key, algorithms=["RS256"], audience=cfg.audience, issuer=cfg.issuer)
            else:
                raise ValueError("No verifier configured.")
        typer.echo(json.dumps({"ok": True, "claims": claims}, indent=2))
    except Exception as exc:  # noqa: BLE001
        typer.echo(json.dumps({"ok": False, "error": str(exc), "issuer": cfg.issuer, "audience": cfg.audience}, indent=2))


@deploy_app.command("validate-config")
def deploy_validate_config(
    env: str = typer.Option("prod", "--env"),
    root: str = ".agent-os",
) -> None:
    secrets = SecretManager(root=root)
    deps = check_dependencies(root=root, postgres_dsn=None, redis_url=None, require_migration_head=(env == "prod"), secrets=secrets)
    required = required_env_contract()
    missing_env = [key for key in required if secrets.get(key) is None]
    ok = deps["postgres_ok"] and deps["redis_ok"] and deps["migration_ok"] and not missing_env
    typer.echo(json.dumps({"ok": ok, "env": env, "deps": deps, "missing_env": missing_env}, indent=2))


@deploy_app.command("print-ecs-task")
def deploy_print_ecs_task(
    role: str = typer.Option(..., "--role"),
    image: str = typer.Option("factorymind-agentos:latest", "--image"),
) -> None:
    task = render_ecs_task(role=role, image=image)
    typer.echo(json.dumps(task, indent=2))


@ops_app.command("check-deps")
def ops_check_deps(
    root: str = ".agent-os",
    postgres_dsn: str | None = typer.Option(None, "--postgres-dsn"),
    redis_url: str | None = typer.Option(None, "--redis-url"),
    require_migration_head: bool = typer.Option(True, "--require-migration-head/--skip-migration-head"),
) -> None:
    secrets = SecretManager(root=root)
    status = check_dependencies(
        root=root,
        postgres_dsn=postgres_dsn,
        redis_url=redis_url,
        require_migration_head=require_migration_head,
        secrets=secrets,
    )
    typer.echo(json.dumps(status, indent=2))


@secrets_app.command("show-status")
def secrets_show_status(root: str = ".agent-os") -> None:
    manager = SecretManager(root=root)
    typer.echo(json.dumps(redact(manager.status()), indent=2))


@secrets_app.command("validate")
def secrets_validate(
    env: str = typer.Option("dev", "--env"),
    root: str = ".agent-os",
) -> None:
    manager = SecretManager(root=root)
    profile = "prod" if env == "prod" else "dev"
    result = manager.validate_required(profile=profile)
    typer.echo(json.dumps(redact(result), indent=2))


@secrets_app.command("reload")
def secrets_reload(root: str = ".agent-os") -> None:
    manager = SecretManager(root=root)
    result = manager.reload()
    typer.echo(json.dumps(redact(result), indent=2))


if __name__ == "__main__":
    app()


