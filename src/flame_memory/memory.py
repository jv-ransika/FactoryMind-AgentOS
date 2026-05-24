from __future__ import annotations

from typing import Any

from flame_memory.models import (
    MemoryEvent,
    MemoryItem,
    MemoryRetrievalRequest,
    MemoryRetrievalResult,
    MemoryScope,
    MemoryType,
    MemoryWriteRequest,
    MemoryWriteResult,
    ResourceStatus,
    RetrievalResult,
    RetrievedMemory,
)
from flame_memory.ports import EmbeddingProvider, MetricsSink, UsageRecorder
from flame_memory.storage import FlameStore


class FlameMemorySystem:
    def __init__(
        self,
        store: FlameStore,
        embedding_provider: EmbeddingProvider | None = None,
        vector_top_k: int = 5,
        metrics: MetricsSink | None = None,
        usage_recorder: UsageRecorder | None = None,
    ) -> None:
        self.store = store
        self.embedding_provider = embedding_provider
        self.vector_top_k = max(1, int(vector_top_k))
        self.metrics = metrics
        self.usage_recorder = usage_recorder

    def create(
        self,
        agent_id: str,
        content: str,
        summary: str = "",
        scope: MemoryScope = MemoryScope.AGENT,
        memory_type: MemoryType = MemoryType.SEMANTIC,
        tags: list[str] | None = None,
        metadata: dict | None = None,
        confidence: float = 0.5,
        status: ResourceStatus = ResourceStatus.ACTIVE,
    ) -> MemoryItem:
        agent = self.store.load_agent(agent_id)
        memory = MemoryItem(
            agent_id=agent_id,
            tenant_id=agent.tenant_id,
            content=content,
            summary=summary,
            scope=scope,
            memory_type=memory_type,
            tags=tags or [],
            metadata=metadata or {},
            confidence=confidence,
            status=status,
        )
        self.store.save_memory(memory)
        self._save_embedding(memory)
        return memory

    def list(self, agent_id: str) -> list[MemoryItem]:
        self.store.load_agent(agent_id)
        return self.store.list_memories(agent_id)

    def retrieve(self, agent_id: str, query: str, limit: int = 5) -> list[RetrievedMemory]:
        if not query.strip() or self.embedding_provider is None:
            return []
        top_k = max(1, min(int(limit), self.vector_top_k))
        try:
            query_vector = self.embedding_provider.embed_text(query)
            self._record_embedding_usage(agent_id=agent_id, session_id=None)
            if not query_vector:
                return []
            rows = self.store.query_memory_vectors(agent_id=agent_id, query_embedding=query_vector, limit=top_k)
        except Exception:
            self.metrics and self.metrics.inc("memory_vector_retrieval_unavailable")
            return []

        results: list[RetrievedMemory] = []
        for memory_id, score in rows:
            try:
                memory = self.store.load_memory(agent_id=agent_id, memory_id=memory_id)
            except Exception:
                continue
            if memory.status != ResourceStatus.ACTIVE:
                continue
            results.append(
                RetrievedMemory(
                    item=memory,
                    retrieval=RetrievalResult(
                        query=query,
                        matched_terms=[],
                        score=max(0.0, min(1.0, float(score))),
                        score_source="vector_cosine",
                    ),
                )
            )

        return results[:top_k]

    def write(self, request: MemoryWriteRequest) -> MemoryWriteResult:
        return MemoryWriteResult(
            memory=self.create(
                agent_id=request.agent_id,
                content=request.content,
                summary=request.summary,
                scope=request.scope,
                memory_type=request.memory_type,
                tags=request.tags,
                metadata=request.metadata,
                confidence=request.confidence,
                status=request.status,
            )
        )

    def retrieve_for_context(self, request: MemoryRetrievalRequest) -> MemoryRetrievalResult:
        return MemoryRetrievalResult(memories=self.retrieve(agent_id=request.agent_id, query=request.query, limit=request.limit))

    def ingest_event(self, event: MemoryEvent) -> dict[str, Any]:
        self.metrics and self.metrics.inc("flame_memory_events_ingested")
        return {
            "accepted": True,
            "event_type": event.event_type,
            "agent_id": event.agent_id,
            "session_id": event.session_id,
        }

    def _save_embedding(self, memory: MemoryItem) -> None:
        if self.embedding_provider is None:
            return
        text = memory.summary.strip() or memory.content
        try:
            vector = self.embedding_provider.embed_text(text)
            self._record_embedding_usage(agent_id=memory.agent_id, session_id=None)
            if not vector:
                return
            self.store.save_memory_vector(
                agent_id=memory.agent_id,
                memory_id=memory.memory_id,
                embedding=vector,
            )
        except Exception:
            self.metrics and self.metrics.inc("memory_vector_embedding_failed")

    def _record_embedding_usage(self, agent_id: str, session_id: str | None) -> None:
        if self.usage_recorder is None:
            return
        try:
            agent = self.store.load_agent(agent_id)
        except Exception:
            return
        provider = self.embedding_provider
        usage = getattr(provider, "last_usage_tokens", {}) if provider is not None else {}
        request_bytes = int(getattr(provider, "last_request_bytes", 0) or 0)
        latency_ms = int(getattr(provider, "last_latency_ms", 0) or 0)
        model = str(getattr(provider, "model", "") or "") if provider is not None else None
        self.usage_recorder.record_usage(
            agent=agent,
            session_id=session_id,
            operation_bucket="embedding",
            model=model,
            request_bytes=request_bytes,
            latency_ms=latency_ms,
            input_tokens=int(usage.get("input_tokens", 0) or 0),
            output_tokens=int(usage.get("output_tokens", 0) or 0),
            reasoning_tokens=int(usage.get("reasoning_tokens", 0) or 0),
            total_tokens=int(usage.get("total_tokens", 0) or 0),
        )
