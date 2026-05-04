from __future__ import annotations

import importlib.util
from pathlib import Path

_SMOKE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "beta_smoke.py"
_SMOKE_SPEC = importlib.util.spec_from_file_location("beta_smoke", _SMOKE_PATH)
if _SMOKE_SPEC is None or _SMOKE_SPEC.loader is None:
    raise RuntimeError(f"Unable to load smoke script: {_SMOKE_PATH}")
_SMOKE_MODULE = importlib.util.module_from_spec(_SMOKE_SPEC)
_SMOKE_SPEC.loader.exec_module(_SMOKE_MODULE)
run_smoke = _SMOKE_MODULE.run_smoke


def test_beta_artifacts_exist() -> None:
    expected = [
        Path("CHANGELOG.md"),
        Path("Dockerfile"),
        Path("docker-compose.beta.yml"),
        Path(".env.example"),
        Path("examples/runtime.beta.json"),
        Path("examples/auth.beta.json"),
        Path("docs/beta-runbook.md"),
        Path("docs/release-checklist-beta.md"),
        Path("docs/templates/known-issue-template.md"),
        Path("docs/templates/pilot-feedback-template.md"),
        Path("scripts/beta_smoke.py"),
    ]
    for item in expected:
        assert item.exists(), f"Missing beta artifact: {item}"


def test_beta_smoke_flow(tmp_path: Path) -> None:
    result = run_smoke(tmp_path / ".agent-os")
    assert result["agent_id"] == "beta-agent"
    assert result["tool_status"] == "success"
    assert result["first_output_type"] in {"question", "final"}
