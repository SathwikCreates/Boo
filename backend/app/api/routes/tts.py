"""
TTS API endpoints for text-to-speech synthesis.

This module provides endpoints for:
- Text-to-speech synthesis with piper-tts
- Streaming audio generation for conversational use
"""

import logging
import os
from typing import Optional, List
from pathlib import Path
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.schemas import SuccessResponse, ErrorResponse
from app.services.tts_service import get_tts_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tts", tags=["tts"])


# Request Models
class TTSSynthesizeRequest(BaseModel):
    """Request model for TTS synthesis."""
    text: str = Field(..., min_length=1, max_length=5000, description="Text to convert to speech")
    stream: bool = Field(True, description="Whether to stream audio for faster response")


# Response Models
class TTSModelInfoResponse(BaseModel):
    """Response model for TTS model information."""
    model_name: str = Field(..., description="Name of the TTS model")
    is_initialized: bool = Field(..., description="Whether the model is initialized")
    sample_rate: int = Field(..., description="Audio sample rate")
    channels: int = Field(..., description="Number of audio channels")
    model_path: str = Field(..., description="Path to the model file")


class TTSVoiceOption(BaseModel):
    """Response model for available TTS voice options."""
    name: str = Field(..., description="Display name for the voice")
    filename: str = Field(..., description="Filename without extension")


class TTSVoicesResponse(BaseModel):
    """Response model for available TTS voices."""
    voices: List[TTSVoiceOption] = Field(..., description="List of available voice options")


@router.get("/voices", response_model=SuccessResponse[TTSVoicesResponse])
async def get_available_voices():
    """
    Get list of available TTS voice models from the TTS directory.
    
    Returns:
        List of voice models found in backend/TTS directory
    """
    try:
        # Get the TTS directory path
        # Try TTS folder first (when running from backend)
        tts_dir = Path("TTS")
        if not tts_dir.exists():
            # Try with backend prefix (when running from project root)
            tts_dir = Path("backend/TTS")
        
        voices = []
        
        # Look for .onnx files in the directory
        if tts_dir.exists() and tts_dir.is_dir():
            for file_path in tts_dir.glob("*.onnx"):
                # Skip .onnx.json files
                if not file_path.name.endswith(".onnx.json"):
                    filename_without_ext = file_path.stem
                    # Create a display name from the filename
                    display_name = filename_without_ext.replace("_", " ").replace("-", " ").title()
                    
                    voices.append(TTSVoiceOption(
                        name=display_name,
                        filename=filename_without_ext
                    ))
        
        return SuccessResponse(
            success=True,
            message="Available voices retrieved successfully",
            data=TTSVoicesResponse(voices=voices)
        )
        
    except Exception as e:
        logger.error(f"Failed to get available voices: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get available voices: {str(e)}"
        )


@router.post("/synthesize")
async def synthesize_speech(request: TTSSynthesizeRequest):
    """
    Convert text to speech using piper-tts.
    
    Args:
        request: TTS synthesis parameters
        
    Returns:
        Audio file (WAV) as response or streaming response
        
    Raises:
        HTTPException: If synthesis fails
    """
    try:
        logger.info(f"TTS request - text: '{request.text[:50]}...', stream: {request.stream}")
        
        tts_service = get_tts_service()
        
        # Generate speech audio
        audio_result = await tts_service.synthesize_speech(
            text=request.text,
            stream=request.stream
        )
        
        # Check if result is streaming (async generator) or complete (bytes)
        if hasattr(audio_result, '__aiter__'):
            # Streaming response
            async def audio_generator():
                async for chunk in audio_result:
                    yield chunk
            
            return StreamingResponse(
                audio_generator(),
                media_type="audio/wav",
                headers={
                    "Content-Disposition": "inline; filename=speech.wav",
                    "Cache-Control": "no-cache"
                }
            )
        else:
            # Complete audio file (bytes)
            return Response(
                content=audio_result,
                media_type="audio/wav",
                headers={
                    "Content-Disposition": "inline; filename=speech.wav",
                    "Content-Length": str(len(audio_result))
                }
            )
        
    except ValueError as e:
        logger.error(f"Invalid TTS request: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"TTS synthesis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Speech synthesis failed: {str(e)}"
        )


@router.get("/model-info", response_model=SuccessResponse[TTSModelInfoResponse])
async def get_tts_model_info():
    """
    Get information about the loaded TTS model.
    
    Returns:
        TTS model information and status
        
    Raises:
        HTTPException: If model info retrieval fails
    """
    try:
        tts_service = get_tts_service()
        
        model_info = await tts_service.get_model_info()
        
        response_data = TTSModelInfoResponse(**model_info)
        
        return SuccessResponse(
            success=True,
            message="TTS model information retrieved successfully",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"Failed to get TTS model info: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get model information: {str(e)}"
        )


@router.post("/initialize", response_model=SuccessResponse[dict])
async def initialize_tts_model():
    """
    Initialize the TTS model.
    
    This endpoint triggers model loading and can be used to warm up the service.
    
    Returns:
        Success response indicating initialization status
        
    Raises:
        HTTPException: If initialization fails
    """
    try:
        tts_service = get_tts_service()
        
        await tts_service.initialize()
        
        # Get model info after initialization
        model_info = await tts_service.get_model_info()
        
        return SuccessResponse(
            success=True,
            message="TTS model initialized successfully",
            data={
                "status": "initialized",
                "model_name": model_info.get("model_name", "Unknown")
            }
        )
        
    except Exception as e:
        logger.error(f"TTS initialization failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize TTS model: {str(e)}"
        )


@router.get("/status", response_model=SuccessResponse[dict])
async def get_tts_status():
    """
    Get current TTS service status.
    
    Returns:
        TTS service status and readiness
    """
    try:
        tts_service = get_tts_service()
        
        is_ready = tts_service.is_ready()
        
        # Get current model name
        model_name = "Not loaded"
        if is_ready:
            try:
                model_info = await tts_service.get_model_info()
                model_name = model_info.get("model_name", "Unknown")
            except:
                pass
        
        return SuccessResponse(
            success=True,
            message="TTS status retrieved successfully",
            data={
                "is_ready": is_ready,
                "is_initialized": tts_service._is_initialized,
                "model_name": model_name
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get TTS status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get TTS status: {str(e)}"
        )