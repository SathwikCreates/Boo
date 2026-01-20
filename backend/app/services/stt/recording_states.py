from enum import Enum
from typing import Dict, Optional, Callable
import logging

logger = logging.getLogger(__name__)


class RecordingState(Enum):
    """Recording states for STT process"""
    IDLE = "idle"
    RECORDING = "recording" 
    PROCESSING = "processing"
    TRANSCRIBING = "transcribing"
    ENHANCING = "enhancing"
    SUCCESS = "success"
    ERROR = "error"


class StateManager:
    """Manager for recording state transitions"""
    
    def __init__(self):
        self.current_state = RecordingState.IDLE
        self.state_callbacks: Dict[str, Callable[[RecordingState], None]] = {}
        self.state_history = []
        
    def add_callback(self, name: str, callback: Callable[[RecordingState], None]):
        """Add state change callback"""
        self.state_callbacks[name] = callback
        
    def remove_callback(self, name: str):
        """Remove state change callback"""
        if name in self.state_callbacks:
            del self.state_callbacks[name]
    
    def set_state(self, new_state: RecordingState, metadata: Optional[dict] = None):
        """Set new recording state"""
        if new_state == self.current_state:
            return
        
        old_state = self.current_state
        self.current_state = new_state
        
        # Add to history
        self.state_history.append({
            "from": old_state,
            "to": new_state,
            "metadata": metadata or {},
            "timestamp": None  # Could add timestamp if needed
        })
        
        # Keep history limited
        if len(self.state_history) > 50:
            self.state_history = self.state_history[-50:]
        
        logger.info(f"State changed: {old_state.value} -> {new_state.value}")
        
        # Notify callbacks
        for name, callback in self.state_callbacks.items():
            try:
                callback(new_state)
            except Exception as e:
                logger.error(f"State callback '{name}' failed: {e}")
    
    def get_state(self) -> RecordingState:
        """Get current state"""
        return self.current_state
    
    def is_active(self) -> bool:
        """Check if recording is in an active state"""
        active_states = {
            RecordingState.RECORDING,
            RecordingState.PROCESSING,
            RecordingState.TRANSCRIBING,
            RecordingState.ENHANCING
        }
        return self.current_state in active_states
    
    def can_start_recording(self) -> bool:
        """Check if recording can be started"""
        return self.current_state in {RecordingState.IDLE, RecordingState.SUCCESS, RecordingState.ERROR}
    
    def can_stop_recording(self) -> bool:
        """Check if recording can be stopped"""
        return self.current_state == RecordingState.RECORDING
    
    def reset(self):
        """Reset to idle state"""
        self.set_state(RecordingState.IDLE)
    
    def get_state_info(self) -> dict:
        """Get detailed state information"""
        return {
            "current_state": self.current_state.value,
            "is_active": self.is_active(),
            "can_start": self.can_start_recording(),
            "can_stop": self.can_stop_recording(),
            "history_count": len(self.state_history)
        }
    
    def get_state_message(self) -> str:
        """Get human-readable state message"""
        messages = {
            RecordingState.IDLE: "Ready to record",
            RecordingState.RECORDING: "Recording audio...",
            RecordingState.PROCESSING: "Processing audio...",
            RecordingState.TRANSCRIBING: "Converting speech to text...",
            RecordingState.ENHANCING: "Creating enhanced versions...",
            RecordingState.SUCCESS: "Entry created successfully!",
            RecordingState.ERROR: "An error occurred"
        }
        return messages.get(self.current_state, "Unknown state")
    
    def get_state_icon(self) -> str:
        """Get icon representation for current state"""
        icons = {
            RecordingState.IDLE: "⭕",
            RecordingState.RECORDING: "🔴",
            RecordingState.PROCESSING: "⚙️",
            RecordingState.TRANSCRIBING: "📝",
            RecordingState.ENHANCING: "✨",
            RecordingState.SUCCESS: "✅",
            RecordingState.ERROR: "❌"
        }
        return icons.get(self.current_state, "❓")
    
    def get_recent_history(self, count: int = 10) -> list:
        """Get recent state history"""
        return self.state_history[-count:] if self.state_history else []


# Global state manager instance
recording_state_manager = StateManager()


def get_state_manager() -> StateManager:
    """Get global state manager instance"""
    return recording_state_manager