"""Authentication and Role-Based Access Control (RBAC) dependencies."""

from typing import Any, List, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from src.core.database import get_db
from src.core.security import decode_access_token
from src.models.entities import PassengerAccount, StaffAccount

security = HTTPBearer(auto_error=False)


class AuthUser:
    """Standardized authenticated user representation for RBAC."""

    def __init__(
        self,
        user_id: str,
        role: str,
        identifier: str,
        full_name: Optional[str] = None,
        db_entity: Any = None,
    ):
        self.user_id = user_id
        self.role = role
        self.identifier = identifier
        self.full_name = full_name
        self.db_entity = db_entity


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[AuthUser]:
    """Extracts and validates JWT token if provided; returns None for anonymous guest mode."""
    if not credentials or not credentials.credentials:
        return None

    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        return None

    user_id = payload.get("sub")
    user_type = payload.get("user_type")
    role = payload.get("role", "passenger")

    if not user_id or not user_type:
        return None

    if user_type == "passenger":
        passenger = db.query(PassengerAccount).filter(PassengerAccount.passenger_id == user_id).first()
        if not passenger:
            return None
        return AuthUser(
            user_id=passenger.passenger_id,
            role=passenger.role,
            identifier=passenger.email,
            full_name=passenger.full_name,
            db_entity=passenger,
        )

    elif user_type == "staff":
        staff = db.query(StaffAccount).filter(StaffAccount.staff_id == user_id).first()
        if not staff:
            return None
        return AuthUser(
            user_id=staff.staff_id,
            role=staff.role,
            identifier=staff.username,
            full_name=staff.full_name,
            db_entity=staff,
        )

    return None


async def get_current_user(
    user: Optional[AuthUser] = Depends(get_current_user_optional),
) -> AuthUser:
    """Enforces authentication; raises 401 Unauthorized if token is absent or invalid."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(allowed_roles: List[str]):
    """Enforces Role-Based Access Control (RBAC); raises 403 Forbidden if role is unauthorized."""

    async def role_checker(current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: role '{current_user.role}' lacks permissions for this resource.",
            )
        return current_user

    return role_checker
