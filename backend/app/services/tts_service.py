"""
TTS Service for text-to-speech synthesis using piper-tts.

This service handles:
- Loading the piper-tts voice model
- Generating speech audio from text
- Streaming audio output for fast response times
"""

import asyncio
import logging
import wave
import io
from typing import Optional, Union, AsyncGenerator
from pathlib import Path

try:
    from piper import PiperVoice, SynthesisConfig
    logger = logging.getLogger(__name__)
    logger.info("Successfully imported PiperVoice and SynthesisConfig from piper")
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.error(f"Failed to import from piper: {e}")
    raise

from app.db.repositories import get_preferences_repository


class TTSService:
    """Service for text-to-speech synthesis using piper-tts."""
    
    def __init__(self):
        """Initialize the TTS service."""
        self.voice: Optional[PiperVoice] = None
        self._model_loading_lock = asyncio.Lock()
        self._is_initialized = False
        self._current_voice_name: Optional[str] = None
        
        # Audio configuration from the voice model
        self.sample_rate = 22050
        self.sample_width = 2  # 16-bit audio
        self.channels = 1  # Mono
        
        logger.info("Initializing TTSService")
    
    async def _get_voice_model_path(self) -> Path:
        """Get the voice model path from preferences."""
        try:
            # Get preferences repository (it returns the class, not instance)
            PreferencesRepo = await get_preferences_repository()
            
            # Get TTS voice preference
            voice_pref = await PreferencesRepo.get_by_key("tts_voice")
            if voice_pref:
                voice_name = voice_pref.get_typed_value()
                logger.info(f"TTS voice preference found in DB: {voice_name}")
            else:
                voice_name = "en_US-hfc_female-medium"
                logger.warning("No TTS voice preference found in DB, using default: en_US-hfc_female-medium")
            logger.info(f"TTS voice preference: {voice_name} (DB record: {voice_pref})")
            
            # Construct path to voice model relative to current working directory
            # When running from backend folder, TTS is directly accessible
            model_path = Path(f"TTS/{voice_name}.onnx")
            
            # If that doesn't exist, try with backend prefix (when running from project root)
            if not model_path.exists():
                model_path = Path(f"backend/TTS/{voice_name}.onnx")
            
            return model_path
        except Exception as e:
            logger.error(f"Failed to get voice model from preferences: {e}")
            # Fallback to default with relative path
            # Try TTS folder first (when running from backend)
            default_path = Path("TTS/en_US-hfc_female-medium.onnx")
            if not default_path.exists():
                # Try with backend prefix (when running from project root)
                default_path = Path("backend/TTS/en_US-hfc_female-medium.onnx")
            return default_path
    
    async def initialize(self) -> None:
        """Initialize the piper-tts model if not already loaded."""
        try:
            # Get current voice preference
            model_path = await self._get_voice_model_path()
            voice_name = model_path.stem
            
            # Check if we need to reload (voice changed)
            logger.info(f"Current voice: {self._current_voice_name}, Requested voice: {voice_name}")
            if self._is_initialized and self._current_voice_name == voice_name:
                logger.info("Voice unchanged, using cached model")
                return
            
            async with self._model_loading_lock:
                # Double-check after acquiring lock
                if self._is_initialized and self._current_voice_name == voice_name:
                    return
                
                try:
                    logger.info(f"Loading piper-tts model: {model_path}")
                    
                    # Check if model file exists
                    if not model_path.exists():
                        raise FileNotFoundError(f"Model file not found: {model_path}")
                    
                    # Load model in thread pool to avoid blocking
                    loop = asyncio.get_event_loop()
                    self.voice = await loop.run_in_executor(
                        None,
                        PiperVoice.load,
                        str(model_path)
                    )
                    
                    self._is_initialized = True
                    self._current_voice_name = voice_name
                    logger.info(f"Piper-TTS model loaded successfully: {voice_name}")
                    
                except Exception as e:
                    logger.error(f"Failed to load piper-tts model: {e}", exc_info=True)
                    raise
        except Exception as e:
            logger.error(f"Error in TTS initialize: {e}", exc_info=True)
            raise
    
    async def _get_synthesis_config(self) -> SynthesisConfig:
        """Get synthesis configuration from preferences."""
        try:
            # Get preferences repository (it returns the class, not instance)
            PreferencesRepo = await get_preferences_repository()
            
            # Get TTS settings from preferences
            volume_pref = await PreferencesRepo.get_by_key("tts_volume")
            speed_pref = await PreferencesRepo.get_by_key("tts_speed")
            
            # Default values
            volume = 1.0  # Normal volume
            length_scale = 1.0  # Normal speed
            
            # Get volume (0.0 to 1.0)
            if volume_pref:
                volume = float(volume_pref.get_typed_value())
                volume = max(0.0, min(1.0, volume))  # Clamp between 0 and 1
            
            # Get speed (convert to length_scale: lower = faster, higher = slower)
            if speed_pref:
                speed = float(speed_pref.get_typed_value())
                # Speed of 2.0 = twice as fast = length_scale of 0.5
                # Speed of 0.5 = half as fast = length_scale of 2.0
                # Speed of 0 = silent (use very high length_scale to make it extremely slow)
                if speed == 0:
                    length_scale = 100.0  # Extremely slow for "silent" effect
                elif speed > 0:
                    length_scale = 1.0 / speed
                else:
                    length_scale = 1.0
            
            return SynthesisConfig(
                volume=volume,
                length_scale=length_scale,
                noise_scale=1.0,  # Default variation
                noise_w_scale=1.0,  # Default speaking variation
                normalize_audio=True  # Use normalized audio
            )
            
        except Exception as e:
            logger.error(f"Failed to get synthesis config from preferences: {e}")
            # Return default config
            return SynthesisConfig(
                volume=1.0,
                length_scale=1.0,
                noise_scale=1.0,
                noise_w_scale=1.0,
                normalize_audio=True
            )
    
    async def synthesize_speech(
        self, 
        text: str, 
        stream: bool = True
    ) -> Union[bytes, AsyncGenerator[bytes, None]]:
        """
        Synthesize speech from text using piper-tts.
        
        Args:
            text: Text to convert to speech (already cleaned by ChatModal)
            stream: Whether to stream audio chunks for faster response
            
        Returns:
            Audio data as bytes or async generator of audio chunks
        """
        await self.initialize()
        
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        try:
            logger.info(f"Synthesizing speech for text: '{text[:50]}...' (stream={stream})")
            
            if stream:
                return self._synthesize_streaming(text)
            else:
                return await self._synthesize_complete(text)
                
        except Exception as e:
            logger.error(f"Speech synthesis failed: {e}")
            raise
    
    async def _synthesize_complete(self, text: str) -> bytes:
        """Synthesize complete audio file using piper-tts."""
        try:
            # Get synthesis config
            syn_config = await self._get_synthesis_config()
            
            # Create WAV buffer
            wav_buffer = io.BytesIO()
            
            # Run synthesis in thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._synthesize_wav_sync,
                text,
                wav_buffer,
                syn_config
            )
            
            # Get the WAV bytes
            wav_buffer.seek(0)
            wav_bytes = wav_buffer.read()
            wav_buffer.close()
            
            logger.info(f"Generated {len(wav_bytes)} bytes of audio")
            return wav_bytes
            
        except Exception as e:
            logger.error(f"Failed to synthesize complete audio: {e}")
            raise
    
    def _synthesize_wav_sync(self, text: str, wav_buffer: io.BytesIO, syn_config: SynthesisConfig) -> None:
        """Synchronous WAV synthesis (runs in thread pool)."""
        with wave.open(wav_buffer, 'wb') as wav_file:
            # Set WAV parameters
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(self.sample_width)
            wav_file.setframerate(self.sample_rate)
            
            # Synthesize audio with config
            logger.debug(f"Calling synthesize_wav with config: {syn_config}")
            try:
                # Use syn_config parameter as per documentation
                self.voice.synthesize_wav(text, wav_file, syn_config=syn_config)
            except TypeError as e:
                logger.error(f"TypeError calling synthesize_wav with syn_config: {e}")
                # Fallback to without config
                logger.warning("Falling back to synthesize without config")
                self.voice.synthesize_wav(text, wav_file)
    
    async def _synthesize_streaming(self, text: str) -> AsyncGenerator[bytes, None]:
        """Synthesize audio in streaming chunks using piper-tts."""
        try:
            # Get synthesis config first
            syn_config = await self._get_synthesis_config()
            
            # Run streaming synthesis in thread pool
            loop = asyncio.get_event_loop()
            
            # Use the actual piper streaming method to collect all raw audio data
            def stream_audio(config):
                all_audio_data = bytearray()
                sample_rate = None
                sample_width = None
                channels = None
                
                logger.debug(f"Calling synthesize with config: {config}")
                try:
                    # Use syn_config parameter as per documentation
                    for chunk in self.voice.synthesize(text, syn_config=config):
                        # Store audio parameters from first chunk
                        if sample_rate is None:
                            sample_rate = chunk.sample_rate
                            sample_width = chunk.sample_width
                            channels = chunk.sample_channels
                        
                        # Append raw audio data (not WAV formatted)
                        all_audio_data.extend(chunk.audio_int16_bytes)
                except TypeError as e:
                    logger.error(f"TypeError calling synthesize with config: {e}")
                    # Fallback to without config
                    logger.warning("Falling back to synthesize without config")
                    for chunk in self.voice.synthesize(text):
                        # Store audio parameters from first chunk
                        if sample_rate is None:
                            sample_rate = chunk.sample_rate
                            sample_width = chunk.sample_width
                            channels = chunk.sample_channels
                        
                        # Append raw audio data (not WAV formatted)
                        all_audio_data.extend(chunk.audio_int16_bytes)
                
                return bytes(all_audio_data), sample_rate, sample_width, channels
            
            # Get all audio data in thread pool
            audio_data, sample_rate, sample_width, channels = await loop.run_in_executor(None, stream_audio, syn_config)
            
            # Create a single WAV file from all the audio data
            wav_bytes = self._create_wav_from_raw_audio(audio_data, sample_rate, sample_width, channels)
            
            # For streaming effect, we can split the final WAV into smaller chunks
            # But ensure we don't break the WAV structure
            chunk_size = len(wav_bytes) // 4  # Split into 4 parts for streaming effect
            if chunk_size < 1024:  # Minimum chunk size
                yield wav_bytes
            else:
                # For streaming, just return the complete audio since WAV can't be properly split
                yield wav_bytes
                    
        except Exception as e:
            logger.error(f"Failed to synthesize streaming audio: {e}")
            raise
    
    def _create_wav_from_raw_audio(self, audio_data: bytes, sample_rate: int, sample_width: int, channels: int) -> bytes:
        """Create a single WAV file from raw audio data."""
        try:
            # Create a BytesIO buffer
            wav_buffer = io.BytesIO()
            
            # Write WAV file to buffer
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(sample_width)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_data)
            
            # Get the bytes
            wav_bytes = wav_buffer.getvalue()
            wav_buffer.close()
            
            return wav_bytes
            
        except Exception as e:
            logger.error(f"Failed to create WAV from raw audio: {e}")
            raise
    
    async def get_model_info(self) -> dict:
        """Get information about the loaded TTS model."""
        await self.initialize()
        
        # Get current model path
        model_path = await self._get_voice_model_path()
        
        return {
            "model_name": self._current_voice_name or "Not loaded",
            "is_initialized": self._is_initialized,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "model_path": str(model_path)
        }
    
    def is_ready(self) -> bool:
        """Check if the TTS service is ready to synthesize speech."""
        return self._is_initialized and self.voice is not None


# Global TTS service instance
_tts_service: Optional[TTSService] = None


def get_tts_service() -> TTSService:
    """Get the global TTS service instance."""
    global _tts_service
    if _tts_service is None:
        _tts_service = TTSService()
    return _tts_service


async def initialize_tts_service() -> None:
    """Initialize the global TTS service."""
    service = get_tts_service()
    await service.initialize()