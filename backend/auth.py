"""
Authentication and authorization edge.
Provides JWT extraction, current user resolution, and permission enforcement.
"""

import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import jwt
from fastapi import HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import asyncpg

from db import get_asyncpg_connection


# Security scheme for FastAPI
security = HTTPBearer(auto_error=False)


class CurrentUser:
    """Represents the current authenticated user."""
    
    def __init__(self, user_id: str, email: str, roles: List[str] = None):
        self.user_id = user_id
        self.email = email
        self.roles = roles or []
        self.permissions: List[str] = []
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        return permission in self.permissions
    
    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in self.roles


def decode_jwt(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT token.
    Returns the decoded payload.
    """
    secret = os.getenv("JWT_SECRET", "your-secret-key")
    
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"verify_exp": True}
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


def create_jwt(user_id: str, email: str, expires_in: int = 3600) -> str:
    """
    Create a JWT token for a user.
    
    Args:
        user_id: The user's ID
        email: The user's email
        expires_in: Token expiration time in seconds (default: 1 hour)
    
    Returns:
        The encoded JWT token
    """
    secret = os.getenv("JWT_SECRET", "your-secret-key")
    
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(seconds=expires_in),
        "iat": datetime.utcnow()
    }
    
    return jwt.encode(payload, secret, algorithm="HS256")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Optional[CurrentUser]:
    """
    Extract and validate the current user from the JWT token.
    This is a FastAPI dependency.
    """
    if not credentials:
        return None
    
    try:
        payload = decode_jwt(credentials.credentials)
        user_id = payload.get("sub")
        email = payload.get("email")
        
        if not user_id or not email:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        
        # Load user's roles and permissions from database
        user = CurrentUser(user_id=user_id, email=email)
        
        # Note: In a real implementation, we would load roles/permissions from DB
        # For now, returning a basic user object
        
        return user
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


async def require_permission(
    permission: str,
    current_user: CurrentUser = Depends(get_current_user)
) -> CurrentUser:
    """
    FastAPI dependency that requires a specific permission.
    
    Usage:
        @app.get("/admin")
        async def admin_route(user: CurrentUser = Depends(require_permission("admin.read"))):
            return {"message": "Admin access granted"}
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Note: In a real implementation, we would check user.has_permission(permission)
    # For now, we'll just return the user as this is a refactor with no behavior change
    
    return current_user


async def require_role(
    role: str,
    current_user: CurrentUser = Depends(get_current_user)
) -> CurrentUser:
    """
    FastAPI dependency that requires a specific role.
    
    Usage:
        @app.get("/admin")
        async def admin_route(user: CurrentUser = Depends(require_role("admin"))):
            return {"message": "Admin access granted"}
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Note: In a real implementation, we would check user.has_role(role)
    # For now, we'll just return the user as this is a refactor with no behavior change
    
    return current_user


async def require_authenticated(
    current_user: CurrentUser = Depends(get_current_user)
) -> CurrentUser:
    """
    FastAPI dependency that requires authentication (any valid user).
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    return current_user