from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_step(name: str, command: list[str], cwd: Path) -> dict:
    try:
        completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=True)
        return {
            "name": name,
            "status": "pass",
            "command": command,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
    except subprocess.CalledProcessError as exc:
        return {
            "name": name,
            "status": "fail",
            "command": command,
            "returncode": exc.returncode,
            "stdout": (exc.stdout or "").strip(),
            "stderr": (exc.stderr or "").strip(),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run fast-track beta.3 -> rc.1 release gates.")
    parser.add_argument("--json-out", default="", help="Optional path for machine-readable summary output.")
    parser.add_argument("--quick-contract", action="store_true", help="Run lightweight contract-only checks.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    steps = [
        ("full_test_suite", ["python", "-m", "pytest", "-q"]),
        ("build_artifacts", ["python", "scripts/release/build_dist.py"]),
        ("verify_install", ["python", "scripts/release/verify_install.py"]),
        ("example_proposal", ["python", "examples/proposal_agent_app.py"]),
        ("example_project_selection", ["python", "examples/project_selection_agent_app.py"]),
        ("example_keyword_extraction", ["python", "examples/keyword_extraction_agent_app.py"]),
        ("beta_smoke", ["python", "scripts/beta_smoke.py"]),
        ("secrets_tests", ["python", "-m", "pytest", "-q", "tests/test_iteration_12_secrets.py"]),
        ("auth_tenant_tests", ["python", "-m", "pytest", "-q", "tests/test_iteration_10_auth_tenant.py"]),
        ("service_runtime_tests", ["python", "-m", "pytest", "-q", "tests/test_iteration_6_service_runtime.py"]),
    ]
    if args.quick_contract:
        steps = [
            ("full_test_suite_subset", ["python", "-m", "pytest", "-q", "tests/test_iteration_1.py"]),
            ("beta_smoke", ["python", "scripts/beta_smoke.py"]),
            ("secrets_tests", ["python", "-m", "pytest", "-q", "tests/test_iteration_12_secrets.py"]),
        ]

    results = [run_step(name, cmd, root) for name, cmd in steps]
    failed = [item for item in results if item["status"] == "fail"]
    summary = {
        "release_track": "beta.3_to_rc.1_fast_track",
        "total_steps": len(results),
        "passed_steps": len(results) - len(failed),
        "failed_steps": len(failed),
        "status": "pass" if not failed else "fail",
        "steps": results,
    }

    rendered = json.dumps(summary, indent=2)
    print(rendered)
    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")

    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
