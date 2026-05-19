from __future__ import annotations

import json
import httpx
from typer.testing import CliRunner

from agent_os import AgentOS, AgentTier, FlameRunState
from agent_os.storage import StorageMode
from agent_os.storage import postgres as pg_storage
from agent_os.cli.app import app
from agent_os.flame.manager import (
    FLAME_EXTRACTION_PROMPT_VERSION,
    FLAME_REFLECTION_PROMPT_VERSION,
    FLAME_REFLECTION_CONTENT_MAX_CHARS,
    FLAME_TEMP_CONTENT_MAX_CHARS,
)


def _make_accepted_session(agent_os: AgentOS, agent_id: str, input_text: str, feedback: str | None = None) -> str:
    session = agent_os.sessions.init(agent_id=agent_id, input=input_text)
    agent_os.sessions.run(session.session_id)
    if feedback:
        agent_os.sessions.feedback(session.session_id, feedback)
    agent_os.sessions.accept(session.session_id)
    return session.session_id


def test_learning_run_dispatches_to_flame_and_records_run(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="proposal_writer", goal="Write proposals.", model="gpt-4.1-mini", agent_tier=AgentTier.SELF_LEARNING_AGENT)
    _make_accepted_session(
        agent_os,
        "proposal_writer",
        "Write a proposal opening for healthcare AI.",
        "Use less generic language and include delivery risk.",
    )

    run = agent_os.learning.run(agent_id="proposal_writer", window_size=20)
    runs = agent_os.flame.list_runs("proposal_writer")
    memories = agent_os.flame.memory.list("proposal_writer")

    assert run.experience_count >= 1
    assert run.candidate_ids == []
    assert runs
    assert runs[0].state in {FlameRunState.SUCCESS, FlameRunState.SKIPPED}
    assert any(item.metadata.get("created_by") == "flame_reflection" for item in memories)


def test_learning_candidate_apis_removed(tmp_path) -> None:
    agent_os = AgentOS.load(root=tmp_path / ".agent-os")
    agent_os.create_agent(agent_id="project_selector", goal="Select projects.", model="gpt-4.1-mini", agent_tier=AgentTier.SELF_LEARNING_AGENT)

    for fn, args in [
        (agent_os.learning.list_candidates, ("project_selector",)),
        (agent_os.learning.validate, ("cand_x",)),
        (agent_os.learning.evaluate, ("cand_x",)),
        (agent_os.learning.promote, ("cand_x",)),
        (agent_os.learning.reject, ("cand_x", "reason")),
        (agent_os.learning.rollback, ("cand_x", "reason")),
    ]:
        try:
            fn(*args)
            assert False, "Expected candidate-era API removal error"
        except ValueError as exc:
            assert "learning_candidates_removed_in_v1_2_0" in str(exc)


def test_cli_learning_flow_with_flame_commands(tmp_path) -> None:
    runner = CliRunner()
    root = str(tmp_path / ".agent-os")
    assert runner.invoke(app, ["init", "--root", root]).exit_code == 0
    assert runner.invoke(
        app,
        [
            "create",
            "agent",
            "project_selector",
            "--goal",
            "Select projects.",
            "--model",
            "gpt-4.1-mini",
            "--agent-tier",
            "self_learning_agent",
            "--root",
            root,
        ],
    ).exit_code == 0
    run = runner.invoke(
        app,
        ["run", "project_selector", "--input", "Find low risk delivery projects.", "--root", root],
    )
    assert run.exit_code == 0
    session_id = run.output.split('"session_id": "')[1].split('"')[0]
    assert runner.invoke(
        app,
        ["feedback", session_id, "--text", "Prioritize delivery risk.", "--root", root],
    ).exit_code == 0
    assert runner.invoke(app, ["accept", session_id, "--root", root]).exit_code == 0

    learn_run = runner.invoke(app, ["learn", "run", "project_selector", "--root", root])
    assert learn_run.exit_code == 0
    assert '"candidate_ids": []' in learn_run.output

    runs = runner.invoke(app, ["flame", "runs", "project_selector", "--root", root])
    assert runs.exit_code == 0
    assert "run_id" in runs.output

    removed = runner.invoke(app, ["learn", "list-candidates", "project_selector", "--root", root])
    assert removed.exit_code != 0


def test_flame_openai_extraction_learning_point_valid(monkeypatch, tmp_path) -> None:
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": '{"items":[{"type":"learning_point","content":"User prefers explicit assumptions before recommendations.","human_feedback_weight":0.9,"source_feedback_snippets":["List assumptions explicitly and add 3 clarifying questions before final recommendation."]}]}',
                "usage": {"input_tokens": 30, "output_tokens": 20, "reasoning_tokens": 0, "total_tokens": 50},
            }

    def fake_post(self, url, headers, json):
        return FakeResponse()

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    agent_os = AgentOS.load(root=tmp_path / ".agent-os", runtime_mode="openai", openai_api_key="k")
    agent_os.create_agent(agent_id="proposal_writer", goal="Write proposals.", model="gpt-4.1-mini", agent_tier=AgentTier.SELF_LEARNING_AGENT)
    session_id = _make_accepted_session(agent_os, "proposal_writer", "Draft proposal", "List assumptions explicitly.")
    pool = agent_os.flame.list_pool("proposal_writer")
    assert pool
    assert any(item.extracted_type.value == "learning_point" for item in pool)
    assert any(item.human_feedback_weight > 0 for item in pool)
    assert session_id in {item.session_id for item in pool}


def test_flame_openai_extraction_invalid_learning_point_strict_drop(monkeypatch, tmp_path) -> None:
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": '{"items":[{"type":"learning_point","content":"User prefers concise outputs.","human_feedback_weight":0.0,"source_feedback_snippets":["Prefer concise outputs."]}]}',
                "usage": {"input_tokens": 25, "output_tokens": 20, "reasoning_tokens": 0, "total_tokens": 45},
            }

    def fake_post(self, url, headers, json):
        return FakeResponse()

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    agent_os = AgentOS.load(root=tmp_path / ".agent-os", runtime_mode="openai", openai_api_key="k")
    agent_os.create_agent(agent_id="proposal_writer", goal="Write proposals.", model="gpt-4.1-mini", agent_tier=AgentTier.SELF_LEARNING_AGENT)
    _make_accepted_session(agent_os, "proposal_writer", "Draft proposal", "Prefer concise outputs.")
    pool = agent_os.flame.list_pool("proposal_writer")
    assert pool == []


def test_flame_openai_extraction_experience_normalized(monkeypatch, tmp_path) -> None:
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": '{"items":[{"type":"learning_point","content":"Accepted responses should remain direct and structured.","human_feedback_weight":0.7,"source_feedback_snippets":["unexpected"]}]}',
                "usage": {"input_tokens": 22, "output_tokens": 22, "reasoning_tokens": 0, "total_tokens": 44},
            }

    def fake_post(self, url, headers, json):
        return FakeResponse()

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    agent_os = AgentOS.load(root=tmp_path / ".agent-os", runtime_mode="openai", openai_api_key="k")
    agent_os.create_agent(agent_id="proposal_writer", goal="Write proposals.", model="gpt-4.1-mini", agent_tier=AgentTier.SELF_LEARNING_AGENT)
    _make_accepted_session(agent_os, "proposal_writer", "Draft proposal", feedback=None)
    pool = agent_os.flame.list_pool("proposal_writer")
    assert pool
    assert all(item.extracted_type.value == "experience" for item in pool)
    assert all(item.human_feedback_weight == 0.0 for item in pool)
    assert all(item.source_feedback_snippets == [] for item in pool)


def test_flame_openai_extraction_malformed_json_strict_drop_and_run_metadata(monkeypatch, tmp_path) -> None:
    class MalformedResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": "not json",
                "usage": {"input_tokens": 20, "output_tokens": 10, "reasoning_tokens": 0, "total_tokens": 30},
            }

    class ValidResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": '{"items":[{"type":"learning_point","content":"User prefers explicit assumptions before recommendations.","human_feedback_weight":0.9,"source_feedback_snippets":["Be explicit about assumptions."]}]}',
                "usage": {"input_tokens": 22, "output_tokens": 18, "reasoning_tokens": 0, "total_tokens": 40},
            }

    calls = {"extraction_count": 0}

    def fake_post(self, url, headers, json):
        inputs = json.get("input", [])
        system_text = ""
        if isinstance(inputs, list) and inputs:
            first = inputs[0]
            if isinstance(first, dict):
                system_text = str(first.get("content", ""))
        if "behavioral signal extraction agent" in system_text:
            calls["extraction_count"] += 1
            if calls["extraction_count"] == 1:
                return MalformedResponse()
            return ValidResponse()
        return ValidResponse()

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    agent_os = AgentOS.load(root=tmp_path / ".agent-os", runtime_mode="openai", openai_api_key="k")
    agent_os.create_agent(agent_id="proposal_writer", goal="Write proposals.", model="gpt-4.1-mini", agent_tier=AgentTier.SELF_LEARNING_AGENT)
    _make_accepted_session(agent_os, "proposal_writer", "Draft proposal", "Be explicit about assumptions.")
    assert agent_os.flame.list_pool("proposal_writer") == []  # malformed response is strict-dropped
    _make_accepted_session(agent_os, "proposal_writer", "Draft proposal 2", "Be explicit about assumptions.")
    assert agent_os.flame.list_pool("proposal_writer")  # second response yields pending items

    run = agent_os.learning.run("proposal_writer")
    runs = agent_os.flame.list_runs("proposal_writer")
    assert run.experience_count >= 1
    assert runs
    assert runs[0].extraction_prompt_version == FLAME_EXTRACTION_PROMPT_VERSION
    assert runs[0].extraction_prompt_hash


def test_flame_reflection_openai_empty_reflections_valid_noop(monkeypatch, tmp_path) -> None:
    class ReflectionEmptyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": '{"reflections":[]}',
                "usage": {"input_tokens": 10, "output_tokens": 5, "reasoning_tokens": 0, "total_tokens": 15},
            }

    class ExtractionValidResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": '{"items":[{"type":"learning_point","content":"User prefers concise responses.","human_feedback_weight":0.8,"source_feedback_snippets":["Use concise language."]}]}',
                "usage": {"input_tokens": 12, "output_tokens": 6, "reasoning_tokens": 0, "total_tokens": 18},
            }

    def fake_post(self, url, headers, json):
        system_text = str((json.get("input") or [{}])[0].get("content", ""))
        if "behavioral signal extraction agent" in system_text:
            return ExtractionValidResponse()
        return ReflectionEmptyResponse()

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    agent_os = AgentOS.load(root=tmp_path / ".agent-os", runtime_mode="openai", openai_api_key="k")
    agent_os.create_agent(agent_id="proposal_writer", goal="Write proposals.", model="gpt-4.1-mini", agent_tier=AgentTier.SELF_LEARNING_AGENT)
    _make_accepted_session(agent_os, "proposal_writer", "Draft proposal", "Use concise language.")

    run = agent_os.learning.run("proposal_writer")
    runs = agent_os.flame.list_runs("proposal_writer")
    memories = agent_os.flame.memory.list("proposal_writer")
    assert run.experience_count >= 1
    assert runs
    assert runs[0].state == FlameRunState.SUCCESS
    assert len(memories) == 0


def test_flame_reflection_openai_discards_low_confidence_and_keeps_valid(monkeypatch, tmp_path) -> None:
    class ReflectionMixedResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": '{"reflections":[{"content":"Weak signal.","confidence":0.1,"human_feedback_weighted":false},{"content":"Use direct language for recommendations.","confidence":0.8,"human_feedback_weighted":true}]}',
                "usage": {"input_tokens": 12, "output_tokens": 10, "reasoning_tokens": 0, "total_tokens": 22},
            }

    class ExtractionValidResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": '{"items":[{"type":"learning_point","content":"User wants direct recommendations.","human_feedback_weight":0.85,"source_feedback_snippets":["Be direct and explicit."]}]}',
                "usage": {"input_tokens": 12, "output_tokens": 6, "reasoning_tokens": 0, "total_tokens": 18},
            }

    def fake_post(self, url, headers, json):
        system_text = str((json.get("input") or [{}])[0].get("content", ""))
        if "behavioral signal extraction agent" in system_text:
            return ExtractionValidResponse()
        return ReflectionMixedResponse()

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    agent_os = AgentOS.load(root=tmp_path / ".agent-os", runtime_mode="openai", openai_api_key="k")
    agent_os.create_agent(agent_id="proposal_writer", goal="Write proposals.", model="gpt-4.1-mini", agent_tier=AgentTier.SELF_LEARNING_AGENT)
    _make_accepted_session(agent_os, "proposal_writer", "Draft proposal", "Be direct and explicit.")

    agent_os.learning.run("proposal_writer")
    memories = agent_os.flame.memory.list("proposal_writer")
    assert len(memories) == 1
    assert memories[0].confidence >= 0.2


def test_flame_reflection_openai_all_low_confidence_yields_no_memory(monkeypatch, tmp_path) -> None:
    class ReflectionLowOnlyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": '{"reflections":[{"content":"Possible pattern.","confidence":0.15,"human_feedback_weighted":true}]}',
                "usage": {"input_tokens": 10, "output_tokens": 6, "reasoning_tokens": 0, "total_tokens": 16},
            }

    class ExtractionValidResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": '{"items":[{"type":"learning_point","content":"User expects explicit assumptions.","human_feedback_weight":0.8,"source_feedback_snippets":["Add assumptions."]}]}',
                "usage": {"input_tokens": 12, "output_tokens": 6, "reasoning_tokens": 0, "total_tokens": 18},
            }

    def fake_post(self, url, headers, json):
        system_text = str((json.get("input") or [{}])[0].get("content", ""))
        if "behavioral signal extraction agent" in system_text:
            return ExtractionValidResponse()
        return ReflectionLowOnlyResponse()

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    agent_os = AgentOS.load(root=tmp_path / ".agent-os", runtime_mode="openai", openai_api_key="k")
    agent_os.create_agent(agent_id="proposal_writer", goal="Write proposals.", model="gpt-4.1-mini", agent_tier=AgentTier.SELF_LEARNING_AGENT)
    _make_accepted_session(agent_os, "proposal_writer", "Draft proposal", "Add assumptions.")

    runs_before = len(agent_os.flame.list_runs("proposal_writer"))
    agent_os.learning.run("proposal_writer")
    runs = agent_os.flame.list_runs("proposal_writer")
    memories = agent_os.flame.memory.list("proposal_writer")
    assert len(runs) >= runs_before + 1
    assert runs[0].state == FlameRunState.SUCCESS
    assert len(memories) == 0


def test_flame_reflection_openai_malformed_item_type_uses_fallback(monkeypatch, tmp_path) -> None:
    class ReflectionMalformedResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": '{"reflections":[{"content":"Should fail strict parser.","confidence":0.8,"human_feedback_weighted":"true"}]}',
                "usage": {"input_tokens": 11, "output_tokens": 7, "reasoning_tokens": 0, "total_tokens": 18},
            }

    class ExtractionValidResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": '{"items":[{"type":"learning_point","content":"User prefers active voice.","human_feedback_weight":0.8,"source_feedback_snippets":["Use active voice."]}]}',
                "usage": {"input_tokens": 12, "output_tokens": 6, "reasoning_tokens": 0, "total_tokens": 18},
            }

    def fake_post(self, url, headers, json):
        system_text = str((json.get("input") or [{}])[0].get("content", ""))
        if "behavioral signal extraction agent" in system_text:
            return ExtractionValidResponse()
        return ReflectionMalformedResponse()

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    agent_os = AgentOS.load(root=tmp_path / ".agent-os", runtime_mode="openai", openai_api_key="k")
    agent_os.create_agent(agent_id="proposal_writer", goal="Write proposals.", model="gpt-4.1-mini", agent_tier=AgentTier.SELF_LEARNING_AGENT)
    _make_accepted_session(agent_os, "proposal_writer", "Draft proposal", "Use active voice.")

    agent_os.learning.run("proposal_writer")
    memories = agent_os.flame.memory.list("proposal_writer")
    assert memories  # fallback synthesizes reflection deterministically
    assert any(m.metadata.get("created_by") == "flame_reflection" for m in memories)


def test_flame_run_records_reflection_prompt_metadata(monkeypatch, tmp_path) -> None:
    class ReflectionValidResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": '{"reflections":[{"content":"Prioritize explicit assumptions in responses.","confidence":0.9,"human_feedback_weighted":true}]}',
                "usage": {"input_tokens": 14, "output_tokens": 8, "reasoning_tokens": 0, "total_tokens": 22},
            }

    class ExtractionValidResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": '{"items":[{"type":"learning_point","content":"User asks for assumptions.","human_feedback_weight":0.8,"source_feedback_snippets":["State assumptions."]}]}',
                "usage": {"input_tokens": 12, "output_tokens": 6, "reasoning_tokens": 0, "total_tokens": 18},
            }

    def fake_post(self, url, headers, json):
        system_text = str((json.get("input") or [{}])[0].get("content", ""))
        if "behavioral signal extraction agent" in system_text:
            return ExtractionValidResponse()
        return ReflectionValidResponse()

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    agent_os = AgentOS.load(root=tmp_path / ".agent-os", runtime_mode="openai", openai_api_key="k")
    agent_os.create_agent(agent_id="proposal_writer", goal="Write proposals.", model="gpt-4.1-mini", agent_tier=AgentTier.SELF_LEARNING_AGENT)
    _make_accepted_session(agent_os, "proposal_writer", "Draft proposal", "State assumptions.")

    agent_os.learning.run("proposal_writer")
    runs = agent_os.flame.list_runs("proposal_writer")
    assert runs
    assert runs[0].reflection_prompt_version == FLAME_REFLECTION_PROMPT_VERSION
    assert runs[0].reflection_prompt_hash


def test_flame_openai_extraction_parses_nested_output_text(monkeypatch, tmp_path) -> None:
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": '{"items":[{"type":"learning_point","content":"User prefers explicit assumptions.","human_feedback_weight":0.8,"source_feedback_snippets":["State assumptions."]}]}',
                            }
                        ],
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 10, "reasoning_tokens": 0, "total_tokens": 20},
            }

    def fake_post(self, url, headers, json):
        return FakeResponse()

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    agent_os = AgentOS.load(root=tmp_path / ".agent-os", runtime_mode="openai", openai_api_key="k")
    agent_os.create_agent(agent_id="proposal_writer", goal="Write proposals.", model="gpt-4.1-mini", agent_tier=AgentTier.SELF_LEARNING_AGENT)
    _make_accepted_session(agent_os, "proposal_writer", "Draft proposal", "State assumptions.")
    pool = agent_os.flame.list_pool("proposal_writer")
    assert pool


def test_flame_openai_extraction_provider_parse_metric(monkeypatch, tmp_path) -> None:
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"usage": {"input_tokens": 1, "output_tokens": 1, "reasoning_tokens": 0, "total_tokens": 2}}

    def fake_post(self, url, headers, json):
        return FakeResponse()

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    root = tmp_path / ".agent-os"
    agent_os = AgentOS.load(root=root, runtime_mode="openai", openai_api_key="k")
    agent_os.create_agent(agent_id="proposal_writer", goal="Write proposals.", model="gpt-4.1-mini", agent_tier=AgentTier.SELF_LEARNING_AGENT)
    _make_accepted_session(agent_os, "proposal_writer", "Draft proposal", "State assumptions.")
    metrics = json.loads((root / "metrics" / "metrics.json").read_text(encoding="utf-8"))
    assert metrics.get("flame_extraction_provider_parse_failed", 0) >= 1


def test_flame_openai_extraction_schema_validation_metric(monkeypatch, tmp_path) -> None:
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": '{"items":[{"type":"learning_point","content":"User prefers concise outputs.","human_feedback_weight":0.0,"source_feedback_snippets":["Prefer concise outputs."]}]}',
                "usage": {"input_tokens": 2, "output_tokens": 2, "reasoning_tokens": 0, "total_tokens": 4},
            }

    def fake_post(self, url, headers, json):
        return FakeResponse()

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    root = tmp_path / ".agent-os"
    agent_os = AgentOS.load(root=root, runtime_mode="openai", openai_api_key="k")
    agent_os.create_agent(agent_id="proposal_writer", goal="Write proposals.", model="gpt-4.1-mini", agent_tier=AgentTier.SELF_LEARNING_AGENT)
    _make_accepted_session(agent_os, "proposal_writer", "Draft proposal", "Prefer concise outputs.")
    metrics = json.loads((root / "metrics" / "metrics.json").read_text(encoding="utf-8"))
    assert metrics.get("flame_extraction_schema_validation_failed", 0) >= 1


def test_storage_mode_dual_write_rejected_for_vector_policy(tmp_path) -> None:
    try:
        AgentOS.load(root=tmp_path / ".agent-os", storage_mode=StorageMode.DUAL_WRITE)
        assert False, "Expected dual_write rejection"
    except RuntimeError as exc:
        assert "vector_backend_required" in str(exc)


def test_postgres_store_requires_pgvector_python(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(pg_storage, "Vector", None)
    store = pg_storage.PostgresDomainStore(dsn="postgresql://postgres@localhost/postgres", root=tmp_path / ".agent-os")
    try:
        store.init()
        assert False, "Expected pgvector python package requirement error"
    except RuntimeError as exc:
        assert "vector_backend_required" in str(exc)
        assert "pgvector_python_package_missing" in str(exc)


def test_flame_temp_content_truncates_and_metrics(monkeypatch, tmp_path) -> None:
    long_content = "x" * (FLAME_TEMP_CONTENT_MAX_CHARS + 50)

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": json.dumps(
                    {
                        "items": [
                            {
                                "type": "learning_point",
                                "content": long_content,
                                "human_feedback_weight": 0.9,
                                "source_feedback_snippets": ["Use concise language."],
                            }
                        ]
                    }
                ),
                "usage": {"input_tokens": 5, "output_tokens": 5, "reasoning_tokens": 0, "total_tokens": 10},
            }

    def fake_post(self, url, headers, json):
        return FakeResponse()

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    root = tmp_path / ".agent-os"
    agent_os = AgentOS.load(root=root, runtime_mode="openai", openai_api_key="k")
    agent_os.create_agent(agent_id="proposal_writer", goal="Write proposals.", model="gpt-4.1-mini", agent_tier=AgentTier.SELF_LEARNING_AGENT)
    _make_accepted_session(agent_os, "proposal_writer", "Draft proposal", "Use concise language.")
    pool = agent_os.flame.list_pool("proposal_writer")
    assert pool
    assert all(len(item.content) <= FLAME_TEMP_CONTENT_MAX_CHARS for item in pool)
    metrics = json.loads((root / "metrics" / "metrics.json").read_text(encoding="utf-8"))
    assert metrics.get("flame_temp_content_truncated", 0) >= 1


def test_flame_reflection_content_truncates_and_metrics(monkeypatch, tmp_path) -> None:
    exact_temp = "t" * FLAME_TEMP_CONTENT_MAX_CHARS
    long_reflection = "r" * (FLAME_REFLECTION_CONTENT_MAX_CHARS + 120)

    class ReflectionResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": json.dumps(
                    {
                        "reflections": [
                            {
                                "content": long_reflection,
                                "confidence": 0.9,
                                "human_feedback_weighted": True,
                            }
                        ]
                    }
                ),
                "usage": {"input_tokens": 5, "output_tokens": 5, "reasoning_tokens": 0, "total_tokens": 10},
            }

    class ExtractionResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": json.dumps(
                    {
                        "items": [
                            {
                                "type": "learning_point",
                                "content": exact_temp,
                                "human_feedback_weight": 0.9,
                                "source_feedback_snippets": ["Use concise language."],
                            }
                        ]
                    }
                ),
                "usage": {"input_tokens": 5, "output_tokens": 5, "reasoning_tokens": 0, "total_tokens": 10},
            }

    def fake_post(self, url, headers, json):
        system_text = str((json.get("input") or [{}])[0].get("content", ""))
        if "behavioral signal extraction agent" in system_text:
            return ExtractionResponse()
        return ReflectionResponse()

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    root = tmp_path / ".agent-os"
    agent_os = AgentOS.load(root=root, runtime_mode="openai", openai_api_key="k")
    agent_os.create_agent(agent_id="proposal_writer", goal="Write proposals.", model="gpt-4.1-mini", agent_tier=AgentTier.SELF_LEARNING_AGENT)
    _make_accepted_session(agent_os, "proposal_writer", "Draft proposal", "Use concise language.")
    pool_before = agent_os.flame.list_pool("proposal_writer")
    assert pool_before
    assert all(len(item.content) == FLAME_TEMP_CONTENT_MAX_CHARS for item in pool_before)
    agent_os.learning.run("proposal_writer")
    memories = agent_os.flame.memory.list("proposal_writer")
    assert memories
    assert all(len(memory.content) <= FLAME_REFLECTION_CONTENT_MAX_CHARS for memory in memories)
    metrics = json.loads((root / "metrics" / "metrics.json").read_text(encoding="utf-8"))
    assert metrics.get("flame_reflection_content_truncated", 0) >= 1
