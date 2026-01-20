import pyaudio
import wave
import threading
import time
import numpy as np
from typing import Optional, Callable
import logging
from scipy import signal
import librosa

logger = logging.getLogger(__name__)


class AudioCapture:
    """Audio capture service for STT processing with dynamic resampling"""
    
    def __init__(
        self,
        target_sample_rate: int = 16000,  # Whisper target rate
        chunk_size: int = 1024,
        channels: int = 1,
        format: int = pyaudio.paInt16
    ):
        self.target_sample_rate = target_sample_rate  # 16kHz for Whisper
        self.native_sample_rate = None  # Will be detected dynamically
        self.chunk_size = chunk_size
        self.channels = channels
        self.format = format
        
        self.audio = None
        self.stream = None
        self.recording_thread = None
        self.is_recording = False
        self.audio_data = []
        
        # Callback for state changes
        self.state_callback: Optional[Callable[[str], None]] = None
        
    def initialize(self) -> bool:
        """Initialize PyAudio and detect native sample rate"""
        try:
            self.audio = pyaudio.PyAudio()
            
            # Detect default microphone's native sample rate
            self._detect_native_sample_rate()
            
            logger.info(f"PyAudio initialized - Native: {self.native_sample_rate}Hz, Target: {self.target_sample_rate}Hz")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize PyAudio: {e}")
            return False
    
    def set_state_callback(self, callback: Callable[[str], None]):
        """Set callback for state changes"""
        self.state_callback = callback
    
    def _notify_state(self, state: str):
        """Notify state change"""
        if self.state_callback:
            self.state_callback(state)
    
    def start_recording(self) -> bool:
        """Start audio recording at native sample rate"""
        if self.is_recording:
            return False
        
        if not self.native_sample_rate:
            logger.error("Native sample rate not detected")
            return False
            
        try:
            # Open audio stream at native sample rate
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=int(self.native_sample_rate),
                input=True,
                frames_per_buffer=self.chunk_size
            )
            
            self.is_recording = True
            self.audio_data = []
            
            # Start recording thread
            self.recording_thread = threading.Thread(target=self._record_audio)
            self.recording_thread.daemon = True
            self.recording_thread.start()
            
            self._notify_state("recording")
            logger.info(f"Audio recording started at {self.native_sample_rate}Hz")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            self.is_recording = False
            return False
    
    def stop_recording(self) -> Optional[bytes]:
        """Stop audio recording and return audio data"""
        if not self.is_recording:
            return None
        
        self.is_recording = False
        self._notify_state("processing")
        
        # Wait for recording thread to finish
        if self.recording_thread:
            self.recording_thread.join(timeout=2.0)
        
        # Close stream
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        
        # Convert audio data to bytes
        if self.audio_data:
            audio_bytes = b''.join(self.audio_data)
            logger.info(f"Recording stopped, captured {len(audio_bytes)} bytes")
            return audio_bytes
        
        return None
    
    def _record_audio(self):
        """Audio recording thread function"""
        try:
            while self.is_recording and self.stream:
                data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                if data:
                    self.audio_data.append(data)
        except Exception as e:
            logger.error(f"Error during audio recording: {e}")
            self.is_recording = False
    
    def save_audio_to_file(self, audio_data: bytes, filename: str, use_target_rate: bool = True) -> bool:
        """Save audio data to WAV file"""
        try:
            sample_rate = self.target_sample_rate if use_target_rate else self.native_sample_rate
            
            with wave.open(filename, 'wb') as wav_file:
                wav_file.setnchannels(self.channels)
                wav_file.setsampwidth(self.audio.get_sample_size(self.format))
                wav_file.setframerate(int(sample_rate))
                wav_file.writeframes(audio_data)
            
            logger.info(f"Audio saved to {filename} at {sample_rate}Hz")
            return True
        except Exception as e:
            logger.error(f"Failed to save audio to {filename}: {e}")
            return False
    
    def convert_to_numpy(self, audio_data: bytes, resample_for_whisper: bool = True) -> Optional[np.ndarray]:
        """Convert audio bytes to numpy array with optional resampling for Whisper"""
        try:
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # Convert to float32 and normalize to [-1, 1]
            audio_float = audio_array.astype(np.float32) / 32768.0
            
            # Resample if needed for Whisper compatibility
            if resample_for_whisper and self.native_sample_rate != self.target_sample_rate:
                audio_float = self._resample_audio(audio_float)
                logger.info(f"Audio resampled from {self.native_sample_rate}Hz to {self.target_sample_rate}Hz")
            
            return audio_float
        except Exception as e:
            logger.error(f"Failed to convert audio to numpy: {e}")
            return None
    
    def force_reset(self):
        """Force reset audio system - use when stuck"""
        try:
            logger.info("Force resetting audio system...")
            
            # Force stop recording
            self.is_recording = False
            
            # Close stream if exists
            if self.stream:
                try:
                    if not self.stream.is_stopped():
                        self.stream.stop_stream()
                    self.stream.close()
                except Exception as e:
                    logger.warning(f"Error closing stream during reset: {e}")
                finally:
                    self.stream = None
            
            # Wait for recording thread to finish
            if self.recording_thread and self.recording_thread.is_alive():
                self.recording_thread.join(timeout=1.0)
            
            # Clear data
            self.audio_data = []
            
            # Recreate PyAudio instance
            if self.audio:
                try:
                    self.audio.terminate()
                except Exception as e:
                    logger.warning(f"Error terminating PyAudio during reset: {e}")
            
            # Reinitialize
            self.audio = pyaudio.PyAudio()
            self._detect_native_sample_rate()
            
            logger.info(f"Audio system force reset complete - Native rate: {self.native_sample_rate}Hz")
            return True
            
        except Exception as e:
            logger.error(f"Force reset failed: {e}")
            return False

    def cleanup(self):
        """Clean up audio resources"""
        if self.is_recording:
            self.stop_recording()
        
        if self.audio:
            self.audio.terminate()
            self.audio = None
        
        logger.info("Audio capture cleaned up")
    
    def get_input_devices(self) -> list:
        """Get list of available input devices"""
        if not self.audio:
            return []
        
        devices = []
        for i in range(self.audio.get_device_count()):
            device_info = self.audio.get_device_info_by_index(i)
            if device_info['maxInputChannels'] > 0:
                devices.append({
                    'index': i,
                    'name': device_info['name'],
                    'channels': device_info['maxInputChannels'],
                    'sample_rate': device_info['defaultSampleRate']
                })
        
        return devices
    
    def _detect_native_sample_rate(self):
        """Detect the default microphone's native sample rate"""
        try:
            # Get default input device
            default_device = self.audio.get_default_input_device_info()
            self.native_sample_rate = default_device['defaultSampleRate']
            
            logger.info(f"Detected native sample rate: {self.native_sample_rate}Hz")
            
        except Exception as e:
            logger.warning(f"Failed to detect native sample rate: {e}")
            # Fallback to common sample rates
            common_rates = [44100, 48000, 22050, 16000]
            
            for rate in common_rates:
                if self._test_sample_rate(rate):
                    self.native_sample_rate = rate
                    logger.info(f"Using fallback sample rate: {rate}Hz")
                    break
            
            if not self.native_sample_rate:
                self.native_sample_rate = 44100  # Final fallback
                logger.warning(f"Using default fallback: {self.native_sample_rate}Hz")
    
    def _test_sample_rate(self, sample_rate: int) -> bool:
        """Test if a sample rate is supported by the default input device"""
        try:
            # Try to open a test stream
            test_stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=sample_rate,
                input=True,
                frames_per_buffer=1024
            )
            test_stream.close()
            return True
        except:
            return False
    
    def _resample_audio(self, audio_data: np.ndarray) -> np.ndarray:
        """Resample audio from native rate to target rate using librosa"""
        try:
            # Use librosa for high-quality resampling
            resampled = librosa.resample(
                audio_data,
                orig_sr=int(self.native_sample_rate),
                target_sr=self.target_sample_rate,
                res_type='kaiser_fast'  # Good balance of quality and speed
            )
            return resampled
        except Exception as e:
            logger.error(f"Librosa resampling failed: {e}")
            # Fallback to scipy resampling
            try:
                # Calculate resampling ratio
                ratio = self.target_sample_rate / self.native_sample_rate
                num_samples = int(len(audio_data) * ratio)
                
                # Use scipy signal resampling
                resampled = signal.resample(audio_data, num_samples)
                return resampled.astype(np.float32)
            except Exception as e2:
                logger.error(f"Scipy resampling also failed: {e2}")
                return audio_data  # Return original if all resampling fails
    
    def get_sample_rate_info(self) -> dict:
        """Get information about sample rates"""
        return {
            "native_sample_rate": self.native_sample_rate,
            "target_sample_rate": self.target_sample_rate,
            "resampling_needed": self.native_sample_rate != self.target_sample_rate,
            "resampling_ratio": self.target_sample_rate / self.native_sample_rate if self.native_sample_rate else 1.0
        }