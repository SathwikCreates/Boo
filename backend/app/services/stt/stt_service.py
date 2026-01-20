import asyncio
import logging
from typing import Optional, Dict, Any, Callable
import tempfile
import os

from .audio_capture import AudioCapture
from .whisper_service import WhisperService
from .recording_states import RecordingState, StateManager, get_state_manager
from app.core.config import settings

logger = logging.getLogger(__name__)


class STTService:
    """Main STT service coordinating audio capture and transcription"""
    
    def __init__(self):
        self.audio_capture = AudioCapture(
            target_sample_rate=16000,  # Whisper target rate
            chunk_size=1024,
            channels=1
        )
        self.whisper_service = WhisperService()
        self.state_manager = get_state_manager()
        
        # Current recording session data
        self.current_session = None
        
        # Callbacks
        self.transcription_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self.error_callback: Optional[Callable[[str], None]] = None
        self.state_callback: Optional[Callable[[RecordingState], None]] = None
        
        # Setup state callbacks
        self._setup_state_callbacks()
        
    def _setup_state_callbacks(self):
        """Setup state change callbacks"""
        # Audio capture state callback
        self.audio_capture.set_state_callback(self._on_audio_state_change)
        
        # Whisper service state callback  
        self.whisper_service.set_state_callback(self._on_whisper_state_change)
        
        # State manager callback
        self.state_manager.add_callback("stt_service", self._on_state_change)
    
    def _on_audio_state_change(self, state: str):
        """Handle audio capture state changes"""
        if state == "recording":
            self.state_manager.set_state(RecordingState.RECORDING)
        elif state == "processing":
            self.state_manager.set_state(RecordingState.PROCESSING)
    
    def _on_whisper_state_change(self, state: str):
        """Handle Whisper service state changes"""
        if state == "transcribing":
            self.state_manager.set_state(RecordingState.TRANSCRIBING)
    
    def _on_state_change(self, new_state: RecordingState):
        """Handle state manager changes"""
        logger.info(f"STT Service state: {new_state.value}")
        
        # Notify external callback if set
        if self.state_callback:
            self.state_callback(new_state)
    
    async def initialize(self) -> bool:
        """Initialize STT service"""
        try:
            # Initialize audio capture
            if not self.audio_capture.initialize():
                logger.error("Failed to initialize audio capture")
                return False
            
            logger.info("STT Service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize STT service: {e}")
            return False
    
    def set_transcription_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set callback for transcription results"""
        self.transcription_callback = callback
    
    def set_error_callback(self, callback: Callable[[str], None]):
        """Set callback for errors"""
        self.error_callback = callback
    
    def set_callbacks(self, 
                     transcription_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
                     error_callback: Optional[Callable[[str], None]] = None,
                     state_callback: Optional[Callable[[RecordingState], None]] = None):
        """Set multiple callbacks at once"""
        if transcription_callback:
            self.transcription_callback = transcription_callback
        if error_callback:
            self.error_callback = error_callback
        if state_callback:
            self.state_callback = state_callback
    
    def start_recording(self) -> bool:
        """Start audio recording"""
        if not self.state_manager.can_start_recording():
            logger.warning(f"Cannot start recording in state: {self.state_manager.get_state()}")
            return False
        
        try:
            # Reset state to IDLE if coming from SUCCESS or ERROR
            current_state = self.state_manager.get_state()
            if current_state in {RecordingState.SUCCESS, RecordingState.ERROR}:
                self.state_manager.set_state(RecordingState.IDLE)
            
            # Start new session
            self.current_session = {
                "start_time": None,  # Could add timestamp
                "audio_data": None,
                "transcription": None
            }
            
            # Start audio capture
            success = self.audio_capture.start_recording()
            
            if not success:
                self.state_manager.set_state(RecordingState.ERROR)
                if self.error_callback:
                    self.error_callback("Failed to start audio recording")
                return False
            
            logger.info("STT recording started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start STT recording: {e}")
            self.state_manager.set_state(RecordingState.ERROR)
            if self.error_callback:
                self.error_callback(f"Recording error: {str(e)}")
            return False
    
    def stop_recording(self) -> bool:
        """Stop audio recording and start transcription"""
        if not self.state_manager.can_stop_recording():
            logger.warning(f"Cannot stop recording in state: {self.state_manager.get_state()}")
            return False
        
        try:
            # Stop audio capture
            audio_data = self.audio_capture.stop_recording()
            
            if not audio_data:
                logger.error("No audio data captured")
                self.state_manager.set_state(RecordingState.ERROR)
                if self.error_callback:
                    self.error_callback("No audio data captured")
                return False
            
            # Store audio data in session
            if self.current_session:
                self.current_session["audio_data"] = audio_data
            
            # Start transcription in background
            asyncio.create_task(self._process_transcription(audio_data))
            
            logger.info("STT recording stopped, transcription started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop STT recording: {e}")
            self.state_manager.set_state(RecordingState.ERROR)
            if self.error_callback:
                self.error_callback(f"Stop recording error: {str(e)}")
            return False
    
    async def _process_transcription(self, audio_data: bytes):
        """Process transcription in background"""
        try:
            # Convert audio data to numpy array with automatic resampling for Whisper
            audio_np = self.audio_capture.convert_to_numpy(audio_data, resample_for_whisper=True)
            
            if audio_np is None:
                raise Exception("Failed to convert audio data")
            
            # Transcribe using Whisper (audio is already resampled to 16kHz)
            result = self.whisper_service.transcribe_audio(audio_np)
            
            if not result:
                raise Exception("Transcription failed")
            
            # Store result in session
            if self.current_session:
                self.current_session["transcription"] = result
            
            # Notify success
            self.state_manager.set_state(RecordingState.SUCCESS)
            
            # Call transcription callback
            if self.transcription_callback:
                logger.info(f"Calling transcription callback with result: {result.get('text', 'NO TEXT') if result else 'NO RESULT'}")
                self.transcription_callback(result)
            else:
                logger.warning("No transcription callback set!")
            
            logger.info("Transcription completed successfully")
            
            # Reset to idle after brief delay
            await asyncio.sleep(0.5)
            self.state_manager.reset()
            
        except Exception as e:
            logger.error(f"Transcription processing failed: {e}")
            self.state_manager.set_state(RecordingState.ERROR)
            
            if self.error_callback:
                self.error_callback(f"Transcription error: {str(e)}")
            
            # Reset to idle after error
            await asyncio.sleep(0.5)
            self.state_manager.reset()
    
    def get_current_state(self) -> RecordingState:
        """Get current recording state"""
        return self.state_manager.get_state()
    
    def get_state_info(self) -> dict:
        """Get detailed state information"""
        base_info = self.state_manager.get_state_info()
        
        # Add service-specific info
        base_info.update({
            "whisper_model": self.whisper_service.get_model_info(),
            "audio_devices": self.audio_capture.get_input_devices(),
            "sample_rate_info": self.audio_capture.get_sample_rate_info(),
            "current_session": {
                "active": self.current_session is not None,
                "has_audio": self.current_session and self.current_session.get("audio_data") is not None,
                "has_transcription": self.current_session and self.current_session.get("transcription") is not None
            } if self.current_session else None
        })
        
        return base_info
    
    def cancel_recording(self) -> bool:
        """Cancel current recording"""
        try:
            if self.state_manager.get_state() == RecordingState.RECORDING:
                self.audio_capture.stop_recording()
            
            self.current_session = None
            self.state_manager.reset()
            
            logger.info("Recording cancelled")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel recording: {e}")
            return False
    
    def force_reset_audio(self) -> bool:
        """Force reset the entire audio system - use when stuck"""
        try:
            logger.info("STT Service: Force resetting audio system...")
            
            # Cancel any recording first
            self.cancel_recording()
            
            # Force reset audio capture system
            success = self.audio_capture.force_reset()
            
            if success:
                logger.info("STT Service: Audio system force reset successful")
            else:
                logger.error("STT Service: Audio system force reset failed")
            
            return success
            
        except Exception as e:
            logger.error(f"STT Service: Force reset failed: {e}")
            return False
    
    def save_last_recording(self, filepath: str) -> bool:
        """Save last recorded audio to file"""
        if not self.current_session or not self.current_session.get("audio_data"):
            return False
        
        try:
            return self.audio_capture.save_audio_to_file(
                self.current_session["audio_data"],
                filepath,
                use_target_rate=True  # Save as 16kHz for Whisper compatibility
            )
        except Exception as e:
            logger.error(f"Failed to save recording: {e}")
            return False
    
    def get_last_transcription(self) -> Optional[Dict[str, Any]]:
        """Get last transcription result"""
        if self.current_session:
            return self.current_session.get("transcription")
        return None
    
    def cleanup(self):
        """Clean up STT service resources"""
        try:
            # Cancel any active recording
            if self.state_manager.is_active():
                self.cancel_recording()
            
            # Cleanup components
            self.audio_capture.cleanup()
            self.whisper_service.cleanup()
            
            # Clear session
            self.current_session = None
            
            logger.info("STT Service cleaned up")
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")


# Global STT service instance
_stt_service: Optional[STTService] = None


async def get_stt_service() -> STTService:
    """Get global STT service instance"""
    global _stt_service
    
    if _stt_service is None:
        _stt_service = STTService()
        await _stt_service.initialize()
    
    return _stt_service