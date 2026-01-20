"""
Hotkey validation and parsing utilities
"""

import re
from typing import Optional, Set, List, Dict, Any
from pynput import keyboard
import logging

logger = logging.getLogger(__name__)


class KeyValidator:
    """Validates and parses hotkey configurations"""
    
    # Valid modifier keys
    VALID_MODIFIERS = {
        'ctrl', 'control', 'alt', 'shift', 'cmd', 'super', 'win', 'windows'
    }
    
    # Valid function keys
    VALID_FUNCTION_KEYS = {
        f'f{i}' for i in range(1, 25)  # F1-F24
    }
    
    # Valid special keys
    VALID_SPECIAL_KEYS = {
        'space', 'enter', 'return', 'tab', 'escape', 'esc', 'backspace', 'delete', 'del',
        'insert', 'ins', 'home', 'end', 'pageup', 'pagedown', 'pgup', 'pgdn',
        'up', 'down', 'left', 'right', 'capslock', 'numlock', 'scrolllock',
        'pause', 'break', 'printscreen', 'prtsc'
    }
    
    # Valid alphanumeric keys
    VALID_ALPHANUMERIC = set('abcdefghijklmnopqrstuvwxyz0123456789')
    
    # Reserved/problematic key combinations
    RESERVED_COMBINATIONS = {
        'ctrl+alt+del',  # System reserved
        'alt+f4',        # Window close
        'ctrl+c',        # Copy
        'ctrl+v',        # Paste
        'ctrl+x',        # Cut
        'ctrl+z',        # Undo
        'ctrl+y',        # Redo
        'ctrl+s',        # Save
        'alt+tab',       # Window switcher
        'win+l',         # Lock screen
    }
    
    def __init__(self):
        self.key_mapping = self._build_key_mapping()
    
    def _build_key_mapping(self) -> Dict[str, Any]:
        """Build mapping from string keys to pynput Key objects"""
        mapping = {}
        
        # Function keys
        for i in range(1, 25):
            key_name = f'f{i}'
            if hasattr(keyboard.Key, key_name):
                mapping[key_name] = getattr(keyboard.Key, key_name)
        
        # Special keys mapping
        special_mapping = {
            'space': keyboard.Key.space,
            'enter': keyboard.Key.enter,
            'return': keyboard.Key.enter,
            'tab': keyboard.Key.tab,
            'escape': keyboard.Key.esc,
            'esc': keyboard.Key.esc,
            'backspace': keyboard.Key.backspace,
            'delete': keyboard.Key.delete,
            'del': keyboard.Key.delete,
            'insert': keyboard.Key.insert,
            'ins': keyboard.Key.insert,
            'home': keyboard.Key.home,
            'end': keyboard.Key.end,
            'pageup': keyboard.Key.page_up,
            'pagedown': keyboard.Key.page_down,
            'pgup': keyboard.Key.page_up,
            'pgdn': keyboard.Key.page_down,
            'up': keyboard.Key.up,
            'down': keyboard.Key.down,
            'left': keyboard.Key.left,
            'right': keyboard.Key.right,
            'capslock': keyboard.Key.caps_lock,
            'numlock': keyboard.Key.num_lock,
            'scrolllock': keyboard.Key.scroll_lock,
            'pause': keyboard.Key.pause,
            'break': keyboard.Key.pause,
            'printscreen': keyboard.Key.print_screen,
            'prtsc': keyboard.Key.print_screen,
            # Modifiers
            'ctrl': keyboard.Key.ctrl,
            'control': keyboard.Key.ctrl,
            'alt': keyboard.Key.alt,
            'shift': keyboard.Key.shift,
            'cmd': keyboard.Key.cmd,
            'super': keyboard.Key.cmd,
            'win': keyboard.Key.cmd,
            'windows': keyboard.Key.cmd,
        }
        
        mapping.update(special_mapping)
        return mapping
    
    def parse_hotkey(self, hotkey_str: str) -> Optional[Dict[str, Any]]:
        """
        Parse a hotkey string into components
        
        Args:
            hotkey_str: String like "ctrl+alt+f8" or "f8"
            
        Returns:
            Dict with 'modifiers' and 'key' or None if invalid
        """
        if not hotkey_str or not isinstance(hotkey_str, str):
            return None
        
        # Normalize the input
        normalized = hotkey_str.lower().strip()
        if not normalized:
            return None
        
        # Split by + sign
        parts = [part.strip() for part in normalized.split('+')]
        if not parts:
            return None
        
        # Last part is the main key
        main_key = parts[-1]
        modifiers = parts[:-1] if len(parts) > 1 else []
        
        # Validate main key
        if not self._is_valid_key(main_key):
            logger.warning(f"Invalid main key: {main_key}")
            return None
        
        # Validate modifiers
        valid_modifiers = []
        for modifier in modifiers:
            if modifier not in self.VALID_MODIFIERS:
                logger.warning(f"Invalid modifier: {modifier}")
                return None
            valid_modifiers.append(modifier)
        
        return {
            'key': main_key,
            'modifiers': valid_modifiers,
            'raw_string': hotkey_str,
            'normalized': normalized
        }
    
    def _is_valid_key(self, key: str) -> bool:
        """Check if a key is valid"""
        return (
            key in self.VALID_FUNCTION_KEYS or
            key in self.VALID_SPECIAL_KEYS or
            key in self.VALID_ALPHANUMERIC
        )
    
    def is_reserved_combination(self, hotkey_str: str) -> bool:
        """Check if a hotkey combination is reserved by the system"""
        normalized = hotkey_str.lower().strip()
        return normalized in self.RESERVED_COMBINATIONS
    
    def validate_hotkey(self, hotkey_str: str) -> Dict[str, Any]:
        """
        Comprehensive hotkey validation
        
        Returns:
            Dict with 'valid', 'parsed', 'warnings', 'errors'
        """
        result = {
            'valid': False,
            'parsed': None,
            'warnings': [],
            'errors': []
        }
        
        # Basic parsing
        parsed = self.parse_hotkey(hotkey_str)
        if not parsed:
            result['errors'].append("Invalid hotkey format")
            return result
        
        result['parsed'] = parsed
        
        # Check for reserved combinations
        if self.is_reserved_combination(hotkey_str):
            result['errors'].append("This key combination is reserved by the system")
            return result
        
        # Function key recommendations
        if parsed['key'] in self.VALID_FUNCTION_KEYS:
            if not parsed['modifiers']:
                result['warnings'].append("Function keys work best without modifiers for global hotkeys")
        
        # Modifier recommendations
        if len(parsed['modifiers']) > 2:
            result['warnings'].append("Complex modifier combinations may be hard to press")
        
        # Check for common conflict patterns
        self._check_common_conflicts(parsed, result)
        
        result['valid'] = len(result['errors']) == 0
        return result
    
    def _check_common_conflicts(self, parsed: Dict[str, Any], result: Dict[str, Any]):
        """Check for common conflict patterns"""
        key = parsed['key']
        modifiers = set(parsed['modifiers'])
        
        # Alt combinations can conflict with menu access
        if 'alt' in modifiers and key in self.VALID_ALPHANUMERIC:
            result['warnings'].append("Alt+letter combinations may conflict with application menus")
        
        # Ctrl combinations are commonly used
        if 'ctrl' in modifiers and key in self.VALID_ALPHANUMERIC:
            result['warnings'].append("Ctrl+letter combinations are commonly used by applications")
        
        # Single letter keys without modifiers are problematic
        if not modifiers and key in self.VALID_ALPHANUMERIC:
            result['warnings'].append("Single letters without modifiers will interfere with typing")
    
    def convert_to_pynput_key(self, key_str: str) -> Optional[Any]:
        """Convert a key string to pynput Key object"""
        normalized = key_str.lower().strip()
        
        # Check direct mapping
        if normalized in self.key_mapping:
            return self.key_mapping[normalized]
        
        # Check if it's a single character
        if len(normalized) == 1 and normalized in self.VALID_ALPHANUMERIC:
            return normalized
        
        return None
    
    def get_recommended_hotkeys(self) -> List[str]:
        """Get list of recommended hotkey combinations"""
        return [
            'f8',     # Current default
            'f9',     # Alternative function key
            'f10',    # Alternative function key
            'f11',    # May conflict with fullscreen
            'f12',    # May conflict with dev tools
            'ctrl+f8',
            'alt+f8',
            'ctrl+shift+r',  # R for Record
            'ctrl+shift+v',  # V for Voice
        ]
    
    def suggest_alternatives(self, invalid_hotkey: str) -> List[str]:
        """Suggest alternative hotkeys if the given one is invalid"""
        alternatives = []
        
        parsed = self.parse_hotkey(invalid_hotkey)
        if parsed:
            key = parsed['key']
            
            # If it's a function key, suggest nearby function keys
            if key in self.VALID_FUNCTION_KEYS:
                f_num = int(key[1:])
                for offset in [-1, 1, -2, 2]:
                    alt_num = f_num + offset
                    if 1 <= alt_num <= 24:
                        alt_key = f'f{alt_num}'
                        if alt_key not in ['f11', 'f12']:  # Avoid common conflicts
                            alternatives.append(alt_key)
        
        # Add general recommendations
        alternatives.extend([k for k in self.get_recommended_hotkeys() if k != invalid_hotkey])
        
        return alternatives[:5]  # Return top 5 alternatives


# Global validator instance
_validator = KeyValidator()


def validate_hotkey(hotkey_str: str) -> Dict[str, Any]:
    """Convenience function for hotkey validation"""
    return _validator.validate_hotkey(hotkey_str)