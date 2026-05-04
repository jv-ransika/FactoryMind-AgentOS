from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ContextPreflightResult:
    estimated_tokens: int
    window_limit: int
    over_limit: bool
    allowed_input_tokens: int
    notes: list[str]


class ContextWindowManager:
    def __init__(self) -> None:
        try:
            import tiktoken  # type: ignore

            self._tiktoken = tiktoken
        except Exception:
            self._tiktoken = None

    def estimate_text_tokens(self, text: str, model: str) -> int:
        if not text:
            return 0
        if self._tiktoken is not None:
            try:
                enc = self._tiktoken.encoding_for_model(model)
            except Exception:
                enc = self._tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        words = len(text.split())
        return max(1, int(words * 1.3) + 8)

    def preflight(
        self,
        model: str,
        context_text: str,
        window_limit: int,
        reserve_output_tokens: int,
        safety_margin_tokens: int,
    ) -> ContextPreflightResult:
        est = self.estimate_text_tokens(context_text, model)
        allowed = max(1, window_limit - reserve_output_tokens - safety_margin_tokens)
        over = est > allowed
        notes: list[str] = []
        if over:
            notes.append("context_overflow_detected")
        return ContextPreflightResult(
            estimated_tokens=est,
            window_limit=window_limit,
            over_limit=over,
            allowed_input_tokens=allowed,
            notes=notes,
        )

    def compact_text(self, text: str, max_chars: int = 1200) -> str:
        if len(text) <= max_chars:
            return text
        head = text[: max_chars // 2].strip()
        tail = text[-max_chars // 2 :].strip()
        return f"{head}\n...[COMPACTED]...\n{tail}"
