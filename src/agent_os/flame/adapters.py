from __future__ import annotations

from typing import Any, Literal

from agent_os.monitoring import record_usage_and_cost
from agent_os.protocol import AgentTier
from agent_os.storage import DomainStore


class AgentOSFlameStoreAdapter:
    def __init__(self, store: DomainStore) -> None:
        self._store = store
        self.root = store.root

    def load_agent(self, agent_id: str) -> Any:
        return self._store.load_agent(agent_id)

    def list_self_learning_agents(self) -> list[Any]:
        return [agent for agent in self._store.list_agents() if agent.agent_tier == AgentTier.SELF_LEARNING_AGENT]

    def save_memory(self, memory: Any) -> None:
        self._store.save_memory(memory)

    def save_memory_vector(self, agent_id: str, memory_id: str, embedding: list[float]) -> None:
        self._store.save_memory_vector(agent_id=agent_id, memory_id=memory_id, embedding=embedding)

    def query_memory_vectors(self, agent_id: str, query_embedding: list[float], limit: int = 5) -> list[tuple[str, float]]:
        return self._store.query_memory_vectors(agent_id=agent_id, query_embedding=query_embedding, limit=limit)

    def load_memory(self, agent_id: str, memory_id: str) -> Any:
        return self._store.load_memory(agent_id=agent_id, memory_id=memory_id)

    def list_memories(self, agent_id: str) -> list[Any]:
        return self._store.list_memories(agent_id)

    def load_events(self, session_id: str) -> list[Any]:
        return self._store.load_events(session_id)

    def save_flame_pool_item(self, item: Any) -> None:
        self._store.save_flame_pool_item(item)

    def list_flame_pool_items(self, agent_id: str | None = None, state: Any | None = None) -> list[Any]:
        return self._store.list_flame_pool_items(agent_id=agent_id, state=state)

    def delete_flame_pool_items(self, pool_item_ids: list[str]) -> None:
        self._store.delete_flame_pool_items(pool_item_ids)

    def save_flame_run(self, run: Any) -> None:
        self._store.save_flame_run(run)

    def list_flame_runs(self, agent_id: str | None = None) -> list[Any]:
        return self._store.list_flame_runs(agent_id=agent_id)


class AgentOSFlameRuntimeAdapter:
    def __init__(self, runtime: Any) -> None:
        self._runtime = runtime

    @property
    def config(self) -> Any:
        return getattr(self._runtime, "config", None)


class AgentOSFlameUsageRecorder:
    def __init__(self, usage_tracker: Any, capabilities: Any | None) -> None:
        self.usage_tracker = usage_tracker
        self.capabilities = capabilities

    def record_usage(
        self,
        *,
        agent: Any,
        operation_bucket: Literal["embedding", "flame_extraction", "flame_reflection"],
        model: str | None,
        request_bytes: int,
        latency_ms: int,
        session_id: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        reasoning_tokens: int = 0,
        total_tokens: int = 0,
    ) -> None:
        record_usage_and_cost(
            usage_tracker=self.usage_tracker,
            capabilities=self.capabilities,
            agent=agent,
            session_id=session_id,
            operation_bucket=operation_bucket,
            model=model,
            request_bytes=request_bytes,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens,
            total_tokens=total_tokens,
        )
