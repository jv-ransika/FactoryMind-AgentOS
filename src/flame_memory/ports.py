from __future__ import annotations

from typing import Any, Literal, Protocol


class EmbeddingProvider(Protocol):
    model: str
    last_usage_tokens: dict[str, int]
    last_request_bytes: int
    last_latency_ms: int

    def embed_text(self, text: str) -> list[float]: ...


class MetricsSink(Protocol):
    def inc(self, name: str, value: int = 1) -> None: ...


class UsageRecorder(Protocol):
    def record_usage(
        self,
        *,
        agent: Any,
        operation_bucket: Literal["embedding", "flame_extraction", "flame_reflection"],
        model: str | None,
        request_bytes: int,
        latency_ms: int,
        session_id: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        reasoning_tokens: int = 0,
        total_tokens: int = 0,
    ) -> None: ...
