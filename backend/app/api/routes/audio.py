from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
import tempfile
import os
import shutil
from pathlib import Path
import subprocess
import librosa
import soundfile as sf
import numpy as np

from app.services.stt.whisper_service import WhisperService
from app.core.config import settings

router = APIRouter(prefix="/audio", tags=["audio"])

# Supported audio formats
SUPPORTED_FORMATS = {'.wav', '.mp3', '.m4a', '.aac', '.ogg', '.flac', '.webm', '.opus'}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
TARGET_SAMPLE_RATE = 16000  # Whisper expects 16kHz

def get_whisper_service():
    """Get WhisperService instance"""
    return WhisperService()

def validate_audio_file(file: UploadFile) -> None:
    """Validate uploaded audio file"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    # Check file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file format. Supported formats: {', '.join(SUPPORTED_FORMATS)}"
        )
    
    # Check file size (this is approximate as we haven't read the file yet)
    if hasattr(file, 'size') and file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
        )

def convert_audio_to_wav(input_path: str, output_path: str) -> dict:
    """
    Convert audio file to WAV format with proper sample rate using librosa.
    Returns metadata about the audio file.
    """
    try:
        # Load audio with librosa (handles multiple formats)
        audio_data, original_sr = librosa.load(input_path, sr=None)
        
        # Get duration
        duration = len(audio_data) / original_sr
        
        # Resample to target sample rate if necessary
        if original_sr != TARGET_SAMPLE_RATE:
            audio_data = librosa.resample(audio_data, orig_sr=original_sr, target_sr=TARGET_SAMPLE_RATE)
        
        # Ensure audio is in the right format (float32, mono)
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)
        
        # Save as WAV
        sf.write(output_path, audio_data, TARGET_SAMPLE_RATE, format='WAV')
        
        return {
            'duration': duration,
            'original_sample_rate': original_sr,
            'target_sample_rate': TARGET_SAMPLE_RATE,
            'channels': 1,  # We force mono
            'format': 'WAV'
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to process audio file: {str(e)}"
        )

@router.post("/transcribe")
async def transcribe_audio(
    audio_file: UploadFile = File(...),
    whisper_service: WhisperService = Depends(get_whisper_service)
):
    """
    Upload and transcribe an audio file.
    
    Accepts various audio formats and converts them to the proper format for Whisper.
    Returns the transcription along with metadata.
    """
    # Validate the uploaded file
    validate_audio_file(audio_file)
    
    # Create temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Save uploaded file
            input_path = os.path.join(temp_dir, f"input{Path(audio_file.filename).suffix}")
            with open(input_path, "wb") as buffer:
                shutil.copyfileobj(audio_file.file, buffer)
            
            # Check actual file size after upload
            file_size = os.path.getsize(input_path)
            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large: {file_size // (1024*1024)}MB. Maximum: {MAX_FILE_SIZE // (1024*1024)}MB"
                )
            
            # Convert to WAV format with proper sample rate
            wav_path = os.path.join(temp_dir, "converted.wav")
            audio_metadata = convert_audio_to_wav(input_path, wav_path)
            
            # Transcribe using Whisper
            try:
                transcription_result = await whisper_service.transcribe_file(wav_path)
                
                if not transcription_result or not transcription_result.get('text'):
                    raise HTTPException(
                        status_code=400,
                        detail="Transcription failed - no text was extracted from the audio"
                    )
                
                # Return transcription with metadata
                return JSONResponse({
                    "success": True,
                    "data": {
                        "transcription": transcription_result['text'].strip(),
                        "duration": audio_metadata['duration'],
                        "confidence": transcription_result.get('confidence'),
                        "language": transcription_result.get('language'),
                        "audio_metadata": {
                            "original_filename": audio_file.filename,
                            "file_size": file_size,
                            "duration_seconds": audio_metadata['duration'],
                            "sample_rate": audio_metadata['target_sample_rate'],
                            "format": audio_metadata['format']
                        }
                    }
                })
                
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Transcription failed: {str(e)}"
                )
                
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            # Handle any other unexpected errors
            raise HTTPException(
                status_code=500,
                detail=f"Audio processing failed: {str(e)}"
            )
        finally:
            # Ensure file is closed
            audio_file.file.close()

@router.get("/formats")
async def get_supported_formats():
    """Get list of supported audio formats"""
    return JSONResponse({
        "success": True,
        "data": {
            "supported_formats": list(SUPPORTED_FORMATS),
            "max_file_size_mb": MAX_FILE_SIZE // (1024 * 1024),
            "target_sample_rate": TARGET_SAMPLE_RATE
        }
    })