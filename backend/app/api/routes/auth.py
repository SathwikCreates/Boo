import os
from fastapi import APIRouter, HTTPException, status, Depends, File, UploadFile, Request
from fastapi.responses import JSONResponse
from typing import List, Optional

from ...models.auth_models import (
    UserRegistrationRequest, LoginRequest, UserResponse, UserListResponse,
    RegistrationResponse, LoginResponse, AuthenticationError, SessionInfo,
    RecoveryPhraseRequest, EmergencyKeyRequest, PasswordResetRequest,
    ChangePasswordRequest, ChangeRecoveryPhraseRequest, ChangeCredentialsResponse,
    UserStatsResponse, DevResetRequest, DevTestUserRequest
)
from ...services.auth_service import get_auth_service
from ...services.user_registry_service import get_user_registry_service
from ...services.database_manager import get_database_manager

router = APIRouter(prefix="/auth", tags=["authentication"])

# Dependency to get current session info
async def get_current_session():
    """Get current session information"""
    auth_service = get_auth_service()
    is_valid, user = await auth_service.validate_session("current")  # Simplified for now
    return {"is_authenticated": is_valid, "user": user}


@router.get("/users", response_model=List[UserListResponse])
async def list_users():
    """List all active users (usernames and display names only)"""
    try:
        user_registry = get_user_registry_service()
        users = await user_registry.list_users()
        return [UserListResponse(**user) for user in users]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve users: {str(e)}"
        )


@router.post("/register", response_model=RegistrationResponse)
async def register_user(request: UserRegistrationRequest):
    """Register a new user account"""
    try:
        auth_service = get_auth_service()
        
        # Initialize user registry if it doesn't exist
        user_registry = get_user_registry_service()
        await user_registry.initialize()
        
        result = await auth_service.register_user(
            name=request.name,
            password=request.password,
            recovery_phrase=request.recovery_phrase,
            emergency_key=request.emergency_key
        )
        
        return RegistrationResponse(
            user=UserResponse(**result['user']),
            emergency_key_file=result['emergency_key_file'],
            filename=result['filename'],
            message="Registration successful"
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )


@router.post("/login", response_model=LoginResponse)
async def login_user(request: LoginRequest):
    """Login user with password, recovery phrase, or emergency key"""
    try:
        # Validate that exactly one auth method is provided
        request.validate_auth_method()
        
        auth_service = get_auth_service()
        success = False
        user = None
        message = ""
        
        # Try password authentication
        if request.password:
            success, user, message = await auth_service.authenticate_password(
                request.name, request.password
            )
        
        # Try recovery phrase authentication
        elif request.recovery_phrase:
            success, user, message = await auth_service.authenticate_recovery_phrase(
                request.name, request.recovery_phrase
            )
        
        # Try emergency key authentication
        elif request.emergency_key_content:
            success, user, message = await auth_service.authenticate_emergency_key(
                request.name, request.emergency_key_content
            )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=message
            )
        
        # Create session
        session_token = await auth_service.create_session(user)
        
        return LoginResponse(
            user=UserResponse(**user),
            session_token=session_token,
            message=message
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )


@router.post("/logout")
async def logout_user(request: Request):
    """End current user session"""
    try:
        # Get session token from Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header.replace("Bearer ", "")
            
            auth_service = get_auth_service()
            await auth_service.logout(session_token)
        
        return {"message": "Logout successful"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Logout failed: {str(e)}"
        )


@router.post("/verify-phrase")
async def verify_recovery_phrase(request: RecoveryPhraseRequest):
    """Verify recovery phrase without logging in"""
    try:
        auth_service = get_auth_service()
        success, user, message = await auth_service.authenticate_recovery_phrase(
            request.name, request.recovery_phrase
        )
        
        if success:
            return {"valid": True, "message": "Recovery phrase is valid"}
        else:
            return {"valid": False, "message": message}
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification failed: {str(e)}"
        )


@router.post("/emergency")
async def verify_emergency_key(request: EmergencyKeyRequest):
    """Verify emergency key without logging in"""
    try:
        auth_service = get_auth_service()
        success, user, message = await auth_service.authenticate_emergency_key(
            request.name, request.key_file_content
        )
        
        if success:
            return {"valid": True, "message": "Emergency key is valid"}
        else:
            return {"valid": False, "message": message}
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification failed: {str(e)}"
        )


@router.post("/emergency/upload")
async def upload_emergency_key(name: str, file: UploadFile = File(...)):
    """Upload and verify emergency key file"""
    try:
        if not file.filename.endswith('.boounlock'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file type. Please upload an .boounlock file"
            )
        
        content = await file.read()
        file_content = content.decode('utf-8')
        
        auth_service = get_auth_service()
        success, user, message = await auth_service.authenticate_emergency_key(
            name, file_content
        )
        
        if success:
            # Create session
            session_token = await auth_service.create_session(user)
            return LoginResponse(
                user=UserResponse(**user),
                session_token=session_token,
                message="Emergency key authentication successful"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=message
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Emergency key upload failed: {str(e)}"
        )


@router.post("/reset-password")
async def reset_password(request: PasswordResetRequest):
    """Reset user password using recovery phrase or emergency key"""
    try:
        request.validate_verification_method()
        
        auth_service = get_auth_service()
        
        # Verify with recovery phrase or emergency key first
        verified = False
        if request.recovery_phrase:
            success, user, _ = await auth_service.authenticate_recovery_phrase(
                request.name, request.recovery_phrase
            )
            verified = success
        elif request.emergency_key_content:
            success, user, _ = await auth_service.authenticate_emergency_key(
                request.name, request.emergency_key_content
            )
            verified = success
        
        if not verified:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid recovery credentials"
            )
        
        # Reset password (this would need to be implemented in auth_service)
        success = await auth_service.reset_user_password(user['username'], request.new_password)
        
        if success:
            return {"message": "Password reset successful"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reset password"
            )
            
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Password reset failed: {str(e)}"
        )


@router.get("/session", response_model=SessionInfo)
async def get_session_info(request: Request):
    """Get current session information"""
    try:
        # Get session token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return SessionInfo(
                user=None,
                is_authenticated=False,
                session_active=False
            )
        
        session_token = auth_header.replace("Bearer ", "")
        auth_service = get_auth_service()
        is_valid, user = await auth_service.validate_session(session_token)
        
        return SessionInfo(
            user=UserResponse(**user) if user else None,
            is_authenticated=is_valid,
            session_active=is_valid
        )
        
    except Exception as e:
        return SessionInfo(
            user=None,
            is_authenticated=False,
            session_active=False
        )


@router.post("/change-password", response_model=ChangeCredentialsResponse)
async def change_password(request: ChangePasswordRequest):
    """Change user's password (requires current user session)"""
    try:
        auth_service = get_auth_service()
        db_manager = get_database_manager()
        
        # Get current user ID from active session
        if not db_manager.is_session_active():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No active session. Please login first."
            )
        
        current_user_id = db_manager.get_current_user_id()
        
        success, message = await auth_service.change_password(
            user_id=current_user_id,
            current_password=request.current_password,
            new_password=request.new_password
        )
        
        if success:
            return ChangeCredentialsResponse(success=True, message=message)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change password: {str(e)}"
        )


@router.post("/change-recovery-phrase", response_model=ChangeCredentialsResponse)
async def change_recovery_phrase(request: ChangeRecoveryPhraseRequest):
    """Change user's recovery phrase (requires current user session)"""
    try:
        auth_service = get_auth_service()
        db_manager = get_database_manager()
        
        # Get current user ID from active session
        if not db_manager.is_session_active():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No active session. Please login first."
            )
        
        current_user_id = db_manager.get_current_user_id()
        
        success, message = await auth_service.change_recovery_phrase(
            user_id=current_user_id,
            current_password=request.current_password,
            new_recovery_phrase=request.new_recovery_phrase
        )
        
        if success:
            return ChangeCredentialsResponse(success=True, message=message)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change recovery phrase: {str(e)}"
        )


@router.get("/status")
async def get_auth_status():
    """Check if authentication system is set up and if users exist"""
    try:
        user_registry = get_user_registry_service()
        
        # Check if registry database exists
        registry_exists = os.path.exists("app_data/shared/user_registry.db")
        
        users = []
        if registry_exists:
            try:
                users = await user_registry.list_users()
            except:
                pass
        
        return {
            "initialized": registry_exists,
            "has_users": len(users) > 0,
            "user_count": len(users),
            "requires_setup": not registry_exists or len(users) == 0
        }
        
    except Exception as e:
        return {
            "initialized": False,
            "has_users": False,
            "user_count": 0,
            "requires_setup": True,
            "error": str(e)
        }


@router.get("/stats", response_model=UserStatsResponse)
async def get_user_stats():
    """Get user statistics (admin/debug endpoint)"""
    try:
        user_registry = get_user_registry_service()
        users = await user_registry.list_users()
        
        # Simple stats for now
        return UserStatsResponse(
            total_users=len(users),
            active_users=len([u for u in users if u.get('is_active', True)]),
            locked_accounts=0,  # Would need additional query
            recent_registrations=0  # Would need date filtering
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}"
        )


# Development endpoints (only available in DEV_MODE)
@router.get("/user/credentials")
async def get_user_credentials(request: Request):
    """Get user's actual credentials (requires current password confirmation)"""
    try:
        auth_service = get_auth_service()
        db_manager = get_database_manager()
        
        # Get current user ID from active session
        if not db_manager.is_session_active():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No active session. Please login first."
            )
        
        current_user_id = db_manager.get_current_user_id()
        
        # Get password from query parameter (sent via prompt)
        current_password = request.query_params.get('current_password')
        if not current_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is required"
            )
        
        # Verify the current password
        user_data = await auth_service.get_user_credentials(current_user_id, current_password)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid password"
            )
            
        return {
            "password": user_data['password'],
            "recovery_phrase": user_data['recovery_phrase'],
            "emergency_key": user_data['emergency_key']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve credentials: {str(e)}"
        )


@router.post("/dev/reset")
async def dev_reset_auth(request: DevResetRequest):
    """DEVELOPMENT ONLY: Reset entire authentication system"""
    if not os.getenv('DEV_MODE', 'false').lower() == 'true':
        raise HTTPException(status_code=404, detail="Not found")
    
    if request.master_password != "dev_override_2024":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid master password"
        )
    
    try:
        # This would clear all auth data
        return {"message": "Development reset not yet implemented"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reset failed: {str(e)}"
        )


@router.post("/dev/create-test-user")
async def dev_create_test_user(request: DevTestUserRequest):
    """DEVELOPMENT ONLY: Create test user"""
    if not os.getenv('DEV_MODE', 'false').lower() == 'true':
        raise HTTPException(status_code=404, detail="Not found")
    
    try:
        auth_service = get_auth_service()
        
        result = await auth_service.register_user(
            name=request.display_name,
            password="test123456",
            recovery_phrase="test recovery phrase for development"
        )
        
        return {
            "message": "Test user created",
            "user": result['user'],
            "credentials": {
                "password": "test123456",
                "recovery_phrase": "test recovery phrase for development"
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test user creation failed: {str(e)}"
        )