from __future__ import annotations

from agent_os import (
    AgentOS,
    MemoryEvent,
    MemoryRetrievalRequest,
    MemoryRetrievalResult,
    MemoryWriteRequest,
    MemoryWriteResult,
)
from agent_os.protocol import AgentTier, EventType


def test_flame_memory_system_is_primary_agentos_memory_api(tmp_path) -> None:
    app = AgentOS.load(root=tmp_path / ".agent-os")
    app.create_agent("a1", goal="g1", model="gpt-4.1-mini")

    memory = app.flame.memory.create(agent_id="a1", content="Prefer concise delivery-risk summaries.")

    assert not hasattr(app, "memory")
    assert app.flame.memory.list("a1") == [memory]
    assert app.flame.memory.retrieve("a1", "delivery risk") == []


def test_flame_memory_port_models_write_and_retrieve(tmp_path) -> None:
    app = AgentOS.load(root=tmp_path / ".agent-os")
    app.create_agent("a1", goal="g1", model="gpt-4.1-mini")

    write_result = app.flame.memory.write(
        MemoryWriteRequest(
            agent_id="a1",
            content="Prefer project summaries with explicit assumptions.",
            tags=["assumptions"],
        )
    )
    retrieve_result = app.flame.memory.retrieve_for_context(
        MemoryRetrievalRequest(agent_id="a1", query="project assumptions", limit=3)
    )
    event_result = app.flame.memory.ingest_event(
        MemoryEvent(
            event_type="external_note",
            agent_id="a1",
            payload={"content": "External adapter can submit events later."},
        )
    )

    assert isinstance(write_result, MemoryWriteResult)
    assert write_result.memory.content == "Prefer project summaries with explicit assumptions."
    assert isinstance(retrieve_result, MemoryRetrievalResult)
    assert retrieve_result.memories == []
    assert event_result["accepted"] is True


def test_context_assembler_uses_flame_memory_system(tmp_path) -> None:
    app = AgentOS.load(root=tmp_path / ".agent-os")
    app.create_agent("a1", goal="g1", model="gpt-4.1-mini", agent_tier=AgentTier.SELF_LEARNING_AGENT)
    calls: list[tuple[str, str]] = []

    def fake_retrieve(agent_id: str, query: str, limit: int = 5):
        calls.append((agent_id, query))
        return []

    app.flame.memory.retrieve = fake_retrieve  # type: ignore[method-assign]
    packet = app.context.build(agent_id="a1", active_input="Find low-risk project.")

    assert packet.selected_memories == []
    assert calls == [("a1", "Find low-risk project.")]


def test_flame_reflection_writes_through_flame_memory_system(tmp_path) -> None:
    app = AgentOS.load(root=tmp_path / ".agent-os")
    app.create_agent("a1", goal="g1", model="gpt-4.1-mini", agent_tier=AgentTier.SELF_LEARNING_AGENT)
    session = app.sessions.init("a1", "Draft a proposal")
    app.sessions.run(session.session_id)
    app.sessions.feedback(session.session_id, "Use direct language.")
    app.sessions.accept(session.session_id)

    writes: list[str] = []
    original_create = app.flame.memory.create

    def tracked_create(*args, **kwargs):
        writes.append(str(kwargs.get("content", "")))
        return original_create(*args, **kwargs)

    app.flame.memory.create = tracked_create  # type: ignore[method-assign]
    app.flame.trigger(agent_id="a1", force=True)

    memories = app.flame.memory.list("a1")
    assert writes
    assert any(memory.metadata.get("created_by") == "flame_reflection" for memory in memories)


def test_acceptance_still_ingests_flame_pool_items(tmp_path) -> None:
    app = AgentOS.load(root=tmp_path / ".agent-os")
    app.create_agent("a1", goal="g1", model="gpt-4.1-mini", agent_tier=AgentTier.SELF_LEARNING_AGENT)
    session = app.sessions.init("a1", "Draft a proposal")
    app.sessions.run(session.session_id)
    app.sessions.feedback(session.session_id, "Use direct language.")
    event = app.sessions.accept(session.session_id)

    assert event.type == EventType.ACCEPTANCE
    assert app.flame.list_pool("a1")
