from __future__ import annotations

from fastapi import HTTPException

from agent_os.protocol import AuthContext, Role


PERMISSIONS: dict[str, set[Role]] = {
    "session:init": {Role.ADMIN, Role.USER},
    "session:run": {Role.ADMIN, Role.USER},
    "session:feedback": {Role.ADMIN, Role.USER},
    "session:accept": {Role.ADMIN, Role.USER},
    "session:get": {Role.ADMIN, Role.USER},
    "learning:run": {Role.ADMIN, Role.USER},
    "learning:evaluate": {Role.ADMIN, Role.USER},
    "learning:promote": {Role.ADMIN},
    "learning:rollback": {Role.ADMIN},
    "learning:policy": {Role.ADMIN},
    "tools:register": {Role.ADMIN},
    "tools:bind": {Role.ADMIN},
    "tools:call": {Role.ADMIN, Role.USER},
    "tools:audit": {Role.ADMIN, Role.USER},
    "ops:metrics": {Role.OPS, Role.ADMIN},
    "ops:readyz": {Role.OPS, Role.ADMIN},
}


def require_permission(ctx: AuthContext, permission: str) -> None:
    allowed = PERMISSIONS.get(permission, set())
    if not allowed:
        raise HTTPException(status_code=403, detail=f"permission_not_mapped:{permission}")
    if not set(ctx.roles).intersection({role.value for role in allowed}):
        raise HTTPException(status_code=403, detail=f"permission_denied:{permission}")
