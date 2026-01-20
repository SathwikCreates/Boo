"""
Main WebSocket manager integrating with STT service
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, Callable
from fastapi import WebSocket, WebSocketDisconnect
import json

from .connection_manager import ConnectionManager, Connection
from .message_protocol import (
    WebSocketMessage,
    MessageType,
    create_state_message,
    create_recording_started_message,
    create_recording_stopped_message,
    create_transcription_message,
    create_error_message,
    create_warning_message,
    parse_client_message
)
from app.services.stt import RecordingState

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Main WebSocket manager for STT communication"""
    
    def __init__(self):
        self.connection_manager = ConnectionManager()
        self.stt_service = None
        self.hotkey_service = None
        
        # Channels for different types of updates
        self.CHANNEL_STT = "stt"
        self.CHANNEL_TRANSCRIPTION = "transcription"
        self.CHANNEL_HOTKEY = "hotkey"
        self.CHANNEL_SYSTEM = "system"
        self.CHANNEL_PROCESSING = "processing"
        
        # State tracking
        self.current_recording_session: Optional[str] = None
        self.recording_start_time: Optional[float] = None
        
        # Callbacks
        self._state_change_handlers: Dict[str, Callable] = {}
    
    def set_stt_service(self, stt_service):
        """Set STT service reference"""
        self.stt_service = stt_service
        
        # Register STT callbacks
        if stt_service:
            stt_service.set_transcription_callback(self._on_transcription_result)
            stt_service.set_error_callback(self._on_stt_error)
            
            # Register with state manager
            state_manager = stt_service.state_manager
            if state_manager:
                state_manager.add_callback("websocket", self._on_state_change)
    
    def set_hotkey_service(self, hotkey_service):
        """Set hotkey service reference"""
        self.hotkey_service = hotkey_service
        
        # Register hotkey callbacks
        if hotkey_service:
            hotkey_service.set_callbacks(
                on_start=self._on_hotkey_recording_start,
                on_stop=self._on_hotkey_recording_stop,
                on_error=self._on_hotkey_error
            )
    
    async def handle_connection(self, websocket: WebSocket, client_info: Dict[str, Any] = None):
        """Handle a new WebSocket connection"""
        connection = await self.connection_manager.connect(websocket, client_info)
        
        # Auto-subscribe to STT channel
        connection.subscribe(self.CHANNEL_STT)
        connection.subscribe(self.CHANNEL_SYSTEM)
        
        try:
            # Send initial state
            if self.stt_service:
                current_state = self.stt_service.get_current_state()
                state_message = create_state_message(
                    state=current_state.value,
                    session_id=connection.session_id,
                    additional_data={
                        "service_ready": True,
                        "hotkey_enabled": self.hotkey_service.is_hotkey_active() if self.hotkey_service else False,
                        "current_hotkey": self.hotkey_service.get_current_hotkey() if self.hotkey_service else None
                    }
                )
                await connection.send_message(state_message)
            
            # Handle incoming messages
            while True:
                data = await websocket.receive_text()
                await self._handle_client_message(connection, data)
                
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: {connection.connection_id}")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            try:
                error_message = create_error_message(
                    error=str(e),
                    error_type="connection_error",
                    session_id=connection.session_id
                )
                await connection.send_message(error_message)
            except:
                pass
        finally:
            await self.connection_manager.disconnect(connection.connection_id)
    
    async def _handle_client_message(self, connection: Connection, message: str):
        """Handle incoming client message"""
        parsed = parse_client_message(message)
        if not parsed:
            await connection.send_message(
                create_error_message(
                    error="Invalid message format",
                    error_type="parse_error",
                    session_id=connection.session_id
                )
            )
            return
        
        message_type = parsed.get("type")
        data = parsed.get("data", {})
        
        # Handle different message types
        if message_type == MessageType.PING:
            # Respond with pong
            from .message_protocol import create_pong_message
            await connection.send_message(create_pong_message(connection.session_id))
        
        elif message_type == MessageType.COMMAND:
            await self._handle_command(connection, data)
        
        elif message_type == MessageType.STATE_CHANGE:
            # Client requesting state update
            if self.stt_service:
                current_state = self.stt_service.get_current_state()
                state_message = create_state_message(
                    state=current_state.value,
                    session_id=connection.session_id
                )
                await connection.send_message(state_message)
        
        else:
            # Unknown message type
            await connection.send_message(
                create_warning_message(
                    warning=f"Unknown message type: {message_type}",
                    warning_type="unknown_message",
                    session_id=connection.session_id
                )
            )
    
    async def _handle_command(self, connection: Connection, data: Dict[str, Any]):
        """Handle command from client"""
        command = data.get("command")
        parameters = data.get("parameters", {})
        
        if command == "start_recording":
            # Start recording via WebSocket command
            if self.stt_service:
                # Check current state before attempting to start
                current_state = self.stt_service.state_manager.get_state()
                if not self.stt_service.state_manager.can_start_recording():
                    # Don't send error for duplicate start commands - just ignore silently
                    logger.debug(f"Ignoring start_recording command - already in state: {current_state}")
                    return
                
                success = self.stt_service.start_recording()
                if not success:
                    await connection.send_message(
                        create_error_message(
                            error=f"Failed to start STT recording",
                            error_type="recording_error",
                            session_id=connection.session_id
                        )
                    )
        
        elif command == "stop_recording":
            # Stop recording via WebSocket command
            if self.stt_service:
                success = self.stt_service.stop_recording()
                if not success:
                    await connection.send_message(
                        create_error_message(
                            error="Failed to stop recording",
                            error_type="recording_error",
                            session_id=connection.session_id
                        )
                    )
        
        elif command == "reset_recording":
            # Reset recording pipeline - force reset to idle state
            logger.info("Received reset_recording command - performing pipeline reset")
            if self.stt_service:
                try:
                    # Force reset the entire audio system - this should fix stuck audio streams
                    if hasattr(self.stt_service, 'force_reset_audio'):
                        self.stt_service.force_reset_audio()
                        logger.info("STT audio system force reset completed")
                    else:
                        # Fallback to regular cancel
                        self.stt_service.cancel_recording()
                        logger.info("STT recording cancelled and state reset to idle")
                    
                    # Also reset hotkey service state
                    if self.hotkey_service and hasattr(self.hotkey_service, 'reset_recording_state'):
                        self.hotkey_service.reset_recording_state()
                        logger.info("Hotkey service recording state also reset")
                    
                    # Clear session tracking
                    self.current_recording_session = None
                    self.recording_start_time = None
                    
                    # Send confirmation back to client
                    success_message = create_state_message(
                        state="idle",
                        session_id=connection.session_id,
                        additional_data={
                            "message": "Recording pipeline reset successfully",
                            "reset_completed": True
                        }
                    )
                    await connection.send_message(success_message)
                    logger.info("Reset recording command completed successfully")
                    
                except Exception as e:
                    logger.error(f"Failed to reset recording pipeline: {e}")
                    await connection.send_message(
                        create_error_message(
                            error=f"Failed to reset recording pipeline: {str(e)}",
                            error_type="reset_error",
                            session_id=connection.session_id
                        )
                    )
        
        elif command == "subscribe":
            # Subscribe to additional channels
            channels = parameters.get("channels", [])
            for channel in channels:
                connection.subscribe(channel)
                logger.info(f"Connection {connection.connection_id} subscribed to {channel}")
        
        elif command == "unsubscribe":
            # Unsubscribe from channels
            channels = parameters.get("channels", [])
            for channel in channels:
                connection.unsubscribe(channel)
                logger.info(f"Connection {connection.connection_id} unsubscribed from {channel}")
        
        else:
            await connection.send_message(
                create_warning_message(
                    warning=f"Unknown command: {command}",
                    warning_type="unknown_command",
                    session_id=connection.session_id
                )
            )
    
    def _on_state_change(self, new_state: RecordingState):
        """Handle STT state change"""
        # Create state message
        state_message = create_state_message(
            state=new_state.value,
            additional_data={
                "state_message": self._get_state_message(new_state),
                "is_active": new_state not in [RecordingState.IDLE, RecordingState.SUCCESS, RecordingState.ERROR]
            }
        )
        
        # Broadcast to STT channel
        asyncio.create_task(
            self.connection_manager.broadcast_to_channel(
                self.CHANNEL_STT,
                state_message
            )
        )
        
        # Send specific messages for certain states
        if new_state == RecordingState.RECORDING:
            import time
            self.recording_start_time = time.time()
            self.current_recording_session = state_message.session_id
            
            recording_message = create_recording_started_message()
            asyncio.create_task(
                self.connection_manager.broadcast_to_channel(
                    self.CHANNEL_STT,
                    recording_message
                )
            )
        
        elif new_state in [RecordingState.PROCESSING, RecordingState.TRANSCRIBING]:
            if self.recording_start_time:
                import time
                duration = time.time() - self.recording_start_time
                
                recording_stopped_message = create_recording_stopped_message(
                    duration=duration
                )
                asyncio.create_task(
                    self.connection_manager.broadcast_to_channel(
                        self.CHANNEL_STT,
                        recording_stopped_message
                    )
                )
    
    def _on_transcription_result(self, result: Dict[str, Any]):
        """Handle transcription result from STT service"""
        # Create transcription message
        transcription_message = create_transcription_message(
            text=result.get("text", ""),
            language=result.get("language", "unknown"),
            confidence=result.get("confidence", 0.0),
            segments=result.get("segments", []),
            processing_time=result.get("processing_time")
        )
        
        # Broadcast to transcription channel
        asyncio.create_task(
            self.connection_manager.broadcast_to_channel(
                self.CHANNEL_TRANSCRIPTION,
                transcription_message
            )
        )
        
        # Also broadcast to STT channel
        asyncio.create_task(
            self.connection_manager.broadcast_to_channel(
                self.CHANNEL_STT,
                transcription_message
            )
        )
        
        # Reset session tracking
        self.current_recording_session = None
        self.recording_start_time = None
    
    def _on_stt_error(self, error: str):
        """Handle STT error"""
        error_message = create_error_message(
            error=error,
            error_type="stt_error",
            recoverable=True
        )
        
        asyncio.create_task(
            self.connection_manager.broadcast_to_channel(
                self.CHANNEL_STT,
                error_message
            )
        )
    
    def _on_hotkey_recording_start(self):
        """Handle hotkey-triggered recording start"""
        # Hotkey events are already handled by STT state changes
        pass
    
    def _on_hotkey_recording_stop(self):
        """Handle hotkey-triggered recording stop"""
        # Hotkey events are already handled by STT state changes
        pass
    
    def _on_hotkey_error(self, error: str):
        """Handle hotkey error"""
        error_message = create_error_message(
            error=error,
            error_type="hotkey_error",
            recoverable=True
        )
        
        asyncio.create_task(
            self.connection_manager.broadcast_to_channel(
                self.CHANNEL_HOTKEY,
                error_message
            )
        )
    
    def _get_state_message(self, state: RecordingState) -> str:
        """Get human-readable message for state"""
        messages = {
            RecordingState.IDLE: "Ready to record",
            RecordingState.RECORDING: "Recording in progress",
            RecordingState.PROCESSING: "Processing audio",
            RecordingState.TRANSCRIBING: "Transcribing audio",
            RecordingState.ENHANCING: "Enhancing transcription",
            RecordingState.SUCCESS: "Transcription complete",
            RecordingState.ERROR: "An error occurred"
        }
        return messages.get(state, "Unknown state")
    
    async def broadcast_system_message(self, message: str, message_type: str = "info"):
        """Broadcast system message to all connections"""
        system_message = WebSocketMessage(
            type=MessageType.STATE_CHANGE,
            data={
                "system_message": message,
                "message_type": message_type
            }
        )
        
        await self.connection_manager.broadcast_to_channel(
            self.CHANNEL_SYSTEM,
            system_message
        )
    
    async def broadcast_processing_status(self, job_data: Dict[str, Any]):
        """Broadcast processing job status update"""
        processing_message = WebSocketMessage(
            type=MessageType.STATE_CHANGE,
            data={
                "event": "processing_status_update",
                "job": job_data
            }
        )
        
        await self.connection_manager.broadcast_to_channel(
            self.CHANNEL_PROCESSING,
            processing_message
        )
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get WebSocket connection statistics"""
        return {
            "total_connections": self.connection_manager.get_connection_count(),
            "stt_subscribers": len(self.connection_manager.get_channel_subscribers(self.CHANNEL_STT)),
            "transcription_subscribers": len(self.connection_manager.get_channel_subscribers(self.CHANNEL_TRANSCRIPTION)),
            "hotkey_subscribers": len(self.connection_manager.get_channel_subscribers(self.CHANNEL_HOTKEY)),
            "active_recording": self.current_recording_session is not None
        }
    
    def on_stt_state_change(self, new_state: RecordingState):
        """Callback for STT state changes"""
        logger.info(f"WebSocket manager received STT state change: {new_state.value}")
        
        # Create state message
        state_message = create_state_message(
            state=new_state.value,
            additional_data={
                "message": self._get_state_message(new_state),
                "timestamp": time.time()
            }
        )
        
        # Broadcast to STT channel
        try:
            asyncio.create_task(
                self.connection_manager.broadcast_to_channel(
                    self.CHANNEL_STT,
                    state_message
                )
            )
        except Exception as e:
            logger.error(f"Failed to broadcast STT state change: {e}")
    
    def on_transcription_result(self, result: Dict[str, Any]):
        """Callback for transcription results"""
        logger.info(f"WebSocket manager received transcription result: {result.get('text', 'NO TEXT') if result else 'NO RESULT'}")
        
        # Create transcription message
        transcription_message = create_transcription_message(
            text=result.get("text", ""),
            language=result.get("language", "unknown"),
            confidence=result.get("confidence", 0.0),
            segments=result.get("segments", []),
            processing_time=result.get("processing_time")
        )
        
        # Broadcast to transcription channel
        try:
            asyncio.create_task(
                self.connection_manager.broadcast_to_channel(
                    self.CHANNEL_TRANSCRIPTION,
                    transcription_message
                )
            )
        except Exception as e:
            logger.error(f"Failed to broadcast transcription result: {e}")
    
    def on_stt_error(self, error: str):
        """Callback for STT errors"""
        logger.error(f"WebSocket manager received STT error: {error}")
        
        # Create error message
        error_message = create_error_message(
            error=error,
            error_type="stt_error",
            recoverable=True
        )
        
        # Broadcast to STT channel
        try:
            asyncio.create_task(
                self.connection_manager.broadcast_to_channel(
                    self.CHANNEL_STT,
                    error_message
                )
            )
        except Exception as e:
            logger.error(f"Failed to broadcast STT error: {e}")
    
    async def cleanup(self):
        """Clean up WebSocket manager"""
        await self.connection_manager.cleanup()
        logger.info("WebSocketManager cleaned up")


# Global WebSocket manager instance
_websocket_manager: Optional[WebSocketManager] = None


async def get_websocket_manager() -> WebSocketManager:
    """Get global WebSocket manager instance"""
    global _websocket_manager
    
    if _websocket_manager is None:
        _websocket_manager = WebSocketManager()
    
    return _websocket_manager