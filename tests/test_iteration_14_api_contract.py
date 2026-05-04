from __future__ import annotations

from agent_os import (
    AgentStatus,
    AgentOS,
    AgentDefinition,
    AgentOutput,
    CostRecord,
    LearningCandidate,
    LearningRun,
    MemoryItem,
    ModelCapability,
    STABLE_CORE_API,
    Session,
    SessionEvent,
    ToolCallResult,
    ToolManifest,
    UsageRecord,
)


def test_stable_core_api_notice_exports() -> None:
    assert isinstance(STABLE_CORE_API, list)
    assert "AgentOS" in STABLE_CORE_API
    assert "AgentOS.load" in STABLE_CORE_API
    assert "AgentOS.sessions" in STABLE_CORE_API


def test_stable_core_symbols_importable() -> None:
    # Contract symbols expected for v1 stable consumer code.
    assert AgentOS is not None
    assert AgentDefinition is not None
    assert Session is not None
    assert SessionEvent is not None
    assert AgentOutput is not None
    assert MemoryItem is not None
    assert LearningRun is not None
    assert LearningCandidate is not None
    assert ToolManifest is not None
    assert ToolCallResult is not None
    assert ModelCapability is not None
    assert UsageRecord is not None
    assert CostRecord is not None
    assert AgentStatus is not None


def test_stable_core_agentos_managers(tmp_path) -> None:
    app = AgentOS.load(root=tmp_path / ".agent-os", runtime_mode="local")
    assert app.sessions is not None
    assert app.memory is not None
    assert app.learning is not None
    assert app.tools is not None
    assert app.capabilities is not None
    assert app.monitor is not None
