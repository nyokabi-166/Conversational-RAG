"""FastAPI dependencies for authenticating users and enforcing roles."""

from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.security import decode_access_token
from src.models.entities import PassengerAccount, StaffAccount

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthUser:
    """Authenticated account details used by route dependencies."""

    user_id: str
    user_type: str
    role: str
    identifier: str
    full_name: Optional[str] = None


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Valid bearer authentication is required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _resolve_user(
    credentials: Optional[HTTPAuthorizationCredentials], db: Session
) -> Optional[AuthUser]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None

    claims = decode_access_token(credentials.credentials)
    if not claims:
        return None

    user_id = claims.get("sub")
    user_type = claims.get("user_type")
    if not isinstance(user_id, str):
        return None

    if user_type == "passenger":
        account = db.query(PassengerAccount).filter_by(passenger_id=user_id).first()
        if account is None:
            return None
        return AuthUser(
            user_id=account.passenger_id,
            user_type="passenger",
            role=account.role or "passenger",
            identifier=account.email or account.passenger_id,
            full_name=account.full_name,
        )

    if user_type == "staff":
        account = db.query(StaffAccount).filter_by(staff_id=user_id).first()
        if account is None:
            return None
        return AuthUser(
            user_id=account.staff_id,
            user_type="staff",
            role=account.role or "policy_admin",
            identifier=account.username,
            full_name=account.full_name,
        )

    return None


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> AuthUser:
    """Require a valid token whose account still exists in the database."""
    user = _resolve_user(credentials, db)
    if user is None:
        raise _unauthorized()
    return user


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[AuthUser]:
    """Return no user for anonymous requests; reject supplied invalid tokens."""
    if credentials is None:
        return None
    user = _resolve_user(credentials, db)
    if user is None:
        raise _unauthorized()
    return user


def require_role(roles: Sequence[str]) -> Callable[..., AuthUser]:
    """Build a dependency that allows only authenticated users in ``roles``."""
    allowed_roles = frozenset(roles)

    def role_dependency(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        role_matches_account_type = (user.role == "passenger") == (
            user.user_type == "passenger"
        )
        if user.role not in allowed_roles or not role_matches_account_type:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return user

    return role_dependency
