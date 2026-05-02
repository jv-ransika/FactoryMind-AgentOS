from __future__ import annotations

import subprocess
from pathlib import Path


class MigrationManager:
    def __init__(self, root: Path | str = ".") -> None:
        self.root = Path(root)

    def _run(self, *args: str) -> str:
        cmd = ["alembic", *args]
        proc = subprocess.run(cmd, cwd=self.root, capture_output=True, text=True, check=True)
        return (proc.stdout or "").strip()

    def upgrade(self, revision: str = "head") -> str:
        self._run("upgrade", revision)
        return f"upgraded:{revision}"

    def downgrade(self, revision: str) -> str:
        self._run("downgrade", revision)
        return f"downgraded:{revision}"

    def status(self) -> str:
        return self._run("current")
