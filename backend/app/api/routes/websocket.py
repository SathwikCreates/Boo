"""
WebSocket endpoints for real-time STT communication
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional
import logging

from app.services.websocket import get_websocket_manager

router = APIRouter(tags=["websocket"])
logger = logging.getLogger(__name__)


@router.websocket("/ws/stt")
async def websocket_stt_endpoint(
    websocket: WebSocket,
    client_id: Optional[str] = Query(None, description="Optional client identifier")
):
    """
    WebSocket endpoint for real-time STT updates
    
    Message Protocol:
    - Incoming: JSON messages with type and data fields
    - Outgoing: JSON messages for state changes, transcriptions, errors
    
    Channels:
    - stt: Recording state updates
    - transcription: Transcription results
    - hotkey: Hotkey-related updates
    - system: System messages
    """
    websocket_manager = await get_websocket_manager()
    
    # Client info for logging/tracking
    client_info = {
        "client_id": client_id,
        "client_host": websocket.client.host if websocket.client else None,
        "headers": dict(websocket.headers) if hasattr(websocket, 'headers') else {}
    }
    
    logger.info(f"WebSocket connection request from {client_info.get('client_host')} (ID: {client_id})")
    
    try:
        await websocket_manager.handle_connection(websocket, client_info)
    except Exception as e:
        logger.error(f"WebSocket handler error: {e}")


@router.get("/ws/status")
async def get_websocket_status():
    """Get WebSocket service status and statistics"""
    try:
        websocket_manager = await get_websocket_manager()
        stats = websocket_manager.get_connection_stats()
        
        return {
            "success": True,
            "data": {
                "service": "websocket",
                "status": "operational",
                "statistics": stats,
                "channels": {
                    "stt": "Recording state updates",
                    "transcription": "Transcription results", 
                    "hotkey": "Hotkey-related updates",
                    "system": "System messages"
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get WebSocket status: {e}")
        return {
            "success": False,
            "error": str(e)
        }