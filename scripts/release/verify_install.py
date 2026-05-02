from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    dist = root / "dist"
    wheels = sorted(dist.glob("*.whl"))
    if not wheels:
        raise RuntimeError("No wheel found. Run scripts/release/build_dist.py first.")
    wheel = wheels[-1]

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        venv = tmp / "venv"
        subprocess.run(["python", "-m", "venv", str(venv)], check=True)
        py = venv / ("Scripts/python.exe" if (venv / "Scripts").exists() else "bin/python")
        pip = venv / ("Scripts/pip.exe" if (venv / "Scripts").exists() else "bin/pip")
        subprocess.run([str(py), "-m", "pip", "install", "--upgrade", "pip"], check=True)
        subprocess.run([str(pip), "install", str(wheel)], check=True)

        code = (
            "from pathlib import Path\n"
            "from agent_os import AgentOS\n"
            "root=Path('.agent-os-install-check')\n"
            "app=AgentOS.load(root=root, runtime_mode='local')\n"
            "app.create_agent(agent_id='a1',goal='g',model='gpt-4.1-mini',tenant_id='default')\n"
            "s=app.sessions.init('a1','hello')\n"
            "o=app.sessions.run(s.session_id)\n"
            "print({'session_id': s.session_id, 'output_type': o.type.value})\n"
        )
        run = subprocess.run([str(py), "-c", code], capture_output=True, text=True, check=True)
        print(json.dumps({"wheel": wheel.name, "smoke_output": run.stdout.strip()}, indent=2))


if __name__ == "__main__":
    main()
