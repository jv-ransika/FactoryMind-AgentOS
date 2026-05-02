from __future__ import annotations

from agent_os.protocol import (
    MemoryItem,
    MemoryScope,
    MemoryType,
    ResourceStatus,
    RetrievalResult,
    RetrievedMemory,
)
from agent_os.retrieval import keyword_overlap
from agent_os.storage import DomainStore


class MemoryManager:
    def __init__(self, store: DomainStore) -> None:
        self.store = store

    def create(
        self,
        agent_id: str,
        content: str,
        summary: str = "",
        scope: MemoryScope = MemoryScope.AGENT,
        memory_type: MemoryType = MemoryType.SEMANTIC,
        tags: list[str] | None = None,
        confidence: float = 0.5,
        status: ResourceStatus = ResourceStatus.ACTIVE,
    ) -> MemoryItem:
        self.store.load_agent(agent_id)
        agent = self.store.load_agent(agent_id)
        memory = MemoryItem(
            agent_id=agent_id,
            tenant_id=agent.tenant_id,
            content=content,
            summary=summary,
            scope=scope,
            memory_type=memory_type,
            tags=tags or [],
            confidence=confidence,
            status=status,
        )
        self.store.save_memory(memory)
        return memory

    def list(self, agent_id: str) -> list[MemoryItem]:
        self.store.load_agent(agent_id)
        return self.store.list_memories(agent_id)

    def retrieve(self, agent_id: str, query: str, limit: int = 5) -> list[RetrievedMemory]:
        memories = [
            memory
            for memory in self.list(agent_id)
            if memory.status == ResourceStatus.ACTIVE
        ]
        results: list[RetrievedMemory] = []
        for memory in memories:
            matched, score = keyword_overlap(
                query,
                [memory.content, memory.summary, " ".join(memory.tags)],
            )
            if score > 0:
                results.append(
                    RetrievedMemory(
                        item=memory,
                        retrieval=RetrievalResult(query=query, matched_terms=matched, score=score),
                    )
                )

        return sorted(
            results,
            key=lambda result: (result.retrieval.score, result.item.confidence, result.item.updated_at),
            reverse=True,
        )[:limit]
