"""
JWT Authentication & Session Management.

Provides token generation, validation, and session isolation.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

_SECRET_KEY = os.environ.get("NAIRA_SECRET_KEY", "dev-secret-key-change-in-prod")
_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token", auto_error=False)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create a new JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, _SECRET_KEY, algorithm=_ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict[str, Any]:
    """Verify a JWT token and return the payload."""
    try:
        payload = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict[str, Any]:
    """FastAPI dependency to get the current authenticated user."""
    # Temporarily allow bypass if no token is provided during development
    if not token:
        return {"sub": "local_dev_user", "roles": ["admin"]}
    
    return verify_token(token)


class SessionManager:
    """Manages user sessions and memory isolation."""

    def __init__(self):
        self._active_sessions = {}

    def get_session(self, session_id: str) -> dict[str, Any]:
        """Get or create a session context."""
        if session_id not in self._active_sessions:
            self._active_sessions[session_id] = {
                "created_at": time.time(),
                "last_active": time.time(),
                "user_id": None,
                "history": [],
            }
        else:
            self._active_sessions[session_id]["last_active"] = time.time()
            
        return self._active_sessions[session_id]
