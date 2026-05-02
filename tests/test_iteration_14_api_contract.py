from __future__ import annotations

from agent_os import (
    AgentOS,
    AgentDefinition,
    AgentOutput,
    LearningCandidate,
    LearningRun,
    MemoryItem,
    STABLE_CORE_API,
    Session,
    SessionEvent,
    SkillDefinition,
    ToolCallResult,
    ToolManifest,
)


def test_stable_core_api_notice_exports() -> None:
    assert isinstance(STABLE_CORE_API, list)
    assert "AgentOS" in STABLE_CORE_API
    assert "AgentOS.load" in STABLE_CORE_API
    assert "AgentOS.sessions" in STABLE_CORE_API


def test_stable_core_symbols_importable() -> None:
    # Contract symbols expected for beta.2 consumer code.
    assert AgentOS is not None
    assert AgentDefinition is not None
    assert Session is not None
    assert SessionEvent is not None
    assert AgentOutput is not None
    assert MemoryItem is not None
    assert SkillDefinition is not None
    assert LearningRun is not None
    assert LearningCandidate is not None
    assert ToolManifest is not None
    assert ToolCallResult is not None


def test_stable_core_agentos_managers(tmp_path) -> None:
    app = AgentOS.load(root=tmp_path / ".agent-os", runtime_mode="local")
    assert app.sessions is not None
    assert app.memory is not None
    assert app.skills is not None
    assert app.learning is not None
    assert app.tools is not None
