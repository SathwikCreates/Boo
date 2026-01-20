import bcrypt
import uuid
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

from .user_registry_service import get_user_registry_service
from .database_manager import get_database_manager
from .session_manager import get_session_manager

logger = logging.getLogger(__name__)


class AuthenticationService:
    """Core authentication service with multiple authentication methods"""
    
    def __init__(self):
        self.user_registry = get_user_registry_service()
        self.db_manager = get_database_manager()
        self.session_manager = get_session_manager()
        self.max_failed_attempts = 5
        self.lockout_duration = 60  # minutes
    
    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def _verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash"""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception:
            return False
    
    def _generate_username(self, display_name: str) -> str:
        """Generate unique username from display name"""
        # Convert to lowercase, replace spaces with underscores
        base_username = display_name.lower().replace(' ', '_')
        # Remove non-alphanumeric characters except underscores
        base_username = ''.join(c for c in base_username if c.isalnum() or c == '_')
        # Ensure it starts with a letter
        if not base_username or not base_username[0].isalpha():
            base_username = f"user_{base_username}"
        
        return base_username[:50]  # Limit length
    
    def _generate_recovery_key(self) -> str:
        """Generate emergency recovery key"""
        return f"boo_{uuid.uuid4().hex}"
    
    def _create_emergency_key_file(self, username: str, display_name: str, recovery_key: str) -> str:
        """Create emergency key file content"""
        key_data = {
            "type": "boo_emergency_key",
            "key": recovery_key,
            "created": datetime.now().isoformat(),
            "username": username,
            "name": display_name
        }
        return json.dumps(key_data, indent=2)
    
    def _parse_emergency_key_file(self, file_content: str) -> Optional[Dict[str, Any]]:
        """Parse and validate emergency key file"""
        try:
            data = json.loads(file_content)
            if data.get("type") != "boo_emergency_key":
                return None
            if "key" not in data:
                return None
            return data
        except (json.JSONDecodeError, KeyError):
            return None
    
    async def register_user(
        self,
        name: str,
        password: str,
        recovery_phrase: str,
        emergency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Register a new user with all authentication methods"""
        
        # Generate username from display name
        username = self._generate_username(name)
        
        # Check if username already exists, add suffix if needed
        counter = 1
        original_username = username
        while await self.user_registry.user_exists(username):
            username = f"{original_username}_{counter}"
            counter += 1
        
        # Hash password and recovery phrase
        password_hash = self._hash_password(password)
        phrase_hash = self._hash_password(recovery_phrase) if recovery_phrase else None
        
        # Generate emergency key if not provided
        if not emergency_key:
            emergency_key = self._generate_recovery_key()
        
        # Create user database
        db_path = await self.db_manager.create_user_database(username)
        
        # Create user in registry
        user = await self.user_registry.create_user(
            username=username,
            display_name=name,
            password_hash=password_hash,
            secret_phrase_hash=phrase_hash,
            recovery_key=emergency_key,
            database_path=db_path
        )
        
        # Generate emergency key file content
        key_file_content = self._create_emergency_key_file(username, name, emergency_key)
        
        return {
            "user": user,
            "emergency_key_file": key_file_content,
            "filename": f"{username}_recovery.boounlock"
        }
    
    async def authenticate_password(self, name: str, password: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """Authenticate user with password"""
        
        # Find user by display name (convert to username)
        username = self._generate_username(name)
        user = await self.user_registry.get_user_by_username(username)
        
        if not user:
            return False, None, "Invalid credentials"
        
        # Check if account is locked
        if await self.user_registry.is_account_locked(user['id']):
            return False, None, "Account temporarily locked due to failed login attempts"
        
        # Verify password
        if not self._verify_password(password, user['password_hash']):
            # Increment failed attempts
            failed_count = await self.user_registry.increment_failed_attempts(user['id'])
            
            if failed_count >= self.max_failed_attempts:
                await self.user_registry.lock_account(user['id'], self.lockout_duration)
                return False, None, f"Account locked for {self.lockout_duration} minutes due to repeated failed attempts"
            
            return False, None, f"Invalid credentials ({self.max_failed_attempts - failed_count} attempts remaining)"
        
        # Reset failed attempts on successful login
        await self.user_registry.reset_failed_attempts(user['id'])
        await self.user_registry.update_last_login(user['id'])
        
        return True, user, "Authentication successful"
    
    async def authenticate_recovery_phrase(self, name: str, recovery_phrase: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """Authenticate user with recovery phrase"""
        
        # Find user by display name
        username = self._generate_username(name)
        user = await self.user_registry.get_user_by_username(username)
        
        if not user:
            return False, None, "Invalid credentials"
        
        if not user['secret_phrase_hash']:
            return False, None, "Recovery phrase not set for this account"
        
        # Check if account is locked
        if await self.user_registry.is_account_locked(user['id']):
            return False, None, "Account temporarily locked"
        
        # Verify recovery phrase
        if not self._verify_password(recovery_phrase, user['secret_phrase_hash']):
            # Increment failed attempts for recovery phrase too
            failed_count = await self.user_registry.increment_failed_attempts(user['id'])
            
            if failed_count >= self.max_failed_attempts:
                await self.user_registry.lock_account(user['id'], self.lockout_duration)
                return False, None, f"Account locked for {self.lockout_duration} minutes"
            
            return False, None, "Invalid recovery phrase"
        
        # Reset failed attempts on successful recovery
        await self.user_registry.reset_failed_attempts(user['id'])
        await self.user_registry.update_last_login(user['id'])
        
        return True, user, "Recovery phrase authentication successful"
    
    async def authenticate_emergency_key(self, name: str, key_file_content: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """Authenticate user with emergency key file"""
        
        # Parse emergency key file
        key_data = self._parse_emergency_key_file(key_file_content)
        if not key_data:
            return False, None, "Invalid emergency key file format"
        
        # Find user by display name
        username = self._generate_username(name)
        user = await self.user_registry.get_user_by_username(username)
        
        if not user:
            return False, None, "Invalid credentials"
        
        # Verify emergency key matches
        if key_data['key'] != user['recovery_key']:
            return False, None, "Invalid emergency key"
        
        # Verify username matches (additional security)
        if key_data.get('username') != user['username']:
            return False, None, "Emergency key does not match this account"
        
        # Emergency key bypasses account locks (it's emergency recovery)
        await self.user_registry.reset_failed_attempts(user['id'])
        await self.user_registry.update_last_login(user['id'])
        
        return True, user, "Emergency key authentication successful"
    
    async def create_session(self, user: Dict[str, Any]) -> str:
        """Create user session and switch database context"""
        
        # Switch database manager to this user
        await self.db_manager.switch_to_user(user['id'])
        
        # Create session in session manager
        session_token = self.session_manager.create_session(
            user_id=user['id'],
            username=user['username'],
            display_name=user['display_name']
        )
        
        # Start background memory processing for this user
        try:
            from .service_coordinator import get_service_coordinator
            coordinator = await get_service_coordinator()
            await coordinator.start_background_memory_processing_for_user()
        except Exception as e:
            # Don't fail login if background processing fails
            logger.error(f"Failed to start background memory processing for user: {e}")
        
        # Initialize hotkey service with user preferences
        try:
            from .service_coordinator import get_service_coordinator
            coordinator = await get_service_coordinator()
            await coordinator.initialize_hotkey_for_user()
        except Exception as e:
            # Don't fail login if hotkey initialization fails
            logger.error(f"Failed to initialize hotkey for user: {e}")
        
        # Trigger pattern detection for this user's database
        try:
            from .service_coordinator import get_service_coordinator
            coordinator = await get_service_coordinator()
            await coordinator.refresh_patterns_for_user()
        except Exception as e:
            # Don't fail login if pattern detection fails
            logger.error(f"Failed to refresh patterns after login: {e}")
        
        return session_token
    
    async def validate_session(self, session_token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Validate session token and return current user"""
        is_valid, session = self.session_manager.validate_session(session_token)
        
        if not is_valid or not session:
            return False, None
        
        # Get full user data from registry
        user = await self.user_registry.get_user_by_id(session.user_id)
        
        return is_valid, user
    
    async def logout(self, session_token: Optional[str] = None):
        """End current session"""
        if session_token:
            self.session_manager.end_session(session_token)
        
        # Clear database context
        await self.db_manager.clear_session()
    
    async def cleanup_expired_locks(self):
        """Clean up expired account locks"""
        await self.user_registry.cleanup_expired_locks()
    
    async def change_password(self, user_id: int, current_password: str, new_password: str) -> Tuple[bool, str]:
        """Change user password with current password verification"""
        user = await self.user_registry.get_user_by_id(user_id)
        if not user:
            return False, "User not found"
        
        # Verify current password
        if not self._verify_password(current_password, user['password_hash']):
            return False, "Current password is incorrect"
        
        # Hash new password
        new_hash = self._hash_password(new_password)
        
        # Update in database
        await self.user_registry.update_password_hash(user_id, new_hash)
        
        return True, "Password updated successfully"
    
    async def change_recovery_phrase(self, user_id: int, current_password: str, new_recovery_phrase: str) -> Tuple[bool, str]:
        """Change recovery phrase with password verification"""
        user = await self.user_registry.get_user_by_id(user_id)
        if not user:
            return False, "User not found"
        
        # Verify current password
        if not self._verify_password(current_password, user['password_hash']):
            return False, "Password is incorrect"
        
        # Hash new recovery phrase
        new_phrase_hash = self._hash_password(new_recovery_phrase)
        
        # Update in database
        await self.user_registry.update_secret_phrase_hash(user_id, new_phrase_hash)
        
        return True, "Recovery phrase updated successfully"
    
    async def get_user_credentials(self, user_id: int, current_password: str) -> Optional[Dict[str, str]]:
        """Get user's actual password after verifying current password (recovery phrase is hashed and cannot be retrieved)"""
        try:
            # Get user data from registry
            user = await self.user_registry.get_user_by_id(user_id)
            if not user:
                return None
            
            # Verify current password
            if not bcrypt.checkpw(current_password.encode('utf-8'), user['password_hash'].encode('utf-8')):
                return None
            
            # Return the verified password and emergency key
            # Note: Recovery phrase is hashed for security and cannot be retrieved
            return {
                'password': current_password,  # We verified this is correct
                'recovery_phrase': None,  # Cannot retrieve hashed recovery phrase
                'emergency_key': user.get('recovery_key')  # Return the actual emergency key
            }
            
        except Exception as e:
            logger.error(f"Failed to get user credentials: {str(e)}")
            return None
    
    # Development helper methods
    async def reset_user_password(self, username: str, new_password: str) -> bool:
        """Reset user password (for development/recovery)"""
        user = await self.user_registry.get_user_by_username(username)
        if not user:
            return False
        
        # Hash new password
        new_hash = self._hash_password(new_password)
        
        # Update in database
        await self.user_registry.update_password_hash(user['id'], new_hash)
        return True
    
    async def get_development_override(self) -> bool:
        """Check if development mode is enabled"""
        return os.getenv('DEV_MODE', 'false').lower() == 'true'


# Singleton instance
_auth_service = None

def get_auth_service() -> AuthenticationService:
    """Get singleton AuthenticationService instance"""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthenticationService()
    return _auth_service