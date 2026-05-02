from __future__ import annotations

import json
from pathlib import Path

from agent_os.protocol import RuntimeConfig
from agent_os.secrets import SecretManager


def load_runtime_config(
    root: Path | str = ".agent-os",
    runtime_mode: str = "local",
    openai_api_key: str | None = None,
    openai_base_url: str | None = None,
    openai_timeout_ms: int | None = None,
    secrets: SecretManager | None = None,
) -> RuntimeConfig:
    secrets = secrets or SecretManager(root=root)
    root_path = Path(root)
    cfg_path = root_path / "runtime.json"
    file_cfg: dict = {}
    if cfg_path.exists():
        with cfg_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
            if isinstance(raw, dict):
                file_cfg = raw

    mode = runtime_mode or str(file_cfg.get("mode", "local"))
    cfg = RuntimeConfig(
        mode="openai" if mode == "openai" else "local",
        openai_api_key=secrets.resolve(openai_api_key) or secrets.resolve(str(file_cfg.get("openai_api_key", "secret://OPENAI_API_KEY"))),
        openai_base_url=secrets.resolve(openai_base_url) or secrets.resolve(file_cfg.get("openai_base_url")) or secrets.get("OPENAI_BASE_URL"),
        openai_timeout_ms=int(openai_timeout_ms or file_cfg.get("openai_timeout_ms", 20000)),
        openai_max_retries=int(file_cfg.get("openai_max_retries", 1)),
        default_token_budget=int(file_cfg.get("default_token_budget", 2500)),
    )
    return cfg
