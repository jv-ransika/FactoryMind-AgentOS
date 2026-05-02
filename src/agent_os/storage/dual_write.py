from __future__ import annotations

from typing import Any

from agent_os.storage.contracts import DomainStore


class DualWriteStore:
    def __init__(self, primary: DomainStore, secondary: DomainStore, read_from_primary: bool = True) -> None:
        self.primary = primary
        self.secondary = secondary
        self.read_from_primary = read_from_primary
        self.root = getattr(primary, "root", None)

    def init(self) -> None:
        self.primary.init()
        self.secondary.init()

    def __getattr__(self, name: str) -> Any:
        if name.startswith("save_") or name.startswith("create_") or name.startswith("append_") or name.startswith("bind_"):
            p = getattr(self.primary, name)
            s = getattr(self.secondary, name)

            def wrapped(*args, **kwargs):
                p(*args, **kwargs)
                s(*args, **kwargs)

            return wrapped
        target = self.primary if self.read_from_primary else self.secondary
        return getattr(target, name)
