from __future__ import annotations

import os
import subprocess
from pathlib import Path


def required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    dist = root / "dist"
    if not dist.exists():
        raise RuntimeError("dist/ does not exist. Run scripts/release/build_dist.py first.")
    if not list(dist.glob("*")):
        raise RuntimeError("dist/ is empty. Run scripts/release/build_dist.py first.")

    repo_url = required("AGENT_OS_PRIVATE_INDEX_URL")
    username = required("AGENT_OS_PRIVATE_INDEX_USERNAME")
    password = required("AGENT_OS_PRIVATE_INDEX_PASSWORD")
    subprocess.run(
        [
            "python",
            "-m",
            "twine",
            "upload",
            "--repository-url",
            repo_url,
            "-u",
            username,
            "-p",
            password,
            "dist/*",
        ],
        cwd=root,
        check=True,
    )
    print({"published": True, "repository_url": repo_url})


if __name__ == "__main__":
    main()
