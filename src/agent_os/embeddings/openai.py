from __future__ import annotations

import time

import httpx


class OpenAIEmbeddingProvider:
    def __init__(
        self,
        api_key: str | None,
        model: str = "text-embedding-3-small",
        base_url: str | None = None,
        timeout_ms: int = 20000,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.timeout_ms = max(1, int(timeout_ms))
        self.last_usage_tokens: dict[str, int] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "total_tokens": 0,
        }
        self.last_request_bytes: int = 0
        self.last_latency_ms: int = 0

    def embed_text(self, text: str) -> list[float]:
        if not self.api_key:
            raise RuntimeError("embedding_config_error:missing_openai_api_key")
        if not text.strip():
            return []
        body = {
            "model": self.model,
            "input": text,
        }
        self.last_request_bytes = len(str(text).encode("utf-8"))
        started = time.perf_counter()
        with httpx.Client(timeout=self.timeout_ms / 1000.0) as client:
            resp = client.post(
                f"{self.base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
        resp.raise_for_status()
        payload = resp.json()
        self.last_latency_ms = int((time.perf_counter() - started) * 1000)
        usage = payload.get("usage") or {}
        self.last_usage_tokens = {
            "input_tokens": int(usage.get("prompt_tokens", 0) or 0),
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "total_tokens": int(usage.get("total_tokens", usage.get("prompt_tokens", 0)) or 0),
        }
        data = payload.get("data")
        if not isinstance(data, list) or not data:
            raise RuntimeError("embedding_provider_error:missing_data")
        first = data[0] if isinstance(data[0], dict) else {}
        vector = first.get("embedding")
        if not isinstance(vector, list):
            raise RuntimeError("embedding_provider_error:missing_embedding")
        return [float(value) for value in vector]
