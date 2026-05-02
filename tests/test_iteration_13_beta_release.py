from __future__ import annotations

from pathlib import Path

from scripts.beta_smoke import run_smoke


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
