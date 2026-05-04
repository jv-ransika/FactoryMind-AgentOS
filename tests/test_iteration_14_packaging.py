from __future__ import annotations

import os
import subprocess
from pathlib import Path
import tomllib

import pytest


def test_build_wheel_and_sdist() -> None:
    repo = Path(__file__).resolve().parents[1]
    subprocess.run(["python", "scripts/release/build_dist.py"], cwd=repo, check=True)
    dist = repo / "dist"
    pyproject = tomllib.loads((repo / "pyproject.toml").read_text(encoding="utf-8"))
    version = str(pyproject["project"]["version"]).replace("-beta.", "b")
    assert any(p.suffix == ".whl" for p in dist.glob("*"))
    assert any(p.suffixes[-2:] == [".tar", ".gz"] for p in dist.glob("*"))
    assert all(version in p.name for p in dist.glob("*"))


@pytest.mark.skipif(os.getenv("AGENT_OS_RUN_PACKAGING_TESTS") != "1", reason="packaging smoke is opt-in")
def test_verify_install_script() -> None:
    repo = Path(__file__).resolve().parents[1]
    subprocess.run(["python", "scripts/release/build_dist.py"], cwd=repo, check=True)
    subprocess.run(["python", "scripts/release/verify_install.py"], cwd=repo, check=True)
