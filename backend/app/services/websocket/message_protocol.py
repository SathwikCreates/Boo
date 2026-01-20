"""
WebSocket message protocol for STT communication
"""

from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime
import json
from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """WebSocket message types"""
    # Connection messages
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    PING = "ping"
    PONG = "pong"
    
    # STT state messages
    STATE_CHANGE = "state_change"
    RECORDING_STARTED = "recording_started"
    RECORDING_STOPPED = "recording_stopped"
    PROCESSING_STARTED = "processing_started"
    TRANSCRIBING_STARTED = "transcribing_started"
    
    # Result messages
    TRANSCRIPTION_RESULT = "transcription_result"
    TRANSCRIPTION_PARTIAL = "transcription_partial"
    
    # Error messages
    ERROR = "error"
    WARNING = "warning"
    
    # Control messages
    COMMAND = "command"
    CONFIG_UPDATE = "config_update"


class WebSocketMessage(BaseModel):
    """Base WebSocket message structure"""
    type: MessageType
    timestamp: datetime = Field(default_factory=datetime.now)
    data: Dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[str] = None
    message_id: Optional[str] = None
    
    def to_json(self) -> str:
        """Convert message to JSON string"""
        return json.dumps({
            "type": self.type.value,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "session_id": self.session_id,
            "message_id": self.message_id
        })
    
    @classmethod
    def from_json(cls, json_str: str) -> "WebSocketMessage":
        """Create message from JSON string"""
        data = json.loads(json_str)
        data["type"] = MessageType(data["type"])
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


def create_state_message(
    state: str,
    session_id: Optional[str] = None,
    additional_data: Optional[Dict[str, Any]] = None
) -> WebSocketMessage:
    """Create a state change message"""
    data = {
        "state": state,
        "state_message": f"State changed to {state}"
    }
    
    if additional_data:
        data.update(additional_data)
    
    return WebSocketMessage(
        type=MessageType.STATE_CHANGE,
        data=data,
        session_id=session_id
    )


def create_recording_started_message(
    session_id: Optional[str] = None,
    device_info: Optional[Dict[str, Any]] = None
) -> WebSocketMessage:
    """Create recording started message"""
    data = {
        "status": "recording",
        "message": "Recording started"
    }
    
    if device_info:
        data["device_info"] = device_info
    
    return WebSocketMessage(
        type=MessageType.RECORDING_STARTED,
        data=data,
        session_id=session_id
    )


def create_recording_stopped_message(
    session_id: Optional[str] = None,
    duration: Optional[float] = None,
    audio_size: Optional[int] = None
) -> WebSocketMessage:
    """Create recording stopped message"""
    data = {
        "status": "stopped",
        "message": "Recording stopped"
    }
    
    if duration is not None:
        data["duration"] = duration
    
    if audio_size is not None:
        data["audio_size"] = audio_size
    
    return WebSocketMessage(
        type=MessageType.RECORDING_STOPPED,
        data=data,
        session_id=session_id
    )


def create_transcription_message(
    text: str,
    language: str,
    confidence: float,
    segments: list,
    session_id: Optional[str] = None,
    is_partial: bool = False,
    processing_time: Optional[float] = None
) -> WebSocketMessage:
    """Create transcription result message"""
    data = {
        "text": text,
        "language": language,
        "confidence": confidence,
        "segments": segments,
        "is_final": not is_partial
    }
    
    if processing_time is not None:
        data["processing_time"] = processing_time
    
    message_type = MessageType.TRANSCRIPTION_PARTIAL if is_partial else MessageType.TRANSCRIPTION_RESULT
    
    return WebSocketMessage(
        type=message_type,
        data=data,
        session_id=session_id
    )


def create_error_message(
    error: str,
    error_type: str = "general",
    session_id: Optional[str] = None,
    recoverable: bool = True,
    details: Optional[Dict[str, Any]] = None
) -> WebSocketMessage:
    """Create error message"""
    data = {
        "error": error,
        "error_type": error_type,
        "recoverable": recoverable
    }
    
    if details:
        data["details"] = details
    
    return WebSocketMessage(
        type=MessageType.ERROR,
        data=data,
        session_id=session_id
    )


def create_warning_message(
    warning: str,
    warning_type: str = "general",
    session_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> WebSocketMessage:
    """Create warning message"""
    data = {
        "warning": warning,
        "warning_type": warning_type
    }
    
    if details:
        data["details"] = details
    
    return WebSocketMessage(
        type=MessageType.WARNING,
        data=data,
        session_id=session_id
    )


def create_ping_message(session_id: Optional[str] = None) -> WebSocketMessage:
    """Create ping message for connection keep-alive"""
    return WebSocketMessage(
        type=MessageType.PING,
        data={"message": "ping"},
        session_id=session_id
    )


def create_pong_message(session_id: Optional[str] = None) -> WebSocketMessage:
    """Create pong response message"""
    return WebSocketMessage(
        type=MessageType.PONG,
        data={"message": "pong"},
        session_id=session_id
    )


def create_command_message(
    command: str,
    parameters: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None
) -> WebSocketMessage:
    """Create command message"""
    data = {
        "command": command,
        "parameters": parameters or {}
    }
    
    return WebSocketMessage(
        type=MessageType.COMMAND,
        data=data,
        session_id=session_id
    )


def parse_client_message(message: str) -> Optional[Dict[str, Any]]:
    """Parse incoming client message"""
    try:
        data = json.loads(message)
        
        # Validate required fields
        if "type" not in data:
            return None
        
        # Convert type to enum if valid
        try:
            data["type"] = MessageType(data["type"])
        except ValueError:
            return None
        
        return data
        
    except json.JSONDecodeError:
        return None
    except Exception:
        return None