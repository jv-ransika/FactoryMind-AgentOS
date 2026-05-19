from __future__ import annotations

import json

import httpx

from agent_os import AgentOS, AgentTier
from agent_os.capabilities import ModelCapabilityRegistry
from agent_os.embeddings.openai import OpenAIEmbeddingProvider
from agent_os.flame import FlameMemorySystem
from agent_os.monitoring import UsageTracker
from agent_os.protocol import RuntimeConfig
from agent_os.runtime import OpenAIRuntimeAdapter
from agent_os.storage.local import LocalStore


def test_embedding_usage_bucket_is_recorded(monkeypatch, tmp_path) -> None:
    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": [{"embedding": [0.1, 0.2, 0.3]}],
                "usage": {"prompt_tokens": 12, "total_tokens": 12},
            }

    monkeypatch.setattr(httpx.Client, "post", lambda self, url, headers, json: _Resp())

    root = tmp_path / ".agent-os"
    store = LocalStore(root)
    store.init()
    app = AgentOS.load(root=root)
    app.create_agent("a1", goal="g1", model="gpt-4.1-mini", agent_tier=AgentTier.SELF_LEARNING_AGENT)
    provider = OpenAIEmbeddingProvider(api_key="k")
    mgr = FlameMemorySystem(
        store=store,
        embedding_provider=provider,
        usage_tracker=UsageTracker(root=root),
        capabilities=ModelCapabilityRegistry(root=root),
    )
    mgr.create(agent_id="a1", content="Prioritize delivery risk first.")

    usage_rows = UsageTracker(root=root).list_usage("a1")
    assert any(row.operation_bucket == "embedding" for row in usage_rows)


def test_flame_extraction_and_reflection_buckets_are_recorded(monkeypatch, tmp_path) -> None:
    class _Resp:
        def __init__(self, payload: dict):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def _fake_post(self, url, headers, json):  # noqa: ANN001
        user_payload = json["input"][1]["content"]
        parsed = {}
        try:
            parsed = __import__("json").loads(user_payload)
        except Exception:
            parsed = {}
        if "schema" in parsed and "items" in parsed.get("schema", {}):
            output = {
                "items": [
                    {
                        "type": "learning_point",
                        "content": "Prefer concise, risk-first bullets.",
                        "human_feedback_weight": 0.9,
                        "source_feedback_snippets": ["Use bullets and prioritize risk."],
                    }
                ]
            }
        else:
            output = {
                "reflections": [
                    {
                        "content": "Use concise, risk-first bullet summaries when user gives correction.",
                        "confidence": 0.82,
                        "human_feedback_weighted": True,
                    }
                ]
            }
        return _Resp(
            {
                "output_text": json_module.dumps(output),
                "usage": {"input_tokens": 22, "output_tokens": 7, "total_tokens": 29},
            }
        )

    json_module = json
    monkeypatch.setattr(httpx.Client, "post", _fake_post)

    root = tmp_path / ".agent-os"
    app = AgentOS.load(root=root)
    app.create_agent("a1", goal="g1", model="gpt-4.1-mini", agent_tier=AgentTier.SELF_LEARNING_AGENT)
    ses = app.sessions.init("a1", "Write a proposal summary")
    app.sessions.run(ses.session_id)
    app.sessions.feedback(ses.session_id, "Use bullets and prioritize risk.")
    app.sessions.accept(ses.session_id)
    app.flame.runtime = OpenAIRuntimeAdapter(config=RuntimeConfig(mode="openai", openai_api_key="k"))
    app.flame.ingest_accepted_session(agent_id="a1", session_id=ses.session_id)
    app.flame.trigger(agent_id="a1", force=True)

    usage_rows = app.usage.list_usage("a1")
    buckets = {row.operation_bucket for row in usage_rows}
    assert "flame_extraction" in buckets
    assert "flame_reflection" in buckets
