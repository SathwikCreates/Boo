from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any

from app.api.schemas import SuccessResponse, ErrorResponse
from app.services import STTService, get_stt_service, RecordingState

router = APIRouter(prefix="/stt", tags=["speech-to-text"])


@router.post("/start", response_model=SuccessResponse)
async def start_recording():
    """Start audio recording for speech-to-text"""
    try:
        stt_service = await get_stt_service()
        
        success = stt_service.start_recording()
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Cannot start recording in current state"
            )
        
        return SuccessResponse(
            message="Recording started successfully",
            data={
                "state": stt_service.get_current_state().value,
                "message": "Hold to record, release to stop"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start recording: {str(e)}"
        )


@router.post("/stop", response_model=SuccessResponse)
async def stop_recording():
    """Stop audio recording and start transcription"""
    try:
        stt_service = await get_stt_service()
        
        success = stt_service.stop_recording()
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Cannot stop recording in current state"
            )
        
        return SuccessResponse(
            message="Recording stopped, transcription started",
            data={
                "state": stt_service.get_current_state().value,
                "message": "Processing audio..."
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop recording: {str(e)}"
        )


@router.post("/cancel", response_model=SuccessResponse)
async def cancel_recording():
    """Cancel current recording"""
    try:
        stt_service = await get_stt_service()
        
        success = stt_service.cancel_recording()
        
        return SuccessResponse(
            message="Recording cancelled" if success else "No active recording to cancel",
            data={
                "state": stt_service.get_current_state().value,
                "cancelled": success
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel recording: {str(e)}"
        )


@router.get("/status", response_model=dict)
async def get_recording_status():
    """Get current recording status and state information"""
    try:
        stt_service = await get_stt_service()
        
        state_info = stt_service.get_state_info()
        
        return {
            "success": True,
            "data": {
                **state_info,
                "state_message": stt_service.state_manager.get_state_message(),
                "state_icon": stt_service.state_manager.get_state_icon()
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get status: {str(e)}"
        )


@router.get("/transcription", response_model=dict)
async def get_last_transcription():
    """Get the last transcription result"""
    try:
        stt_service = await get_stt_service()
        
        transcription = stt_service.get_last_transcription()
        
        if not transcription:
            return {
                "success": True,
                "data": None,
                "message": "No transcription available"
            }
        
        return {
            "success": True,
            "data": transcription,
            "message": "Transcription retrieved successfully"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get transcription: {str(e)}"
        )


@router.get("/models", response_model=dict)
async def get_available_models():
    """Get list of available Whisper models"""
    try:
        stt_service = await get_stt_service()
        
        models = stt_service.whisper_service.get_available_models()
        current_model = stt_service.whisper_service.get_model_info()
        
        return {
            "success": True,
            "data": {
                "available_models": models,
                "current_model": current_model,
                "recommendations": {
                    "fastest": "tiny",
                    "balanced": "base", 
                    "most_accurate": "large-v3",
                    "english_only_fast": "base.en",
                    "english_only_accurate": "medium.en"
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get models: {str(e)}"
        )


@router.post("/change-model", response_model=SuccessResponse)
async def change_whisper_model(model_name: str):
    """Change the Whisper model"""
    try:
        stt_service = await get_stt_service()
        
        # Check if recording is active
        if stt_service.state_manager.is_active():
            raise HTTPException(
                status_code=400,
                detail="Cannot change model while recording is active"
            )
        
        # Get available models
        available_models = stt_service.whisper_service.get_available_models()
        
        if model_name not in available_models:
            raise HTTPException(
                status_code=400,
                detail=f"Model '{model_name}' not available. Available models: {available_models}"
            )
        
        # Change model
        success = stt_service.whisper_service.change_model(model_name)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to load model '{model_name}'"
            )
        
        return SuccessResponse(
            message=f"Model changed to '{model_name}' successfully",
            data={
                "model_name": model_name,
                "model_info": stt_service.whisper_service.get_model_info()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to change model: {str(e)}"
        )


@router.get("/devices", response_model=dict)
async def get_audio_devices():
    """Get list of available audio input devices"""
    try:
        stt_service = await get_stt_service()
        
        devices = stt_service.audio_capture.get_input_devices()
        
        return {
            "success": True,
            "data": {
                "devices": devices,
                "count": len(devices)
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get audio devices: {str(e)}"
        )


@router.get("/sample-rates", response_model=dict)
async def get_sample_rate_info():
    """Get sample rate information for dynamic resampling"""
    try:
        stt_service = await get_stt_service()
        
        sample_info = stt_service.audio_capture.get_sample_rate_info()
        
        return {
            "success": True,
            "data": {
                **sample_info,
                "whisper_requirement": "16kHz for optimal performance",
                "resampling_method": "librosa with scipy fallback"
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get sample rate info: {str(e)}"
        )


@router.post("/test", response_model=SuccessResponse)
async def test_stt_service():
    """Test STT service initialization and basic functionality"""
    try:
        stt_service = await get_stt_service()
        
        # Test audio capture initialization
        audio_ok = stt_service.audio_capture.audio is not None
        
        # Test Whisper model info (don't load if not loaded)
        whisper_info = stt_service.whisper_service.get_model_info()
        
        # Get available devices and sample rate info
        devices = stt_service.audio_capture.get_input_devices()
        sample_info = stt_service.audio_capture.get_sample_rate_info()
        
        return SuccessResponse(
            message="STT service test completed",
            data={
                "audio_capture": audio_ok,
                "whisper_model": whisper_info,
                "audio_devices_count": len(devices),
                "sample_rate_info": sample_info,
                "current_state": stt_service.get_current_state().value,
                "service_ready": audio_ok and len(devices) > 0
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"STT service test failed: {str(e)}"
        )