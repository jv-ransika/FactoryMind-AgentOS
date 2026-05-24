from __future__ import annotations

import importlib
import sys

from agent_os import AgentOS


def test_flame_memory_import_does_not_import_agent_os() -> None:
    for name in list(sys.modules):
        if name == "flame_memory" or name.startswith("flame_memory."):
            sys.modules.pop(name)
        if name == "agent_os" or name.startswith("agent_os."):
            sys.modules.pop(name)

    flame_memory = importlib.import_module("flame_memory")

    assert flame_memory.FlameMemorySystem is not None
    assert flame_memory.FlameManager is not None
    assert "agent_os" not in sys.modules
    assert not any(name.startswith("agent_os.") for name in sys.modules)


def test_agentos_constructs_flame_through_adapter_boundary(tmp_path) -> None:
    app = AgentOS.load(root=tmp_path, runtime_mode="local")

    assert app.flame.__class__.__module__.startswith("flame_memory")
    assert app.flame.memory.__class__.__module__.startswith("flame_memory")
    assert app.flame.store.__class__.__name__ == "AgentOSFlameStoreAdapter"
    assert app.context.memory is app.flame.memory


def test_agent_os_flame_imports_are_compatibility_shims() -> None:
    from agent_os.flame import FlameManager as ShimFlameManager
    from agent_os.flame import FlameMemorySystem as ShimFlameMemorySystem
    from flame_memory import FlameManager, FlameMemorySystem

    assert ShimFlameManager is FlameManager
    assert ShimFlameMemorySystem is FlameMemorySystem
