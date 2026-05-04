from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

from agent_os.protocol import ModelCapability, RuntimeConfig


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


DEFAULT_CAPABILITIES: dict[str, dict] = {
    "gpt-4.1": {
        "context_window": 1_047_576,
        "max_output_tokens": 32_768,
        "input_price_per_1m": 2.0,
        "output_price_per_1m": 8.0,
        "cached_input_price_per_1m": 0.5,
    },
    "gpt-4.1-mini": {
        "context_window": 1_047_576,
        "max_output_tokens": 32_768,
        "input_price_per_1m": 0.8,
        "output_price_per_1m": 3.2,
        "cached_input_price_per_1m": 0.2,
    },
    "gpt-5.4-mini": {
        "context_window": 400_000,
        "max_output_tokens": 128_000,
        "input_price_per_1m": 0.75,
        "output_price_per_1m": 4.5,
        "cached_input_price_per_1m": 0.08,
    },
    "gpt-5.5": {
        "context_window": 1_050_000,
        "max_output_tokens": 128_000,
        "input_price_per_1m": 5.0,
        "output_price_per_1m": 30.0,
        "cached_input_price_per_1m": 0.5,
    },
    "text-embedding-3-small": {
        "context_window": 8192,
        "max_output_tokens": 1,
        "input_price_per_1m": 0.02,
        "output_price_per_1m": 0.0,
        "cached_input_price_per_1m": None,
    },
}


@dataclass
class CapabilityRefreshResult:
    refreshed_at: str
    model_count: int


class ModelCapabilityRegistry:
    def __init__(self, root: Path | str, runtime_config_loader=None) -> None:
        self.root = Path(root)
        self.dir = self.root / "capabilities"
        self.path = self.dir / "models.json"
        self.runtime_config_loader = runtime_config_loader
        self._init()

    def _init(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            payload = {
                "catalog_version": "2026-05-02",
                "updated_at": _utc_iso(),
                "models": DEFAULT_CAPABILITIES,
            }
            self._write(payload)

    def _read(self) -> dict:
        self._init()
        with self.path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write(self, payload: dict) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")

    def refresh(self) -> CapabilityRefreshResult:
        payload = self._read()
        payload["updated_at"] = _utc_iso()
        self._write(payload)
        return CapabilityRefreshResult(
            refreshed_at=payload["updated_at"],
            model_count=len(payload.get("models", {})),
        )

    def get(self, model_id: str, verify_provider: bool = False) -> ModelCapability:
        payload = self._read()
        models = payload.get("models", {})
        model_data = models.get(model_id)
        if model_data is None:
            raise ValueError(f"unknown_model_capability:{model_id}")

        if verify_provider:
            self._verify_model_exists(model_id)

        return ModelCapability(
            model_id=model_id,
            context_window=int(model_data["context_window"]),
            max_output_tokens=int(model_data["max_output_tokens"]),
            input_price_per_1m=model_data.get("input_price_per_1m"),
            output_price_per_1m=model_data.get("output_price_per_1m"),
            cached_input_price_per_1m=model_data.get("cached_input_price_per_1m"),
            source="provider_verified" if verify_provider else "local_catalog",
            catalog_version=str(payload.get("catalog_version", "2026-05-02")),
        )

    def _verify_model_exists(self, model_id: str) -> None:
        cfg: RuntimeConfig | None = self.runtime_config_loader() if callable(self.runtime_config_loader) else None
        if cfg is None or not cfg.openai_api_key:
            raise ValueError("runtime_config_error:missing_openai_api_key_for_model_verify")
        base_url = (cfg.openai_base_url or "https://api.openai.com/v1").rstrip("/")
        with httpx.Client(timeout=cfg.openai_timeout_ms / 1000.0) as client:
            response = client.get(
                f"{base_url}/models/{model_id}",
                headers={"Authorization": f"Bearer {cfg.openai_api_key}"},
            )
        if response.status_code == 404:
            raise ValueError(f"unknown_provider_model:{model_id}")
        response.raise_for_status()
