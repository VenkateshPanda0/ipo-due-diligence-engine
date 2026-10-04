"""
Authentication and authorization.

Identity and role come only from server-side configuration. A client-supplied
role header (``X-User-Role``) is ignored — in ruleset 1.0.0 it let any key holder
act as a reviewer (baseline defect D11).

When no keys are configured the API runs in local single-user mode: requests are
attributed to the ``local-user`` principal with the admin role. Use this only on a
trusted machine.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from enum import Enum

from fastapi import Depends, Header, HTTPException, Request, status

from app.core.config import Settings, get_settings


class Role(str, Enum):
    VIEWER = "viewer"
    ANALYST = "analyst"
    REVIEWER = "reviewer"
    ADMIN = "admin"


_RANK = {Role.VIEWER: 0, Role.ANALYST: 1, Role.REVIEWER: 2, Role.ADMIN: 3}


@dataclass(frozen=True)
class Principal:
    """Authenticated caller."""

    user_id: str
    role: Role
    authenticated: bool

    def has(self, role: Role) -> bool:
        return _RANK[self.role] >= _RANK[role]


LOCAL_PRINCIPAL = Principal(user_id="local-user", role=Role.ADMIN, authenticated=False)


@dataclass(frozen=True)
class _KeyEntry:
    user_id: str
    role: Role
    digest: bytes


def _digest(key: str) -> bytes:
    return hashlib.sha256(key.encode("utf-8")).digest()


def parse_api_keys(settings: Settings) -> list[_KeyEntry]:
    """Parse API_KEYS / API_KEY into key entries (keys are held only as digests)."""
    entries: list[_KeyEntry] = []
    if settings.api_keys:
        for raw in settings.api_keys.split(","):
            raw = raw.strip()
            if not raw:
                continue
            parts = raw.split("|")
            if len(parts) != 3:
                raise ValueError("API_KEYS entries must be '<user_id>|<role>|<key or sha256=hex>'.")
            user_id, role, secret = (p.strip() for p in parts)
            digest = (
                bytes.fromhex(secret.removeprefix("sha256="))
                if secret.startswith("sha256=")
                else _digest(secret)
            )
            entries.append(_KeyEntry(user_id=user_id, role=Role(role), digest=digest))
    if settings.api_key:
        entries.append(
            _KeyEntry(user_id="api-user", role=Role.ANALYST, digest=_digest(settings.api_key))
        )
    return entries


def authenticate(settings: Settings, authorization: str | None) -> Principal:
    """Resolve the principal for a request; raises 401 on bad credentials."""
    entries = parse_api_keys(settings)
    if not entries:
        return LOCAL_PRINCIPAL
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key.")
    presented = _digest(authorization.removeprefix("Bearer ").strip())
    match: _KeyEntry | None = None
    for entry in entries:  # compare against every entry: no early exit timing signal
        if hmac.compare_digest(presented, entry.digest):
            match = entry
    if match is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key.")
    return Principal(user_id=match.user_id, role=match.role, authenticated=True)


def request_settings(request: Request) -> Settings:
    """Settings of the application instance serving this request."""
    container = getattr(request.app.state, "container", None)
    return container.settings if container is not None else get_settings()


def get_principal(
    settings: Settings = Depends(request_settings),
    authorization: str | None = Header(default=None),
) -> Principal:
    """FastAPI dependency returning the authenticated principal."""
    return authenticate(settings, authorization)


def require_api_key(principal: Principal = Depends(get_principal)) -> Principal:
    """Backward-compatible dependency: any authenticated (or local) principal."""
    return principal


def require_role(role: Role):  # type: ignore[no-untyped-def]
    """Dependency factory enforcing a minimum role."""

    def _check(principal: Principal = Depends(get_principal)) -> Principal:
        if not principal.has(role):
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail=f"{role.value} role required.")
        return principal

    return _check


require_reviewer_role = require_role(Role.REVIEWER)
require_analyst_role = require_role(Role.ANALYST)
