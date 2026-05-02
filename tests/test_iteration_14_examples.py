from __future__ import annotations

import subprocess
from pathlib import Path


def _run_example(path: str) -> str:
    proc = subprocess.run(
        ["python", path],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout


def test_proposal_example_runs() -> None:
    out = _run_example("examples/proposal_agent_app.py")
    assert "proposal-agent" in out


def test_project_selection_example_runs() -> None:
    out = _run_example("examples/project_selection_agent_app.py")
    assert "project-selection-agent" in out


def test_keyword_extraction_example_runs() -> None:
    out = _run_example("examples/keyword_extraction_agent_app.py")
    assert "keyword-agent" in out
