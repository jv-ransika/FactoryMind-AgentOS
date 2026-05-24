from __future__ import annotations

import json
import os
from pathlib import Path

from agent_os.protocol import RuntimeConfig
from agent_os.secrets import SecretManager


def _bool_config(value: object, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


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
    configured_engine = os.getenv("AGENT_OS_RUNTIME_ENGINE") or str(file_cfg.get("runtime_engine", "openai_agents_sdk"))
    cfg = RuntimeConfig(
        mode="openai" if mode == "openai" else "local",
        runtime_engine=configured_engine,
        openai_api_key=secrets.resolve(openai_api_key) or secrets.resolve(str(file_cfg.get("openai_api_key", "secret://OPENAI_API_KEY"))),
        openai_base_url=secrets.resolve(openai_base_url) or secrets.resolve(file_cfg.get("openai_base_url")) or secrets.get("OPENAI_BASE_URL"),
        openai_timeout_ms=int(openai_timeout_ms or file_cfg.get("openai_timeout_ms", 20000)),
        openai_max_retries=int(file_cfg.get("openai_max_retries", 1)),
        default_token_budget=int(file_cfg.get("default_token_budget", 2500)),
        reserve_output_tokens=int(file_cfg.get("reserve_output_tokens", 2048)),
        context_safety_margin_tokens=int(file_cfg.get("context_safety_margin_tokens", 512)),
        flame_pool_size_trigger=int(file_cfg.get("flame_pool_size_trigger", 12)),
        flame_time_trigger_hours=int(file_cfg.get("flame_time_trigger_hours", 24)),
        flame_extraction_model=str(file_cfg.get("flame_extraction_model", "gpt-4.1-mini")),
        flame_reflection_model=str(file_cfg.get("flame_reflection_model", "gpt-4.1-mini")),
        embedding_provider=str(os.getenv("AGENT_OS_EMBEDDING_PROVIDER") or file_cfg.get("embedding_provider", "openai")),
        embedding_model=str(os.getenv("AGENT_OS_EMBEDDING_MODEL") or file_cfg.get("embedding_model", "text-embedding-3-small")),
        memory_vector_top_k=int(os.getenv("AGENT_OS_MEMORY_VECTOR_TOP_K") or file_cfg.get("memory_vector_top_k", 5)),
        confidence_repair_enabled=_bool_config(file_cfg.get("confidence_repair_enabled"), True),
        confidence_threshold=float(file_cfg.get("confidence_threshold", 0.60)),
        confidence_repair_max_attempts=int(file_cfg.get("confidence_repair_max_attempts", 1)),
    )
    return cfg
