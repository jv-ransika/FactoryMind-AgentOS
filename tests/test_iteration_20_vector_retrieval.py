from __future__ import annotations

import httpx

from agent_os import AgentOS, AgentTier
from agent_os.embeddings.openai import OpenAIEmbeddingProvider
from agent_os.memory.manager import MemoryManager
from agent_os.protocol import ResourceStatus
from agent_os.storage.local import LocalStore


class _StubEmbeddingProvider:
    def __init__(self, vector: list[float] | None = None, fail: bool = False) -> None:
        self.vector = vector or [0.1, 0.2, 0.3]
        self.fail = fail

    def embed_text(self, text: str) -> list[float]:
        if self.fail:
            raise RuntimeError("embed_fail")
        _ = text
        return list(self.vector)


def test_openai_embedding_provider_maps_response(monkeypatch) -> None:
    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"embedding": [0.5, 0.25, -0.1]}]}

    monkeypatch.setattr(httpx.Client, "post", lambda self, url, headers, json: _Resp())
    provider = OpenAIEmbeddingProvider(api_key="k", model="text-embedding-3-small")
    vector = provider.embed_text("hello")
    assert vector == [0.5, 0.25, -0.1]


def test_memory_create_writes_vector_when_provider_available(tmp_path, monkeypatch) -> None:
    store = LocalStore(tmp_path / ".agent-os")
    store.init()
    store.save_agent(
        AgentOS.load(root=tmp_path / ".agent-os").create_agent(
            agent_id="a1",
            goal="g1",
            model="gpt-4.1-mini",
            agent_tier=AgentTier.SELF_LEARNING_AGENT,
        )
    )
    captured: dict[str, object] = {}

    def _save_memory_vector(agent_id: str, memory_id: str, embedding: list[float]) -> None:
        captured["agent_id"] = agent_id
        captured["memory_id"] = memory_id
        captured["embedding"] = embedding

    monkeypatch.setattr(store, "save_memory_vector", _save_memory_vector)
    manager = MemoryManager(store=store, embedding_provider=_StubEmbeddingProvider())
    memory = manager.create(agent_id="a1", content="Prefer low-risk delivery plans.")
    assert captured["agent_id"] == "a1"
    assert captured["memory_id"] == memory.memory_id
    assert captured["embedding"] == [0.1, 0.2, 0.3]


def test_vector_retrieve_returns_ranked_memories_from_store(tmp_path, monkeypatch) -> None:
    app = AgentOS.load(root=tmp_path / ".agent-os")
    app.create_agent(agent_id="a1", goal="g1", model="gpt-4.1-mini", agent_tier=AgentTier.SELF_LEARNING_AGENT)
    m1 = app.memory.create(agent_id="a1", content="Prefer delivery-risk-first ranking.")
    m2 = app.memory.create(agent_id="a1", content="Deprecated", status=ResourceStatus.DEPRECATED)

    manager = MemoryManager(store=app.store, embedding_provider=_StubEmbeddingProvider(), vector_top_k=5)
    monkeypatch.setattr(
        app.store,
        "query_memory_vectors",
        lambda agent_id, query_embedding, limit=5: [(m1.memory_id, 0.9), (m2.memory_id, 0.8)],
    )
    retrieved = manager.retrieve(agent_id="a1", query="rank low risk", limit=5)
    assert [item.item.memory_id for item in retrieved] == [m1.memory_id]
    assert retrieved[0].retrieval.score_source == "vector_cosine"


def test_vector_retrieve_unavailable_backend_returns_empty(tmp_path, monkeypatch) -> None:
    app = AgentOS.load(root=tmp_path / ".agent-os")
    app.create_agent(agent_id="a1", goal="g1", model="gpt-4.1-mini", agent_tier=AgentTier.SELF_LEARNING_AGENT)
    app.memory.create(agent_id="a1", content="Prefer low-risk delivery plans.")

    manager = MemoryManager(store=app.store, embedding_provider=_StubEmbeddingProvider())
    monkeypatch.setattr(
        app.store,
        "query_memory_vectors",
        lambda agent_id, query_embedding, limit=5: (_ for _ in ()).throw(RuntimeError("backend_down")),
    )
    assert manager.retrieve(agent_id="a1", query="low risk", limit=5) == []
