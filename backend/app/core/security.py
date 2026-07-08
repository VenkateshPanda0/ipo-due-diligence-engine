"""Optional API-key validation helpers."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from app.core.config import Settings, get_settings

_REVIEWER_ROLES = frozenset({"reviewer", "admin"})


def validate_api_key(
    settings: Settings,
    authorization: str | None = Header(default=None),
) -> None:
    """Validate bearer token when API_KEY is configured."""
    if settings.api_key is None:
        return
    expected = f"Bearer {settings.api_key}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )


def require_api_key(
    settings: Settings = Depends(get_settings),
    authorization: str | None = Header(default=None),
) -> None:
    """FastAPI dependency that validates API-key auth when configured."""
    validate_api_key(settings, authorization)


def require_reviewer_role(
    settings: Settings = Depends(get_settings),
    authorization: str | None = Header(default=None),
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
) -> None:
    """Require a reviewer/admin role when API-key auth is enabled."""
    validate_api_key(settings, authorization)
    if settings.api_key is None:
        return
    if x_user_role is None or x_user_role.strip().lower() not in _REVIEWER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reviewer role required.",
        )
