from __future__ import annotations

import shutil
import subprocess
import tarfile
from pathlib import Path
import tomllib


def _normalized_pep440(version: str) -> str:
    # Convert versions like 0.1.0-beta.3 to wheel/sdist normalized 0.1.0b3.
    return version.replace("-beta.", "b")


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    dist = root / "dist"
    if dist.exists():
        shutil.rmtree(dist)
    dist.mkdir(parents=True, exist_ok=True)
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    raw_version = str(pyproject["project"]["version"])
    normalized_version = _normalized_pep440(raw_version)

    # Wheel build (tool-agnostic path via pip with explicit dist destination).
    subprocess.run(
        ["python", "-m", "pip", "download", "--no-deps", "--only-binary", ":all:", "--dest", str(dist), "."],
        cwd=root,
        check=True,
    )
    if not any(p.suffix == ".whl" for p in dist.glob("*")):
        subprocess.run(
            ["python", "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(dist), "."],
            cwd=root,
            check=True,
        )

    sdist_ok = False
    # Source distribution build: prefer python -m build.
    try:
        subprocess.run(["python", "-m", "build", "--sdist", "--outdir", "dist"], cwd=root, check=True)
        sdist_ok = True
    except subprocess.CalledProcessError:
        # Deterministic fallback for restricted environments: create a local source archive.
        archive_path = dist / f"agent_os-{normalized_version}.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tar:
            for path in [
                root / "src",
                root / "README.md",
                root / "pyproject.toml",
                root / "CHANGELOG.md",
            ]:
                tar.add(path, arcname=path.relative_to(root))
        sdist_ok = True

    # Enforce version-consistent artifacts only.
    for artifact in list(dist.glob("*")):
        name = artifact.name
        if normalized_version not in name:
            artifact.unlink(missing_ok=True)

    files = sorted(p.name for p in dist.glob("*"))
    if not files:
        raise RuntimeError("No distribution artifacts were generated.")
    if not any(p.suffix == ".whl" for p in dist.glob("*")):
        raise RuntimeError("Wheel artifact could not be generated.")
    if not sdist_ok:
        raise RuntimeError("Source distribution could not be generated.")
    print({"dist_files": files})


if __name__ == "__main__":
    main()
