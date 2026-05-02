from __future__ import annotations

import pytest

from agent_os import AgentOS, StorageMode
from agent_os.storage import RedisIdempotencyStore, RedisQueueStore


def test_local_mode_still_operates(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os", storage_mode=StorageMode.LOCAL)
    agent_os.create_agent(agent_id="a1", goal="g1", model="gpt-4.1-mini")
    assert [a.id for a in agent_os.list_agents()] == ["a1"]


def test_dual_write_shadow_and_verify(tmp_path, monkeypatch) -> None:
    if RedisIdempotencyStore is None or RedisQueueStore is None:
        pytest.skip("redis backend optional deps are not installed")
    fakeredis = pytest.importorskip("fakeredis")
    redis = pytest.importorskip("redis")
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis.Redis, "from_url", staticmethod(lambda *args, **kwargs: fake))
    root = tmp_path / ".agent-os"
    sqlite_dsn = f"sqlite:///{tmp_path / 'agent_os.db'}"
    agent_os = AgentOS.load(
        root=root,
        storage_mode=StorageMode.DUAL_WRITE,
        postgres_dsn=sqlite_dsn,
        redis_url="redis://unused",
    )
    agent_os.create_agent(agent_id="a2", goal="g2", model="gpt-4.1-mini")
    parity = agent_os.storage.verify_shadow()
    assert parity["mode"] == "dual_write"
    assert parity["matches"] is True
    assert "a2" in parity["primary_ids"]


def test_redis_queue_and_idempotency_backends(monkeypatch) -> None:
    if RedisIdempotencyStore is None or RedisQueueStore is None:
        pytest.skip("redis backend optional deps are not installed")
    fakeredis = pytest.importorskip("fakeredis")
    redis = pytest.importorskip("redis")
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis.Redis, "from_url", staticmethod(lambda *args, **kwargs: fake))
    idem = RedisIdempotencyStore(redis_url="redis://unused", ttl_seconds=60)
    queue = RedisQueueStore(redis_url="redis://unused")

    idem.record("k1", {"operation_id": "op1"})
    assert idem.get("k1") == {"operation_id": "op1"}

    queue.enqueue({"job_id": "j1", "type": "x"})
    job = queue.next_pending()
    assert job is not None
    queue.mark_running(job)
    queue.mark_completed(job)
    assert queue.depth() == 0

