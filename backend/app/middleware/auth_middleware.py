from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ..services.auth_service import get_auth_service


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that validates sessions for all requests except auth and health endpoints
    """
    
    def __init__(self, app):
        super().__init__(app)
        # Endpoints that don't require authentication
        self.excluded_paths = {
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/auth/",
            "/api/v1/auth/register",
            "/api/v1/auth/login",
            "/api/v1/auth/logout",
            "/api/v1/auth/status", 
            "/api/v1/auth/users",
            "/api/v1/health",
            "/api/v1/health/",
        }
    
    async def dispatch(self, request: Request, call_next):
        print(f"MIDDLEWARE: Processing request to {request.url.path}")
        
        # Skip authentication for excluded paths
        if request.url.path in self.excluded_paths or request.url.path.startswith("/api/v1/auth/"):
            print(f"MIDDLEWARE: Skipping auth for {request.url.path}")
            return await call_next(request)
        
        # Skip authentication for non-API paths
        if not request.url.path.startswith("/api/v1/"):
            print(f"MIDDLEWARE: Skipping non-API path {request.url.path}")
            return await call_next(request)
        
        # Check for session token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            print(f"MIDDLEWARE: No auth header for {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authentication required"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        session_token = auth_header.replace("Bearer ", "")
        print(f"MIDDLEWARE: Validating session for {request.url.path}")
        
        # Validate session and switch database context
        try:
            auth_service = get_auth_service()
            is_valid, user = await auth_service.validate_session(session_token)
            
            if not is_valid or not user:
                print(f"MIDDLEWARE: Invalid session for {request.url.path}")
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid or expired session"},
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            print(f"MIDDLEWARE: Valid session for user {user['username']} on {request.url.path}")
            
            # Add user info to request state for use in endpoints
            request.state.current_user = user
            
        except Exception as e:
            print(f"MIDDLEWARE: Exception validating session: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": f"Authentication error: {str(e)}"},
            )
        
        # Continue with request
        return await call_next(request)