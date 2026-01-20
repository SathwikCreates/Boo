from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from pydantic import BaseModel

from app.api.schemas import SuccessResponse, ErrorResponse
from app.services.hotkey import get_hotkey_service, validate_hotkey

router = APIRouter(prefix="/hotkey", tags=["hotkey"])


class HotkeyChangeRequest(BaseModel):
    hotkey: str


class HotkeyValidationRequest(BaseModel):
    hotkey: str


@router.get("/status", response_model=dict)
async def get_hotkey_status():
    """Get current hotkey status and configuration"""
    try:
        hotkey_service = await get_hotkey_service()
        status = hotkey_service.get_status()
        
        return {
            "success": True,
            "data": status
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get hotkey status: {str(e)}"
        )


@router.get("/current", response_model=dict)
async def get_current_hotkey():
    """Get the currently configured hotkey"""
    try:
        hotkey_service = await get_hotkey_service()
        
        return {
            "success": True,
            "data": {
                "hotkey": hotkey_service.get_current_hotkey(),
                "active": hotkey_service.is_hotkey_active(),
                "registered": hotkey_service.hotkey_registered
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get current hotkey: {str(e)}"
        )


@router.post("/change", response_model=SuccessResponse)
async def change_hotkey(request: HotkeyChangeRequest):
    """Change the recording hotkey"""
    try:
        hotkey_service = await get_hotkey_service()
        
        result = await hotkey_service.change_hotkey(request.hotkey)
        
        if not result['success']:
            raise HTTPException(
                status_code=400,
                detail=result['message']
            )
        
        response_data = {
            "old_hotkey": result.get('old_hotkey'),
            "new_hotkey": result.get('new_hotkey'),
            "message": result['message']
        }
        
        if 'warnings' in result:
            response_data['warnings'] = result['warnings']
        
        return SuccessResponse(
            message=result['message'],
            data=response_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to change hotkey: {str(e)}"
        )


@router.post("/validate", response_model=dict)
async def validate_hotkey_endpoint(request: HotkeyValidationRequest):
    """Validate a hotkey string"""
    try:
        validation = validate_hotkey(request.hotkey)
        
        return {
            "success": True,
            "data": {
                "valid": validation['valid'],
                "parsed": validation['parsed'],
                "errors": validation['errors'],
                "warnings": validation['warnings']
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to validate hotkey: {str(e)}"
        )


@router.get("/suggestions", response_model=dict)
async def get_hotkey_suggestions():
    """Get recommended hotkey combinations"""
    try:
        hotkey_service = await get_hotkey_service()
        suggestions = hotkey_service.get_hotkey_suggestions()
        
        return {
            "success": True,
            "data": {
                "suggestions": suggestions,
                "current": hotkey_service.get_current_hotkey(),
                "description": "Recommended hotkey combinations for voice recording"
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get hotkey suggestions: {str(e)}"
        )


@router.post("/enable", response_model=SuccessResponse)
async def enable_hotkey():
    """Enable the current hotkey"""
    try:
        hotkey_service = await get_hotkey_service()
        
        success = hotkey_service.set_hotkey_active(True)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to enable hotkey - hotkey may not be registered"
            )
        
        return SuccessResponse(
            message="Hotkey enabled successfully",
            data={
                "hotkey": hotkey_service.get_current_hotkey(),
                "active": True
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to enable hotkey: {str(e)}"
        )


@router.post("/disable", response_model=SuccessResponse)
async def disable_hotkey():
    """Disable the current hotkey"""
    try:
        hotkey_service = await get_hotkey_service()
        
        success = hotkey_service.set_hotkey_active(False)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to disable hotkey - hotkey may not be registered"
            )
        
        return SuccessResponse(
            message="Hotkey disabled successfully",
            data={
                "hotkey": hotkey_service.get_current_hotkey(),
                "active": False
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to disable hotkey: {str(e)}"
        )


@router.post("/test", response_model=SuccessResponse)
async def test_hotkey_service():
    """Test hotkey service functionality"""
    try:
        hotkey_service = await get_hotkey_service()
        status = hotkey_service.get_status()
        
        # Test validation
        test_validation = validate_hotkey("f8")
        
        return SuccessResponse(
            message="Hotkey service test completed",
            data={
                "service_status": status,
                "test_validation": {
                    "hotkey": "f8",
                    "valid": test_validation['valid']
                },
                "service_ready": (
                    status['service_running'] and 
                    status['hotkey_registered'] and
                    status['stt_service_available']
                )
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Hotkey service test failed: {str(e)}"
        )