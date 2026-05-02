from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from sqlalchemy import text

from agent_os.secrets import SecretManager
from agent_os.storage import PostgresDomainStore, RedisIdempotencyStore


def environment_mode() -> str:
    return os.getenv("AGENT_OS_ENV", "dev").strip().lower() or "dev"


def check_dependencies(
    root: Path | str,
    postgres_dsn: str | None,
    redis_url: str | None,
    require_migration_head: bool = True,
    secrets: SecretManager | None = None,
) -> dict[str, Any]:
    secrets = secrets or SecretManager(root=root)
    postgres_dsn = secrets.resolve(postgres_dsn) or secrets.get("AGENT_OS_POSTGRES_DSN")
    redis_url = secrets.resolve(redis_url) or secrets.get("AGENT_OS_REDIS_URL")
    result = {
        "mode": environment_mode(),
        "postgres_ok": False,
        "redis_ok": False,
        "migration_ok": False,
        "errors": [],
    }
    if not postgres_dsn:
        result["errors"].append("missing_postgres_dsn")
        return result
    if not redis_url:
        result["errors"].append("missing_redis_url")
        return result

    try:
        pg = PostgresDomainStore(dsn=postgres_dsn, root=root)
        pg.init()
        with pg.engine.begin() as conn:
            conn.execute(text("SELECT 1"))
        result["postgres_ok"] = True
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(f"postgres_error:{exc.__class__.__name__}")

    try:
        idem = RedisIdempotencyStore(redis_url=redis_url)
        idem.redis.ping()
        result["redis_ok"] = True
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(f"redis_error:{exc.__class__.__name__}")

    try:
        if require_migration_head:
            # lightweight check for expected latest table/column presence
            with pg.engine.begin() as conn:  # type: ignore[name-defined]
                conn.execute(text("SELECT tenant_id FROM agent_os_records LIMIT 1"))
            result["migration_ok"] = True
        else:
            result["migration_ok"] = True
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(f"migration_error:{exc.__class__.__name__}")

    return result
