from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_iteration_15_artifacts_exist() -> None:
    expected = [
        Path("docs/release-fast-track-no-pilot.md"),
        Path("docs/release-checklist-rc1.md"),
        Path("docs/stable-readiness-report-template.md"),
        Path("docs/templates/release-blocker-intake-template.md"),
        Path("docs/beta3-fix-log.md"),
        Path("scripts/release/run_fast_track_validation.py"),
    ]
    for item in expected:
        assert item.exists(), f"Missing iteration 15 artifact: {item}"


def test_fast_track_runner_outputs_contract(tmp_path: Path) -> None:
    out = tmp_path / "summary.json"
    proc = subprocess.run(
        ["python", "scripts/release/run_fast_track_validation.py", "--quick-contract", "--json-out", str(out)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )
    # Runner may fail in some environments; contract still must be emitted.
    assert proc.returncode in (0, 1)
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["release_track"] == "beta.3_to_rc.1_fast_track"
    assert "steps" in data
    assert isinstance(data["steps"], list)
    assert data["total_steps"] == len(data["steps"])
