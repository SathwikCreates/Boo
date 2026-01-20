"""
Global hotkey management with press-and-hold detection
"""

import threading
import time
from typing import Optional, Callable, Dict, Any, Set
from pynput import keyboard
import logging

from .key_validator import KeyValidator

logger = logging.getLogger(__name__)


class HotkeyManager:
    """Manages global hotkey registration and press-and-hold detection"""
    
    def __init__(self):
        self.validator = KeyValidator()
        self.listener: Optional[keyboard.Listener] = None
        self.registered_hotkeys: Dict[str, Dict[str, Any]] = {}
        self.pressed_keys: Set[Any] = set()
        self.hotkey_states: Dict[str, Dict[str, Any]] = {}
        self.running = False
        self._lock = threading.Lock()
        
        # Press-and-hold tracking
        self.hold_timers: Dict[str, threading.Timer] = {}
        self.hold_threshold = 0.1  # Minimum hold time in seconds
        
    def start(self) -> bool:
        """Start the global hotkey listener"""
        if self.running:
            logger.warning("Hotkey manager already running")
            return True
        
        try:
            self.listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release
            )
            self.listener.start()
            self.running = True
            logger.info("Hotkey manager started successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to start hotkey manager: {e}")
            return False
    
    def stop(self):
        """Stop the global hotkey listener"""
        if not self.running:
            return
        
        try:
            if self.listener:
                self.listener.stop()
                self.listener = None
            
            # Cancel any active hold timers
            with self._lock:
                for timer in self.hold_timers.values():
                    timer.cancel()
                self.hold_timers.clear()
            
            self.running = False
            self.pressed_keys.clear()
            self.hotkey_states.clear()
            
            logger.info("Hotkey manager stopped")
        except Exception as e:
            logger.error(f"Error stopping hotkey manager: {e}")
    
    def register_hotkey(self, 
                       hotkey_id: str,
                       hotkey_str: str,
                       on_press: Optional[Callable[[], None]] = None,
                       on_release: Optional[Callable[[], None]] = None,
                       on_hold_start: Optional[Callable[[], None]] = None,
                       on_hold_end: Optional[Callable[[float], None]] = None,
                       hold_mode: bool = True) -> bool:
        """
        Register a hotkey with callbacks
        
        Args:
            hotkey_id: Unique identifier for this hotkey
            hotkey_str: Hotkey string (e.g., "f8", "ctrl+alt+r")
            on_press: Callback for key press (immediate)
            on_release: Callback for key release (immediate)
            on_hold_start: Callback when hold is detected
            on_hold_end: Callback when hold ends (receives hold duration)
            hold_mode: If True, enables press-and-hold detection
        
        Returns:
            True if registration successful
        """
        # Validate the hotkey
        validation = self.validator.validate_hotkey(hotkey_str)
        if not validation['valid']:
            logger.error(f"Invalid hotkey '{hotkey_str}': {validation['errors']}")
            return False
        
        if validation['warnings']:
            for warning in validation['warnings']:
                logger.warning(f"Hotkey '{hotkey_str}': {warning}")
        
        parsed = validation['parsed']
        
        # Convert to pynput keys
        main_key = self.validator.convert_to_pynput_key(parsed['key'])
        if main_key is None:
            logger.error(f"Cannot convert key '{parsed['key']}' to pynput format")
            return False
        
        modifier_keys = []
        for mod in parsed['modifiers']:
            mod_key = self.validator.convert_to_pynput_key(mod)
            if mod_key is None:
                logger.error(f"Cannot convert modifier '{mod}' to pynput format")
                return False
            modifier_keys.append(mod_key)
        
        # Register the hotkey
        with self._lock:
            self.registered_hotkeys[hotkey_id] = {
                'hotkey_str': hotkey_str,
                'parsed': parsed,
                'main_key': main_key,
                'modifier_keys': set(modifier_keys),
                'on_press': on_press,
                'on_release': on_release,
                'on_hold_start': on_hold_start,
                'on_hold_end': on_hold_end,
                'hold_mode': hold_mode,
                'active': True
            }
            
            # Initialize state tracking
            self.hotkey_states[hotkey_id] = {
                'pressed': False,
                'holding': False,
                'press_time': None,
                'hold_started': False
            }
        
        logger.info(f"Registered hotkey '{hotkey_str}' with ID '{hotkey_id}'")
        return True
    
    def unregister_hotkey(self, hotkey_id: str) -> bool:
        """Unregister a hotkey"""
        with self._lock:
            if hotkey_id not in self.registered_hotkeys:
                logger.warning(f"Hotkey ID '{hotkey_id}' not found")
                return False
            
            # Cancel any active timer
            if hotkey_id in self.hold_timers:
                self.hold_timers[hotkey_id].cancel()
                del self.hold_timers[hotkey_id]
            
            # Remove from tracking
            del self.registered_hotkeys[hotkey_id]
            if hotkey_id in self.hotkey_states:
                del self.hotkey_states[hotkey_id]
        
        logger.info(f"Unregistered hotkey ID '{hotkey_id}'")
        return True
    
    def set_hotkey_active(self, hotkey_id: str, active: bool) -> bool:
        """Enable or disable a registered hotkey"""
        with self._lock:
            if hotkey_id not in self.registered_hotkeys:
                return False
            
            self.registered_hotkeys[hotkey_id]['active'] = active
            
            # Reset state if disabling
            if not active:
                self.hotkey_states[hotkey_id] = {
                    'pressed': False,
                    'holding': False,
                    'press_time': None,
                    'hold_started': False
                }
                
                # Cancel any active timer
                if hotkey_id in self.hold_timers:
                    self.hold_timers[hotkey_id].cancel()
                    del self.hold_timers[hotkey_id]
        
        logger.info(f"Hotkey '{hotkey_id}' {'enabled' if active else 'disabled'}")
        return True
    
    def _on_key_press(self, key):
        """Handle key press events"""
        try:
            self.pressed_keys.add(key)
            self._check_hotkey_matches(key, is_press=True)
        except Exception as e:
            logger.error(f"Error in key press handler: {e}")
    
    def _on_key_release(self, key):
        """Handle key release events"""
        try:
            self.pressed_keys.discard(key)
            self._check_hotkey_matches(key, is_press=False)
        except Exception as e:
            logger.error(f"Error in key release handler: {e}")
    
    def _check_hotkey_matches(self, key, is_press: bool):
        """Check if current key state matches any registered hotkeys"""
        with self._lock:
            for hotkey_id, hotkey_data in self.registered_hotkeys.items():
                if not hotkey_data['active']:
                    continue
                
                is_match = self._is_hotkey_match(hotkey_data, key)
                state = self.hotkey_states[hotkey_id]
                
                if is_press and is_match and not state['pressed']:
                    # Hotkey press detected
                    self._handle_hotkey_press(hotkey_id, hotkey_data, state)
                
                elif not is_press and state['pressed'] and (
                    key == hotkey_data['main_key'] or 
                    key in hotkey_data['modifier_keys']
                ):
                    # Hotkey release detected
                    self._handle_hotkey_release(hotkey_id, hotkey_data, state)
    
    def _is_hotkey_match(self, hotkey_data: Dict[str, Any], triggered_key) -> bool:
        """Check if current pressed keys match the hotkey combination"""
        main_key = hotkey_data['main_key']
        required_modifiers = hotkey_data['modifier_keys']
        
        # Main key must be pressed
        if main_key not in self.pressed_keys:
            return False
        
        # All required modifiers must be pressed
        for modifier in required_modifiers:
            if modifier not in self.pressed_keys:
                return False
        
        # Check if the triggered key is part of this hotkey
        return (triggered_key == main_key or triggered_key in required_modifiers)
    
    def _handle_hotkey_press(self, hotkey_id: str, hotkey_data: Dict[str, Any], state: Dict[str, Any]):
        """Handle hotkey press event"""
        state['pressed'] = True
        state['press_time'] = time.time()
        state['hold_started'] = False
        
        logger.debug(f"Hotkey '{hotkey_id}' pressed")
        
        # Call immediate press callback
        if hotkey_data['on_press']:
            try:
                hotkey_data['on_press']()
            except Exception as e:
                logger.error(f"Error in press callback for '{hotkey_id}': {e}")
        
        # Set up hold detection if enabled
        if hotkey_data['hold_mode'] and hotkey_data['on_hold_start']:
            def on_hold_timer():
                with self._lock:
                    if (hotkey_id in self.hotkey_states and 
                        self.hotkey_states[hotkey_id]['pressed'] and
                        not self.hotkey_states[hotkey_id]['hold_started']):
                        
                        self.hotkey_states[hotkey_id]['hold_started'] = True
                        logger.debug(f"Hotkey '{hotkey_id}' hold detected")
                        
                        try:
                            hotkey_data['on_hold_start']()
                        except Exception as e:
                            logger.error(f"Error in hold start callback for '{hotkey_id}': {e}")
            
            timer = threading.Timer(self.hold_threshold, on_hold_timer)
            self.hold_timers[hotkey_id] = timer
            timer.start()
    
    def _handle_hotkey_release(self, hotkey_id: str, hotkey_data: Dict[str, Any], state: Dict[str, Any]):
        """Handle hotkey release event"""
        if not state['pressed']:
            return
        
        hold_duration = 0
        if state['press_time']:
            hold_duration = time.time() - state['press_time']
        
        was_holding = state['hold_started']
        
        # Reset state
        state['pressed'] = False
        state['holding'] = False
        state['press_time'] = None
        state['hold_started'] = False
        
        # Cancel hold timer
        if hotkey_id in self.hold_timers:
            self.hold_timers[hotkey_id].cancel()
            del self.hold_timers[hotkey_id]
        
        logger.debug(f"Hotkey '{hotkey_id}' released (duration: {hold_duration:.2f}s)")
        
        # Call release callback
        if hotkey_data['on_release']:
            try:
                hotkey_data['on_release']()
            except Exception as e:
                logger.error(f"Error in release callback for '{hotkey_id}': {e}")
        
        # Call hold end callback if was holding
        if was_holding and hotkey_data['on_hold_end']:
            try:
                hotkey_data['on_hold_end'](hold_duration)
            except Exception as e:
                logger.error(f"Error in hold end callback for '{hotkey_id}': {e}")
    
    def get_registered_hotkeys(self) -> Dict[str, Dict[str, Any]]:
        """Get information about registered hotkeys"""
        with self._lock:
            return {
                hotkey_id: {
                    'hotkey_str': data['hotkey_str'],
                    'active': data['active'],
                    'hold_mode': data['hold_mode'],
                    'state': self.hotkey_states.get(hotkey_id, {}).copy()
                }
                for hotkey_id, data in self.registered_hotkeys.items()
            }
    
    def is_running(self) -> bool:
        """Check if the hotkey manager is running"""
        return self.running
    
    def get_status(self) -> Dict[str, Any]:
        """Get detailed status information"""
        with self._lock:
            return {
                'running': self.running,
                'registered_count': len(self.registered_hotkeys),
                'active_count': sum(1 for data in self.registered_hotkeys.values() if data['active']),
                'pressed_keys_count': len(self.pressed_keys),
                'active_timers': len(self.hold_timers),
                'hotkeys': self.get_registered_hotkeys()
            }