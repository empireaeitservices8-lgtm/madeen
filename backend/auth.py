"""Password hashing, JWT tokens, and FastAPI dependencies for login and role checks."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import ADMIN_PASSWORD, ADMIN_USERNAME, JWT_EXPIRE_HOURS, JWT_SECRET
from db import User, get_db

ALGORITHM = "HS256"
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def user_from_token(token: Optional[str], db: Session) -> Optional[User]:
    """Resolve a token to an active user, or None if missing/invalid/expired."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    user = db.get(User, int(payload["sub"]))
    return user if user and user.is_active else None


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    user = user_from_token(creds.credentials if creds else None, db)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in or session expired")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user


def scoped_site_id(user: User) -> Optional[int]:
    """Admins see every site (None); supervisors are limited to their own site."""
    return None if user.role == "admin" else user.site_id


def ensure_site_access(user: User, site_id: int) -> None:
    if user.role != "admin" and user.site_id != site_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have access to this site")


def ensure_default_admin(db: Session) -> None:
    """Create the first admin account if there are no users yet."""
    if db.scalar(select(User.id).limit(1)) is not None:
        return
    password = ADMIN_PASSWORD or secrets.token_urlsafe(9)
    db.add(User(username=ADMIN_USERNAME, password_hash=hash_password(password),
                full_name="Administrator", role="admin"))
    db.commit()
    if ADMIN_PASSWORD:
        print(f"[setup] Created admin user '{ADMIN_USERNAME}' with the password from ADMIN_PASSWORD")
    else:
        print("=" * 64)
        print(f"[setup] Created admin user '{ADMIN_USERNAME}' with password: {password}")
        print("[setup] Log in and change it from the Users page. This is shown only once.")
        print("=" * 64)
