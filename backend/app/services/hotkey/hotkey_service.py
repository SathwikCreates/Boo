"""
Hotkey service that integrates with STT and preferences
"""

import asyncio
import logging
from typing import Optional, Dict, Any, Callable
import threading

from .hotkey_manager import HotkeyManager
from .key_validator import validate_hotkey
from app.core.config import settings

logger = logging.getLogger(__name__)


class HotkeyService:
    """Main hotkey service integrating with STT and preferences"""
    
    def __init__(self):
        self.manager = HotkeyManager()
        self.stt_service = None  # Will be set later to avoid circular imports
        self.preferences_repo = None  # Will be set later
        
        # Current hotkey configuration
        self.current_hotkey = settings.DEFAULT_HOTKEY
        self.hotkey_registered = False
        
        # Recording state
        self.is_recording = False
        self.recording_lock = threading.Lock()
        
        # Callbacks
        self.on_recording_start: Optional[Callable[[], None]] = None
        self.on_recording_stop: Optional[Callable[[], None]] = None
        self.on_recording_error: Optional[Callable[[str], None]] = None
        
    async def initialize(self) -> bool:
        """Initialize the hotkey service"""
        try:
            # Load hotkey configuration from preferences first
            await self._load_hotkey_preference()
            
            # Try to start the hotkey manager (may fail in test environments)
            try:
                if not self.manager.start():
                    logger.warning("Failed to start hotkey manager - continuing without global hotkeys")
                else:
                    logger.info("Hotkey manager started successfully")
                    
                    # Register the default STT hotkey only if manager started
                    if not await self._register_stt_hotkey():
                        logger.warning("Failed to register STT hotkey - API still available")
            except Exception as e:
                logger.warning(f"Hotkey manager initialization failed: {e} - API still available")
            
            logger.info("Hotkey service initialized (API available)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize hotkey service: {e}")
            return False
    
    def set_stt_service(self, stt_service):
        """Set the STT service reference (to avoid circular imports)"""
        self.stt_service = stt_service
    
    def set_preferences_repository(self, preferences_repo):
        """Set the preferences repository"""
        self.preferences_repo = preferences_repo
    
    def set_callbacks(self, 
                     on_start: Optional[Callable[[], None]] = None,
                     on_stop: Optional[Callable[[], None]] = None,
                     on_error: Optional[Callable[[str], None]] = None):
        """Set callback functions for recording events"""
        self.on_recording_start = on_start
        self.on_recording_stop = on_stop
        self.on_recording_error = on_error
    
    async def _load_hotkey_preference(self):
        """Load hotkey configuration from preferences"""
        try:
            if self.preferences_repo:
                hotkey_pref = await self.preferences_repo.get_by_key("hotkey")
                if hotkey_pref:
                    self.current_hotkey = hotkey_pref.get_typed_value()
                    logger.info(f"Loaded hotkey preference: {self.current_hotkey}")
                else:
                    # Set default preference
                    await self.preferences_repo.set_value(
                        key="hotkey",
                        value=self.current_hotkey,
                        value_type="string",
                        description="Global hotkey for voice recording"
                    )
                    logger.info(f"Created default hotkey preference: {self.current_hotkey}")
        except Exception as e:
            logger.warning(f"Failed to load hotkey preference: {e}")
            # Continue with default
    
    async def _register_stt_hotkey(self) -> bool:
        """Register the STT recording hotkey"""
        try:
            # Unregister existing hotkey if any
            if self.hotkey_registered:
                self.manager.unregister_hotkey("stt_recording")
                self.hotkey_registered = False
            
            # Register new hotkey
            success = self.manager.register_hotkey(
                hotkey_id="stt_recording",
                hotkey_str=self.current_hotkey,
                on_hold_start=self._on_recording_start,
                on_hold_end=self._on_recording_end,
                hold_mode=True
            )
            
            if success:
                self.hotkey_registered = True
                logger.info(f"Registered STT hotkey: {self.current_hotkey}")
            else:
                logger.error(f"Failed to register STT hotkey: {self.current_hotkey}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error registering STT hotkey: {e}")
            return False
    
    def _on_recording_start(self):
        """Handle recording start (called from hotkey thread)"""
        def async_start():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._async_recording_start())
            finally:
                loop.close()
        
        threading.Thread(target=async_start, daemon=True).start()
    
    def _on_recording_end(self, duration: float):
        """Handle recording end (called from hotkey thread)"""
        def async_end():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._async_recording_end(duration))
            finally:
                loop.close()
        
        threading.Thread(target=async_end, daemon=True).start()
    
    async def _async_recording_start(self):
        """Async handler for recording start"""
        with self.recording_lock:
            if self.is_recording:
                logger.warning("Recording already in progress")
                return
            
            try:
                if not self.stt_service:
                    raise Exception("STT service not available")
                
                # Check if we can start recording before attempting
                if not self.stt_service.state_manager.can_start_recording():
                    logger.debug(f"Ignoring hotkey start - already in state: {self.stt_service.state_manager.get_state()}")
                    # Sync our internal state with STT service state
                    self.is_recording = self.stt_service.state_manager.get_state().value == "recording"
                    return
                
                # Start STT recording
                success = self.stt_service.start_recording()
                if not success:
                    raise Exception("Failed to start STT recording")
                
                self.is_recording = True
                logger.info("Hotkey triggered: Recording started")
                
                # Call callback
                if self.on_recording_start:
                    self.on_recording_start()
                    
            except Exception as e:
                error_msg = f"Failed to start recording: {e}"
                logger.error(error_msg)
                if self.on_recording_error:
                    self.on_recording_error(error_msg)
    
    async def _async_recording_end(self, duration: float):
        """Async handler for recording end"""
        with self.recording_lock:
            # Check actual STT service state instead of just our internal flag
            if not self.is_recording and not self.stt_service.state_manager.can_stop_recording():
                logger.debug("No recording in progress - hotkey released but no active recording")
                return
            
            try:
                if not self.stt_service:
                    raise Exception("STT service not available")
                
                # Check if we can actually stop recording
                current_state = self.stt_service.state_manager.get_state()
                if not self.stt_service.state_manager.can_stop_recording():
                    # If already processing/transcribing, the recording was already stopped
                    if current_state.value in ["processing", "transcribing"]:
                        logger.debug(f"Recording already stopped and processing - state: {current_state}")
                        self.is_recording = False
                        return
                    else:
                        logger.debug(f"Cannot stop recording in state: {current_state}")
                        return
                
                # Stop STT recording
                success = self.stt_service.stop_recording()
                if not success:
                    raise Exception("Failed to stop STT recording")
                
                self.is_recording = False
                logger.info(f"Hotkey released: Recording stopped (duration: {duration:.2f}s)")
                
                # Call callback
                if self.on_recording_stop:
                    self.on_recording_stop()
                    
            except Exception as e:
                error_msg = f"Failed to stop recording: {e}"
                logger.error(error_msg)
                self.is_recording = False  # Reset state even on error
                if self.on_recording_error:
                    self.on_recording_error(error_msg)
    
    async def change_hotkey(self, new_hotkey: str) -> Dict[str, Any]:
        """
        Change the recording hotkey
        
        Returns:
            Dict with 'success', 'message', and optional 'warnings'
        """
        try:
            # Validate the new hotkey
            validation = validate_hotkey(new_hotkey)
            if not validation['valid']:
                return {
                    'success': False,
                    'message': f"Invalid hotkey: {'; '.join(validation['errors'])}",
                    'errors': validation['errors']
                }
            
            # Store old hotkey for rollback
            old_hotkey = self.current_hotkey
            
            # Update current hotkey
            self.current_hotkey = new_hotkey
            
            # Re-register the hotkey
            if not await self._register_stt_hotkey():
                # Rollback on failure
                self.current_hotkey = old_hotkey
                await self._register_stt_hotkey()
                return {
                    'success': False,
                    'message': f"Failed to register hotkey '{new_hotkey}'"
                }
            
            # Save to preferences
            if self.preferences_repo:
                try:
                    await self.preferences_repo.update_by_key("recording_hotkey", new_hotkey)
                    logger.info(f"Saved new hotkey to preferences: {new_hotkey}")
                except Exception as e:
                    logger.warning(f"Failed to save hotkey preference: {e}")
            
            result = {
                'success': True,
                'message': f"Hotkey changed to '{new_hotkey}'",
                'old_hotkey': old_hotkey,
                'new_hotkey': new_hotkey
            }
            
            if validation['warnings']:
                result['warnings'] = validation['warnings']
            
            logger.info(f"Hotkey changed from '{old_hotkey}' to '{new_hotkey}'")
            return result
            
        except Exception as e:
            error_msg = f"Error changing hotkey: {e}"
            logger.error(error_msg)
            return {
                'success': False,
                'message': error_msg
            }
    
    def validate_hotkey_string(self, hotkey_str: str) -> Dict[str, Any]:
        """Validate a hotkey string without changing it"""
        return validate_hotkey(hotkey_str)
    
    def get_hotkey_suggestions(self) -> list:
        """Get list of recommended hotkey combinations"""
        from .key_validator import KeyValidator
        validator = KeyValidator()
        return validator.get_recommended_hotkeys()
    
    def get_current_hotkey(self) -> str:
        """Get the currently configured hotkey"""
        return self.current_hotkey
    
    def is_hotkey_active(self) -> bool:
        """Check if the hotkey is currently active"""
        return self.hotkey_registered and self.manager and self.manager.is_running()
    
    def set_hotkey_active(self, active: bool) -> bool:
        """Enable or disable the current hotkey"""
        if not self.hotkey_registered or not self.manager:
            return False
        
        return self.manager.set_hotkey_active("stt_recording", active)
    
    def get_status(self) -> Dict[str, Any]:
        """Get detailed status information"""
        manager_status = {}
        manager_running = False
        
        if self.manager:
            try:
                manager_status = self.manager.get_status()
                manager_running = self.manager.is_running()
            except Exception as e:
                logger.warning(f"Error getting manager status: {e}")
        
        return {
            'service_running': manager_running,
            'hotkey_registered': self.hotkey_registered,
            'current_hotkey': self.current_hotkey,
            'is_recording': self.is_recording,
            'manager_status': manager_status,
            'stt_service_available': self.stt_service is not None
        }
    
    def reset_recording_state(self):
        """Reset the recording state without stopping the service"""
        try:
            with self.recording_lock:
                self.is_recording = False
                logger.info("Hotkey service recording state reset to idle")
        except Exception as e:
            logger.error(f"Error resetting hotkey recording state: {e}")
    
    def cleanup(self):
        """Clean up the hotkey service"""
        try:
            if self.manager:
                self.manager.stop()
            
            self.hotkey_registered = False
            self.is_recording = False
            
            logger.info("Hotkey service cleaned up")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# Global hotkey service instance
_hotkey_service: Optional[HotkeyService] = None


async def get_hotkey_service() -> HotkeyService:
    """Get global hotkey service instance"""
    global _hotkey_service
    
    if _hotkey_service is None:
        _hotkey_service = HotkeyService()
        # Don't auto-initialize - will be done after user login
    
    return _hotkey_service