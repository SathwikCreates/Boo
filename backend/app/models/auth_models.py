from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime


class UserRegistrationRequest(BaseModel):
    """Request model for user registration"""
    name: str = Field(..., min_length=1, max_length=100, description="User's display name")
    password: str = Field(..., min_length=8, max_length=128, description="User's password")
    recovery_phrase: str = Field(..., min_length=10, max_length=500, description="User's recovery phrase")
    emergency_key: Optional[str] = Field(None, description="Optional pre-generated emergency key")
    
    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('Name cannot be empty or whitespace only')
        return v.strip()
    
    @validator('recovery_phrase')
    def validate_recovery_phrase(cls, v):
        if not v.strip():
            raise ValueError('Recovery phrase cannot be empty')
        return v.strip()


class LoginRequest(BaseModel):
    """Request model for user login"""
    name: str = Field(..., min_length=1, max_length=100, description="User's display name")
    password: Optional[str] = Field(None, min_length=8, max_length=128, description="User's password")
    recovery_phrase: Optional[str] = Field(None, min_length=10, max_length=500, description="Recovery phrase")
    emergency_key_content: Optional[str] = Field(None, description="Emergency key file content")
    
    @validator('name')
    def validate_name(cls, v):
        return v.strip()
    
    def validate_auth_method(self):
        """Ensure exactly one authentication method is provided"""
        methods = [
            bool(self.password),
            bool(self.recovery_phrase),
            bool(self.emergency_key_content)
        ]
        
        if sum(methods) != 1:
            raise ValueError("Exactly one authentication method must be provided")
        
        return True


class UserResponse(BaseModel):
    """Response model for user information"""
    id: int
    username: str
    display_name: str
    created_at: datetime
    last_login: Optional[datetime]
    is_active: bool
    
    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Response model for user list"""
    id: int
    username: str
    display_name: str
    created_at: datetime
    last_login: Optional[datetime]
    
    class Config:
        from_attributes = True


class RegistrationResponse(BaseModel):
    """Response model for successful registration"""
    user: UserResponse
    emergency_key_file: str = Field(..., description="Emergency key file content")
    filename: str = Field(..., description="Suggested filename for emergency key")
    message: str = "Registration successful"


class LoginResponse(BaseModel):
    """Response model for successful login"""
    user: UserResponse
    session_token: str
    message: str


class AuthenticationError(BaseModel):
    """Error response model for authentication failures"""
    error: str
    code: str
    details: Optional[str] = None


class SessionInfo(BaseModel):
    """Response model for session information"""
    user: Optional[UserResponse]
    is_authenticated: bool
    session_active: bool


class RecoveryPhraseRequest(BaseModel):
    """Request model for recovery phrase validation"""
    name: str = Field(..., description="User's display name")
    recovery_phrase: str = Field(..., min_length=10, description="Recovery phrase to validate")


class EmergencyKeyRequest(BaseModel):
    """Request model for emergency key validation"""
    name: str = Field(..., description="User's display name")
    key_file_content: str = Field(..., description="Emergency key file content")


class PasswordResetRequest(BaseModel):
    """Request model for password reset"""
    name: str = Field(..., description="User's display name")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")
    recovery_phrase: Optional[str] = Field(None, description="Recovery phrase for verification")
    emergency_key_content: Optional[str] = Field(None, description="Emergency key for verification")
    
    def validate_verification_method(self):
        """Ensure at least one verification method is provided"""
        methods = [
            bool(self.recovery_phrase),
            bool(self.emergency_key_content)
        ]
        
        if sum(methods) == 0:
            raise ValueError("Recovery phrase or emergency key must be provided for password reset")
        
        return True


class ChangePasswordRequest(BaseModel):
    """Request model for changing password"""
    current_password: str = Field(..., min_length=8, max_length=128, description="Current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")
    
    @validator('new_password')
    def validate_new_password(cls, v, values):
        if 'current_password' in values and v == values['current_password']:
            raise ValueError('New password must be different from current password')
        return v


class ChangeRecoveryPhraseRequest(BaseModel):
    """Request model for changing recovery phrase"""
    current_password: str = Field(..., min_length=8, max_length=128, description="Current password for verification")
    new_recovery_phrase: str = Field(..., min_length=10, max_length=500, description="New recovery phrase")
    
    @validator('new_recovery_phrase')
    def validate_recovery_phrase(cls, v):
        if not v.strip():
            raise ValueError('Recovery phrase cannot be empty')
        return v.strip()


class ChangeCredentialsResponse(BaseModel):
    """Response model for credential changes"""
    success: bool
    message: str


class UserStatsResponse(BaseModel):
    """Response model for user statistics"""
    total_users: int
    active_users: int
    locked_accounts: int
    recent_registrations: int  # Last 7 days


# Development/Debug Models
class DevResetRequest(BaseModel):
    """Development-only request model for resetting auth system"""
    confirm: bool = Field(..., description="Confirmation flag")
    master_password: str = Field(..., description="Master password for dev reset")


class DevTestUserRequest(BaseModel):
    """Development-only request model for creating test user"""
    username: str = Field(..., description="Test username")
    display_name: str = Field(..., description="Test display name")
    skip_validation: bool = Field(False, description="Skip normal validation")