from fastapi import Depends, HTTPException, Request, status
from typing import Optional, Dict, Any

from ..services.auth_service import get_auth_service


async def get_current_user(request: Request) -> Dict[str, Any]:
    """
    Dependency that validates session and switches to user's database.
    Use this on all protected endpoints.
    """
    # Get session token from Authorization header
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    session_token = auth_header.replace("Bearer ", "")
    
    # Validate session and switch database context
    auth_service = get_auth_service()
    is_valid, user = await auth_service.validate_session(session_token)
    
    if not is_valid or not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_current_user_optional(request: Request) -> Optional[Dict[str, Any]]:
    """
    Optional dependency that validates session if present.
    Returns None if no valid session.
    """
    try:
        return await get_current_user(request)
    except HTTPException:
        return None