import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass


@dataclass
class UserSession:
    """User session data structure"""
    session_id: str
    user_id: int
    username: str
    display_name: str
    created_at: datetime
    last_activity: datetime
    expires_at: datetime


class SessionManager:
    """In-memory session management for user authentication"""
    
    def __init__(self, session_duration_hours: int = 24):
        self.active_sessions: Dict[str, UserSession] = {}
        self.user_sessions: Dict[int, str] = {}  # user_id -> session_id mapping
        self.session_duration = timedelta(hours=session_duration_hours)
    
    def create_session(self, user_id: int, username: str, display_name: str) -> str:
        """Create new user session"""
        # End any existing session for this user
        self.end_user_session(user_id)
        
        session_id = str(uuid.uuid4())
        now = datetime.now()
        
        session = UserSession(
            session_id=session_id,
            user_id=user_id,
            username=username,
            display_name=display_name,
            created_at=now,
            last_activity=now,
            expires_at=now + self.session_duration
        )
        
        self.active_sessions[session_id] = session
        self.user_sessions[user_id] = session_id
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[UserSession]:
        """Get active session by session ID"""
        session = self.active_sessions.get(session_id)
        
        if not session:
            return None
        
        # Check if session has expired
        if datetime.now() > session.expires_at:
            self.end_session(session_id)
            return None
        
        # Update last activity
        session.last_activity = datetime.now()
        
        return session
    
    def get_user_session(self, user_id: int) -> Optional[UserSession]:
        """Get active session for a user"""
        session_id = self.user_sessions.get(user_id)
        if not session_id:
            return None
        
        return self.get_session(session_id)
    
    def validate_session(self, session_id: str) -> Tuple[bool, Optional[UserSession]]:
        """Validate session and return session data"""
        session = self.get_session(session_id)
        return (session is not None, session)
    
    def end_session(self, session_id: str) -> bool:
        """End a specific session"""
        session = self.active_sessions.pop(session_id, None)
        if session:
            # Remove from user sessions mapping
            self.user_sessions.pop(session.user_id, None)
            return True
        return False
    
    def end_user_session(self, user_id: int) -> bool:
        """End all sessions for a specific user"""
        session_id = self.user_sessions.get(user_id)
        if session_id:
            return self.end_session(session_id)
        return False
    
    def extend_session(self, session_id: str, hours: int = None) -> bool:
        """Extend session expiration"""
        session = self.active_sessions.get(session_id)
        if not session:
            return False
        
        if hours is None:
            hours = self.session_duration.total_seconds() / 3600
        
        session.expires_at = datetime.now() + timedelta(hours=hours)
        return True
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions"""
        now = datetime.now()
        expired_sessions = []
        
        for session_id, session in self.active_sessions.items():
            if now > session.expires_at:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            self.end_session(session_id)
        
        return len(expired_sessions)
    
    def get_active_sessions_count(self) -> int:
        """Get count of active sessions"""
        self.cleanup_expired_sessions()
        return len(self.active_sessions)
    
    def get_user_sessions_info(self) -> Dict[str, Any]:
        """Get summary of all active sessions"""
        self.cleanup_expired_sessions()
        
        sessions_info = []
        for session in self.active_sessions.values():
            sessions_info.append({
                "session_id": session.session_id,
                "user_id": session.user_id,
                "username": session.username,
                "display_name": session.display_name,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "expires_at": session.expires_at.isoformat()
            })
        
        return {
            "total_sessions": len(sessions_info),
            "sessions": sessions_info
        }
    
    def is_user_online(self, user_id: int) -> bool:
        """Check if user has an active session"""
        session = self.get_user_session(user_id)
        return session is not None


# Singleton instance
_session_manager = None

def get_session_manager() -> SessionManager:
    """Get singleton SessionManager instance"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager