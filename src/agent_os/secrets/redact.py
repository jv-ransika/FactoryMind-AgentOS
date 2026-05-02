from __future__ import annotations

from typing import Any


SUSPECT_KEYS = {
    "openai_api_key",
    "api_key",
    "authorization",
    "password",
    "token",
    "secret",
    "private_key",
    "postgres_dsn",
    "redis_url",
}


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            key = str(k).lower()
            if any(marker in key for marker in SUSPECT_KEYS):
                out[str(k)] = "[REDACTED]"
            else:
                out[str(k)] = redact(v)
        return out
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in ["sk-", "bearer ", "password=", "secret://"]):
            return "[REDACTED]"
        return value
    return value
