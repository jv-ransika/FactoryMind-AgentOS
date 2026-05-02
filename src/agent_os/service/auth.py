from __future__ import annotations

import os
import base64
import json
import time
from pathlib import Path
from typing import Callable

from fastapi import Header, HTTPException

from agent_os.protocol import AuthConfig, AuthContext, Role
from agent_os.secrets import SecretManager


def load_auth_config(root: Path | str = ".agent-os", secrets: SecretManager | None = None) -> AuthConfig:
    secrets = secrets or SecretManager(root=root)
    root_path = Path(root)
    cfg_path = root_path / "auth.json"
    raw: dict = {}
    if cfg_path.exists():
        import json

        with cfg_path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
            if isinstance(value, dict):
                raw = value
    return AuthConfig(
        issuer=secrets.resolve(raw.get("issuer")) or secrets.get("AGENT_OS_JWT_ISSUER") or "agent-os",
        audience=secrets.resolve(raw.get("audience")) or secrets.get("AGENT_OS_JWT_AUDIENCE") or "agent-os",
        jwks_url=secrets.resolve(raw.get("jwks_url")) or secrets.get("AGENT_OS_JWT_JWKS_URL"),
        public_key_path=secrets.resolve(raw.get("public_key_path")) or secrets.get("AGENT_OS_JWT_PUBLIC_KEY_PATH"),
        clock_skew_seconds=int(secrets.resolve(str(raw.get("clock_skew_seconds", "")) or None) or os.getenv("AGENT_OS_JWT_CLOCK_SKEW_SECONDS", "30")),
    )


def build_auth_dependency(auth_config: AuthConfig, required_roles: set[Role] | None = None) -> Callable:
    required_roles = required_roles or set()

    def dep(authorization: str | None = Header(default=None)) -> AuthContext:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing_bearer_token")
        token = authorization.split(" ", 1)[1].strip()
        claims = _decode_token(token, auth_config)
        sub = claims.get("sub")
        tenant_id = claims.get("tenant_id")
        roles = claims.get("roles", [])
        exp = claims.get("exp")
        if not isinstance(sub, str) or not sub:
            raise HTTPException(status_code=401, detail="invalid_claim_sub")
        if not isinstance(tenant_id, str) or not tenant_id:
            raise HTTPException(status_code=401, detail="invalid_claim_tenant_id")
        if not isinstance(roles, list) or not all(isinstance(item, str) for item in roles):
            raise HTTPException(status_code=401, detail="invalid_claim_roles")
        if not isinstance(exp, int) or exp < int(time.time()):
            raise HTTPException(status_code=401, detail="invalid_claim_exp")
        ctx = AuthContext(sub=sub, tenant_id=tenant_id, roles=[str(item) for item in roles])
        if required_roles and not set(ctx.roles).intersection({r.value for r in required_roles}):
            raise HTTPException(status_code=403, detail="insufficient_role")
        return ctx

    return dep


def _decode_token(token: str, config: AuthConfig) -> dict:
    if token.startswith("dev."):
        return _decode_dev_token(token)
    try:
        import jwt  # type: ignore

        algorithms = ["RS256"]
        options = {"require": ["exp", "sub", "tenant_id", "roles"]}
        if config.jwks_url:
            jwk_client = jwt.PyJWKClient(config.jwks_url)
            signing_key = jwk_client.get_signing_key_from_jwt(token).key
            return jwt.decode(
                token,
                signing_key,
                algorithms=algorithms,
                audience=config.audience,
                issuer=config.issuer,
                options=options,
                leeway=config.clock_skew_seconds,
            )
        if config.public_key_path:
            with Path(config.public_key_path).open("r", encoding="utf-8") as handle:
                public_key = handle.read()
            return jwt.decode(
                token,
                public_key,
                algorithms=algorithms,
                audience=config.audience,
                issuer=config.issuer,
                options=options,
                leeway=config.clock_skew_seconds,
            )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail=f"invalid_token:{exc.__class__.__name__}") from exc
    raise HTTPException(status_code=500, detail="auth_config_missing_verifier")


def _decode_dev_token(token: str) -> dict:
    try:
        payload_b64 = token.split(".", 1)[1]
        raw = base64.urlsafe_b64decode(payload_b64 + "=" * (-len(payload_b64) % 4))
        claims = json.loads(raw.decode("utf-8"))
        if not isinstance(claims, dict):
            raise ValueError("claims_not_object")
        return claims
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail=f"invalid_dev_token:{exc.__class__.__name__}") from exc
