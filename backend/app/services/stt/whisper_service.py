import whisper
import numpy as np
import tempfile
import os
import logging
from typing import Optional, Dict, Any, Callable
from threading import Lock

from app.core.config import settings

logger = logging.getLogger(__name__)


class WhisperService:
    """Whisper speech-to-text service with lazy loading"""
    
    def __init__(self):
        self.model = None
        self.model_name = settings.WHISPER_MODEL
        self.device = settings.WHISPER_DEVICE
        self.language = settings.WHISPER_LANGUAGE
        self._model_lock = Lock()
        self._loading = False
        
        # Callback for state changes
        self.state_callback: Optional[Callable[[str], None]] = None
    
    def set_state_callback(self, callback: Callable[[str], None]):
        """Set callback for state changes"""
        self.state_callback = callback
    
    def _notify_state(self, state: str):
        """Notify state change"""
        if self.state_callback:
            self.state_callback(state)
    
    def _load_model(self) -> bool:
        """Load Whisper model with lazy loading"""
        if self.model is not None:
            return True
        
        with self._model_lock:
            # Double-check locking pattern
            if self.model is not None:
                return True
            
            if self._loading:
                return False
            
            try:
                self._loading = True
                logger.info(f"Loading Whisper model: {self.model_name}")
                
                # Load the model
                self.model = whisper.load_model(
                    self.model_name,
                    device=self.device
                )
                
                logger.info(f"Whisper model {self.model_name} loaded successfully")
                return True
                
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {e}")
                self.model = None
                return False
            finally:
                self._loading = False
    
    def transcribe_audio(self, audio_data: np.ndarray) -> Optional[Dict[str, Any]]:
        """Transcribe audio data using Whisper"""
        if not self._load_model():
            logger.error("Whisper model not available")
            return None
        
        try:
            self._notify_state("transcribing")
            logger.info("Starting Whisper transcription")
            
            # Prepare transcription options
            options = {
                "fp16": False,  # Use fp32 for CPU compatibility
                "language": self.language if self.language else None,
                "task": "transcribe",
                "verbose": False
            }
            
            # Transcribe audio
            result = self.model.transcribe(audio_data, **options)
            
            # Extract relevant information
            transcription_result = {
                "text": result["text"].strip(),
                "language": result.get("language", "unknown"),
                "segments": result.get("segments", []),
                "confidence": self._calculate_average_confidence(result.get("segments", [])),
                "processing_time": None  # Could be measured if needed
            }
            
            logger.info(f"Transcription completed: '{transcription_result['text'][:50]}...'")
            return transcription_result
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return None
    
    async def transcribe_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Transcribe audio file using Whisper"""
        if not self._load_model():
            logger.error("Whisper model not available")
            return None
        
        try:
            self._notify_state("transcribing")
            logger.info(f"Transcribing file: {file_path}")
            
            # Prepare transcription options
            options = {
                "fp16": False,
                "language": self.language if self.language else None,
                "task": "transcribe",
                "verbose": False
            }
            
            # Transcribe file
            result = self.model.transcribe(file_path, **options)
            
            # Extract relevant information
            transcription_result = {
                "text": result["text"].strip(),
                "language": result.get("language", "unknown"),
                "segments": result.get("segments", []),
                "confidence": self._calculate_average_confidence(result.get("segments", [])),
                "processing_time": None
            }
            
            logger.info(f"File transcription completed: '{transcription_result['text'][:50]}...'")
            return transcription_result
            
        except Exception as e:
            logger.error(f"File transcription failed: {e}")
            return None
    
    def transcribe_with_temp_file(self, audio_data: np.ndarray, sample_rate: int = 16000) -> Optional[Dict[str, Any]]:
        """Transcribe audio by saving to temporary file first"""
        temp_file = None
        try:
            # Create temporary WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_file = f.name
            
            # Save audio data to temporary file at the specified sample rate
            import soundfile as sf  # Alternative to wave for numpy arrays
            sf.write(temp_file, audio_data, samplerate=sample_rate, format='WAV')
            
            # Transcribe the file
            result = self.transcribe_file(temp_file)
            
            return result
            
        except Exception as e:
            logger.error(f"Temp file transcription failed: {e}")
            return None
        finally:
            # Clean up temporary file
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except:
                    pass
    
    def _calculate_average_confidence(self, segments: list) -> float:
        """Calculate average confidence from segments"""
        if not segments:
            return 0.0
        
        # Whisper doesn't always provide confidence scores
        # This is a placeholder for future enhancement
        confidences = []
        for segment in segments:
            if "confidence" in segment:
                confidences.append(segment["confidence"])
            elif "avg_logprob" in segment:
                # Convert log probability to rough confidence estimate
                conf = min(1.0, max(0.0, (segment["avg_logprob"] + 1.0)))
                confidences.append(conf)
        
        if confidences:
            return sum(confidences) / len(confidences)
        else:
            # Default confidence when not available
            return 0.85
    
    def is_model_loaded(self) -> bool:
        """Check if model is loaded"""
        return self.model is not None
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model"""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "language": self.language,
            "loaded": self.is_model_loaded(),
            "loading": self._loading
        }
    
    def cleanup(self):
        """Clean up model resources"""
        with self._model_lock:
            if self.model is not None:
                # Whisper models don't need explicit cleanup
                # but we can clear the reference
                self.model = None
                logger.info("Whisper model unloaded")
    
    def change_model(self, model_name: str) -> bool:
        """Change Whisper model"""
        if model_name == self.model_name and self.is_model_loaded():
            return True
        
        # Cleanup current model
        self.cleanup()
        
        # Set new model name
        self.model_name = model_name
        
        # Load new model
        return self._load_model()
    
    def get_available_models(self) -> list:
        """Get list of available Whisper models"""
        return [
            "tiny",
            "tiny.en",
            "base", 
            "base.en",
            "small",
            "small.en",
            "medium",
            "medium.en",
            "large",
            "large-v1",
            "large-v2",
            "large-v3"
        ]