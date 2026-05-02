from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol


class SecretResolver(Protocol):
    def get(self, key: str) -> str | None: ...


class EnvSecretProvider:
    def get(self, key: str) -> str | None:
        return os.getenv(key)


class DotenvSecretProvider:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._loaded = False
        self._values: dict[str, str] = {}

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            row = line.strip()
            if not row or row.startswith("#") or "=" not in row:
                continue
            k, v = row.split("=", 1)
            self._values[k.strip()] = v.strip()

    def get(self, key: str) -> str | None:
        self._load()
        return self._values.get(key)

    def reload(self) -> None:
        self._loaded = False
        self._values = {}
        self._load()


class LocalSecretsFileProvider:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._loaded = False
        self._values: dict[str, str] = {}

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            self._values = {str(k): str(v) for k, v in raw.items()}

    def get(self, key: str) -> str | None:
        self._load()
        return self._values.get(key)

    def reload(self) -> None:
        self._loaded = False
        self._values = {}
        self._load()


class SecretManager:
    def __init__(self, root: Path | str = ".agent-os") -> None:
        self.root = Path(root)
        self.providers: list[SecretResolver] = [
            EnvSecretProvider(),
            DotenvSecretProvider(self.root / "secrets.env"),
            DotenvSecretProvider(Path(".env")),
            LocalSecretsFileProvider(self.root / "secrets.json"),
        ]
        self.cache: dict[str, str] = {}
        self.last_reload_ok = True
        self.last_reload_errors: list[str] = []

    def reload(self) -> dict:
        self.cache = {}
        self.last_reload_errors = []
        self.last_reload_ok = True
        for provider in self.providers:
            fn = getattr(provider, "reload", None)
            if callable(fn):
                try:
                    fn()
                except Exception as exc:  # noqa: BLE001
                    self.last_reload_ok = False
                    self.last_reload_errors.append(f"{provider.__class__.__name__}:{exc.__class__.__name__}")
        return self.status()

    def status(self) -> dict:
        return {
            "providers": [provider.__class__.__name__ for provider in self.providers],
            "cache_keys": sorted(self.cache.keys()),
            "last_reload_ok": self.last_reload_ok,
            "last_reload_errors": list(self.last_reload_errors),
        }

    def resolve(self, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            return str(value)
        if value.startswith("secret://"):
            key = value.split("secret://", 1)[1]
            return self.get(key)
        return value

    def get(self, key: str) -> str | None:
        if key in self.cache:
            return self.cache[key]
        for provider in self.providers:
            value = provider.get(key)
            if value is not None and str(value).strip() != "":
                self.cache[key] = str(value)
                return self.cache[key]
        return None

    def get_required(self, key: str) -> str:
        value = self.get(key)
        if value is None:
            raise RuntimeError(f"secret_unavailable:{key}")
        return value

    def validate_required(self, profile: str = "dev") -> dict:
        required = ["OPENAI_API_KEY"] if profile == "dev" else [
            "OPENAI_API_KEY",
            "AGENT_OS_POSTGRES_DSN",
            "AGENT_OS_REDIS_URL",
            "AGENT_OS_JWT_ISSUER",
            "AGENT_OS_JWT_AUDIENCE",
        ]
        missing = [key for key in required if self.get(key) is None]
        return {"profile": profile, "ok": not missing, "missing": missing}
