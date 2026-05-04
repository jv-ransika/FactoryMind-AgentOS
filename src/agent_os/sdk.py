from __future__ import annotations

from pathlib import Path
import os

from agent_os.capabilities import ModelCapabilityRegistry
from agent_os.context import ContextAssembler
from agent_os.flame import FlameManager
from agent_os.embeddings import OpenAIEmbeddingProvider
from agent_os.context.window_manager import ContextWindowManager
from agent_os.idempotency import IdempotencyStore
from agent_os.jobs import JobManager
from agent_os.learning import LearningManager
from agent_os.memory import MemoryManager
from agent_os.monitoring import MonitorManager, UsageTracker
from agent_os.observability import MetricsStore
from agent_os.ops.deps import check_dependencies, environment_mode
from agent_os.protocol import AgentDefinition, AgentTier, LearningMode
from agent_os.runtime import AgentRuntimeAdapter, LocalRuntimeAdapter, OpenAIRuntimeAdapter, load_runtime_config
from agent_os.secrets import SecretManager
from agent_os.sessions import SessionManager
from agent_os.skills import SkillManager
from agent_os.storage import (
    DomainStore,
    LocalQueueStore,
    LocalStore,
    MigrationManager,
    PostgresDomainStore,
    RedisIdempotencyStore,
    RedisQueueStore,
    StorageMode,
)
from agent_os.tools import ToolManager


class Agent(AgentDefinition):
    pass


class AgentOS:
    def __init__(
        self,
        store: DomainStore,
        runtime: AgentRuntimeAdapter | None = None,
        idempotency_store: IdempotencyStore | object | None = None,
        queue_store: LocalQueueStore | object | None = None,
    ) -> None:
        self.store = store
        self.root = store.root
        self.secrets = SecretManager(root=self.root)
        self.runtime = runtime or LocalRuntimeAdapter()
        self.metrics = MetricsStore(root=self.root)
        cfg = getattr(self.runtime, "config", None)
        embedding_provider = None
        if cfg is not None and str(getattr(cfg, "embedding_provider", "openai")).lower() == "openai":
            embedding_provider = OpenAIEmbeddingProvider(
                api_key=getattr(cfg, "openai_api_key", None),
                model=str(getattr(cfg, "embedding_model", "text-embedding-3-small")),
                base_url=getattr(cfg, "openai_base_url", None),
                timeout_ms=int(getattr(cfg, "openai_timeout_ms", 20000)),
            )
        self.usage = UsageTracker(root=self.root)
        self.capabilities = ModelCapabilityRegistry(root=self.root)
        self.memory = MemoryManager(
            store=self.store,
            embedding_provider=embedding_provider,
            vector_top_k=int(getattr(cfg, "memory_vector_top_k", 5) if cfg is not None else 5),
            metrics=self.metrics,
            usage_tracker=self.usage,
            capabilities=self.capabilities,
        )
        self.skills = SkillManager(store=self.store)
        self.tools = ToolManager(store=self.store)
        self.context = ContextAssembler(memory=self.memory)
        flame_pool_size_trigger = int(getattr(cfg, "flame_pool_size_trigger", 12))
        flame_time_trigger_hours = int(getattr(cfg, "flame_time_trigger_hours", 24))
        self.flame = FlameManager(
            store=self.store,
            memory=self.memory,
            runtime=self.runtime,
            usage_tracker=self.usage,
            capabilities=self.capabilities,
            metrics=self.metrics if hasattr(self, "metrics") else None,
            pool_size_trigger=flame_pool_size_trigger,
            time_trigger_hours=flame_time_trigger_hours,
        )
        self.learning = LearningManager(store=self.store, flame=self.flame, usage_tracker=self.usage)
        self.sessions = SessionManager(store=self.store, runtime=self.runtime, context=self.context)
        self.idempotency = idempotency_store or IdempotencyStore(root=self.root)
        self.flame.metrics = self.metrics
        self.jobs = JobManager(root=self.root, agent_os=self, queue_store=queue_store, idempotency=self.idempotency)
        self.migrate = MigrationManager(root=Path.cwd())
        self.storage = _StorageOps(self)
        self.context_window_manager = ContextWindowManager()
        self.monitor = MonitorManager(agent_os=self)
        self.sessions.on_accept = self._handle_session_accept

        if isinstance(self.runtime, OpenAIRuntimeAdapter):
            self.runtime.metrics = self.metrics
            self.runtime.capabilities = self.capabilities
            self.runtime.context_window_manager = self.context_window_manager
            self.runtime.usage_tracker = self.usage

    @classmethod
    def load(
        cls,
        root: Path | str = ".agent-os",
        runtime: AgentRuntimeAdapter | None = None,
        runtime_mode: str = "local",
        openai_api_key: str | None = None,
        openai_base_url: str | None = None,
        openai_timeout_ms: int | None = None,
        storage_mode: StorageMode = StorageMode.LOCAL,
        postgres_dsn: str | None = None,
        redis_url: str | None = None,
        read_source: str = "local",
    ) -> "AgentOS":
        secrets = SecretManager(root=root)
        env_mode = environment_mode()
        cfg = load_runtime_config(
            root=root,
            runtime_mode=runtime_mode,
            openai_api_key=openai_api_key,
            openai_base_url=openai_base_url,
            openai_timeout_ms=openai_timeout_ms,
            secrets=secrets,
        )
        local = LocalStore(root)
        local.init()
        selected_runtime = runtime
        if selected_runtime is None:
            if cfg.mode == "openai":
                selected_runtime = OpenAIRuntimeAdapter(config=cfg)
            else:
                selected_runtime = LocalRuntimeAdapter()
        if env_mode == "prod" and storage_mode == StorageMode.LOCAL:
            raise RuntimeError("prod mode requires external postgres+redis storage.")
        if storage_mode == StorageMode.LOCAL:
            app = cls(store=local, runtime=selected_runtime)
            app.secrets = secrets
            app.capabilities.runtime_config_loader = lambda: load_runtime_config(
                root=root,
                runtime_mode=runtime_mode,
                openai_api_key=openai_api_key,
                openai_base_url=openai_base_url,
                openai_timeout_ms=openai_timeout_ms,
                secrets=app.secrets,
            )
            if isinstance(app.runtime, OpenAIRuntimeAdapter):
                app.runtime.metrics = app.metrics
                app.runtime.config_loader = lambda: load_runtime_config(
                    root=root,
                    runtime_mode=runtime_mode,
                    openai_api_key=openai_api_key,
                    openai_base_url=openai_base_url,
                    openai_timeout_ms=openai_timeout_ms,
                    secrets=app.secrets,
                )
                app.runtime.capabilities = app.capabilities
                app.runtime.context_window_manager = app.context_window_manager
                app.runtime.usage_tracker = app.usage
            return app
        if storage_mode == StorageMode.DUAL_WRITE:
            raise RuntimeError(
                "vector_backend_required: storage_mode=dual_write is disabled; use storage_mode=postgres_redis with pgvector"
            )

        pg_dsn = secrets.resolve(postgres_dsn) or secrets.get("AGENT_OS_POSTGRES_DSN")
        r_url = secrets.resolve(redis_url) or secrets.get("AGENT_OS_REDIS_URL")
        if not pg_dsn:
            raise ValueError("Postgres DSN is required for non-local storage modes.")
        if not r_url:
            raise ValueError("Redis URL is required for non-local storage modes.")
        if env_mode == "prod":
            status = check_dependencies(root=root, postgres_dsn=pg_dsn, redis_url=r_url, require_migration_head=True, secrets=secrets)
            if not (status["postgres_ok"] and status["redis_ok"] and status["migration_ok"]):
                raise RuntimeError(f"prod dependency check failed: {status['errors']}")
        pg = PostgresDomainStore(dsn=pg_dsn, root=root)
        pg.init()
        store = pg
        if RedisIdempotencyStore is None or RedisQueueStore is None:
            raise RuntimeError("redis package is required for non-local storage modes.")
        idem = RedisIdempotencyStore(redis_url=r_url)
        queue = RedisQueueStore(redis_url=r_url)
        app = cls(store=store, runtime=selected_runtime, idempotency_store=idem, queue_store=queue)
        app.secrets = secrets
        app.capabilities.runtime_config_loader = lambda: load_runtime_config(
            root=root,
            runtime_mode=runtime_mode,
            openai_api_key=openai_api_key,
            openai_base_url=openai_base_url,
            openai_timeout_ms=openai_timeout_ms,
            secrets=app.secrets,
        )
        if isinstance(app.runtime, OpenAIRuntimeAdapter):
            app.runtime.metrics = app.metrics
            app.runtime.config_loader = lambda: load_runtime_config(
                root=root,
                runtime_mode=runtime_mode,
                openai_api_key=openai_api_key,
                openai_base_url=openai_base_url,
                openai_timeout_ms=openai_timeout_ms,
                secrets=app.secrets,
            )
            app.runtime.capabilities = app.capabilities
            app.runtime.context_window_manager = app.context_window_manager
            app.runtime.usage_tracker = app.usage
        return app

    def register_agent(self, agent: AgentDefinition) -> None:
        self.store.save_agent(agent)

    def create_agent(
        self,
        agent_id: str,
        goal: str,
        model: str,
        tenant_id: str = "default",
        agent_tier: AgentTier = AgentTier.BASIC_AGENT,
        learning_mode: LearningMode = LearningMode.COLLECT_ONLY,
        output_mode: str = "text",
        output_schema: dict | None = None,
    ) -> AgentDefinition:
        if not model.strip():
            raise ValueError("model is required.")
        enforced_learning_mode = learning_mode
        if agent_tier == AgentTier.BASIC_AGENT:
            enforced_learning_mode = LearningMode.OFF
        agent = AgentDefinition(
            id=agent_id,
            goal=goal,
            model=model,
            tenant_id=tenant_id,
            agent_tier=agent_tier,
            learning_mode=enforced_learning_mode,
            output_mode=output_mode,
            output_schema=output_schema,
        )
        self.register_agent(agent)
        return agent

    def get_agent(self, agent_id: str) -> AgentDefinition:
        return self.store.load_agent(agent_id)

    def list_agents(self) -> list[AgentDefinition]:
        return self.store.list_agents()

    def _handle_session_accept(self, session_id: str, agent_id: str) -> None:
        try:
            agent = self.store.load_agent(agent_id)
        except Exception:
            return
        if agent.agent_tier != AgentTier.SELF_LEARNING_AGENT:
            return
        try:
            self.flame.ingest_accepted_session(agent_id=agent_id, session_id=session_id)
        except Exception:
            self.metrics.inc("flame_ingest_failed")


class _StorageOps:
    def __init__(self, agent_os: AgentOS) -> None:
        self.agent_os = agent_os

    def verify_shadow(self, agent_id: str | None = None) -> dict:
        store = self.agent_os.store
        if not isinstance(store, DualWriteStore):
            return {"mode": "non_dual_write", "matches": True}
        primary_agents = store.primary.list_agents()
        secondary_agents = store.secondary.list_agents()
        if agent_id is not None:
            primary_agents = [a for a in primary_agents if a.id == agent_id]
            secondary_agents = [a for a in secondary_agents if a.id == agent_id]
        p_ids = sorted([a.id for a in primary_agents])
        s_ids = sorted([a.id for a in secondary_agents])
        return {
            "mode": "dual_write",
            "primary_count": len(p_ids),
            "secondary_count": len(s_ids),
            "matches": p_ids == s_ids,
            "primary_ids": p_ids,
            "secondary_ids": s_ids,
        }
