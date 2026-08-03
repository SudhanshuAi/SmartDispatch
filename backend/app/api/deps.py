"""Auth stub — role + scoped driver/guest identity via headers (JWT later)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import Header, HTTPException, status

from app.config import get_settings
from app.models.enums import UserRole


@dataclass(frozen=True)
class AuthContext:
    role: UserRole
    user_id: str | None = None
    driver_id: UUID | None = None
    guest_id: UUID | None = None


def _parse_role(x_role: str | None) -> UserRole:
    settings = get_settings()
    role_raw = (x_role or settings.auth_stub_default_role).lower()
    try:
        return UserRole(role_raw)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid X-Role") from exc


def require_admin(x_role: str | None = Header(default=None, alias="X-Role")) -> AuthContext:
    """Admin routes require explicit X-Role: admin — never inferred from settings default."""
    if not x_role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-Role required")
    role = _parse_role(x_role)
    if role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return AuthContext(role=role)


def require_driver(
    x_role: str | None = Header(default=None, alias="X-Role"),
    x_driver_id: str | None = Header(default=None, alias="X-Driver-Id"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> AuthContext:
    """Driver routes require explicit driver role + driver id — never inferred from admin default."""
    if not x_role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-Role required")
    role = _parse_role(x_role)
    if role != UserRole.driver:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Driver role required")
    if not x_driver_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-Driver-Id required")
    try:
        driver_id = UUID(x_driver_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid X-Driver-Id") from exc
    return AuthContext(role=role, user_id=x_user_id, driver_id=driver_id)


def require_guest(
    x_role: str | None = Header(default=None, alias="X-Role"),
    x_guest_id: str | None = Header(default=None, alias="X-Guest-Id"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> AuthContext:
    """Guest routes require explicit guest role + guest id."""
    if not x_role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-Role required")
    role = _parse_role(x_role)
    if role != UserRole.guest:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Guest role required")
    if not x_guest_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-Guest-Id required")
    try:
        guest_id = UUID(x_guest_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid X-Guest-Id") from exc
    return AuthContext(role=role, user_id=x_user_id, guest_id=guest_id)
