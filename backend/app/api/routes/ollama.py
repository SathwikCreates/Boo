"""
Ollama API endpoints for model management and text generation
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from app.api.schemas import SuccessResponse, ErrorResponse
from app.services.ollama import (
    get_ollama_service,
    OllamaConnectionError,
    OllamaModelNotFoundError,
    OllamaTimeoutError,
    OllamaGenerationError
)

router = APIRouter(prefix="/ollama", tags=["ollama"])


class GenerateRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    system: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False


class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False


class ModelConfigRequest(BaseModel):
    model: str


@router.get("/status", response_model=dict)
async def get_ollama_status():
    """Get Ollama service status and connection info"""
    try:
        ollama_service = await get_ollama_service()
        status = await ollama_service.test_connection()
        
        return {
            "success": True,
            "data": {
                "service": "ollama",
                **status
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "data": {
                "service": "ollama",
                "connected": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
        }


@router.get("/models", response_model=dict)
async def list_models():
    """List all available Ollama models"""
    try:
        ollama_service = await get_ollama_service()
        models = await ollama_service.list_models()
        
        model_list = []
        for model in models:
            model_list.append({
                "name": model.name,
                "modified_at": model.modified_at.isoformat(),
                "size": model.size,
                "size_mb": round(model.size_mb, 2),
                "size_gb": round(model.size_gb, 2),
                "digest": model.digest
            })
        
        return {
            "success": True,
            "data": {
                "models": model_list,
                "count": len(model_list),
                "default_model": ollama_service.get_default_model()
            }
        }
        
    except OllamaConnectionError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to Ollama: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list models: {str(e)}"
        )


@router.get("/models/{model_name}", response_model=dict)
async def get_model_info(model_name: str):
    """Get detailed information about a specific model"""
    try:
        ollama_service = await get_ollama_service()
        model_info = await ollama_service.get_model_info(model_name)
        
        return {
            "success": True,
            "data": {
                "name": model_name,
                "modelfile": model_info.modelfile,
                "parameters": model_info.parameters,
                "template": model_info.template,
                "details": model_info.details
            }
        }
        
    except OllamaModelNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )
    except OllamaConnectionError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to Ollama: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get model info: {str(e)}"
        )


@router.post("/generate", response_model=dict)
async def generate_text(request: GenerateRequest):
    """Generate text using Ollama"""
    try:
        ollama_service = await get_ollama_service()
        
        response = await ollama_service.generate(
            prompt=request.prompt,
            model=request.model,
            system=request.system,
            stream=request.stream,
            options={
                'temperature': request.temperature,
                'num_predict': request.max_tokens
            }
        )
        
        return {
            "success": True,
            "data": {
                "model": response.model,
                "response": response.response,
                "created_at": response.created_at.isoformat(),
                "done": response.done,
                "total_duration_seconds": response.total_duration_seconds,
                "tokens_per_second": response.tokens_per_second,
                "context": response.context,
                "eval_count": response.eval_count
            }
        }
        
    except OllamaModelNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )
    except OllamaTimeoutError as e:
        raise HTTPException(
            status_code=408,
            detail=str(e)
        )
    except OllamaConnectionError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to Ollama: {str(e)}"
        )
    except OllamaGenerationError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Generation failed: {str(e)}"
        )


@router.post("/chat", response_model=dict)
async def chat_completion(request: ChatRequest):
    """Chat completion using Ollama"""
    try:
        ollama_service = await get_ollama_service()
        
        response = await ollama_service.chat(
            messages=request.messages,
            model=request.model,
            stream=request.stream,
            options={
                'temperature': request.temperature,
                'num_predict': request.max_tokens
            }
        )
        
        return {
            "success": True,
            "data": {
                "model": response.model,
                "message": {
                    "role": response.message.role,
                    "content": response.message.content
                },
                "created_at": response.created_at.isoformat(),
                "done": response.done,
                "total_duration_seconds": response.total_duration / 1e9 if response.total_duration else 0,
                "eval_count": response.eval_count
            }
        }
        
    except OllamaModelNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )
    except OllamaTimeoutError as e:
        raise HTTPException(
            status_code=408,
            detail=str(e)
        )
    except OllamaConnectionError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to Ollama: {str(e)}"
        )
    except OllamaGenerationError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Chat completion failed: {str(e)}"
        )


@router.post("/set-default-model", response_model=SuccessResponse)
async def set_default_model(request: ModelConfigRequest):
    """Set the default Ollama model"""
    try:
        ollama_service = await get_ollama_service()
        
        # Check if model exists
        if not await ollama_service.model_exists(request.model):
            raise HTTPException(
                status_code=404,
                detail=f"Model '{request.model}' not found"
            )
        
        ollama_service.set_default_model(request.model)
        
        return SuccessResponse(
            message=f"Default model set to '{request.model}'",
            data={
                "default_model": request.model,
                "previous_model": ollama_service.get_default_model()
            }
        )
        
    except HTTPException:
        raise
    except OllamaConnectionError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to Ollama: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to set default model: {str(e)}"
        )


@router.post("/test", response_model=SuccessResponse)
async def test_ollama_service():
    """Test Ollama service functionality"""
    try:
        ollama_service = await get_ollama_service()
        
        # Test connection
        status = await ollama_service.test_connection()
        
        if not status["connected"]:
            raise HTTPException(
                status_code=503,
                detail=f"Ollama connection test failed: {status.get('error', 'Unknown error')}"
            )
        
        # Test basic generation if models are available
        generation_test = None
        if status["model_count"] > 0:
            try:
                test_response = await ollama_service.generate(
                    prompt="Hello, world!",
                    options={
                        'num_predict': 10,
                        'temperature': 0.1
                    }
                )
                generation_test = {
                    "success": True,
                    "response_length": len(test_response.response),
                    "model_used": test_response.model
                }
            except Exception as e:
                generation_test = {
                    "success": False,
                    "error": str(e)
                }
        
        return SuccessResponse(
            message="Ollama service test completed",
            data={
                "connection": status,
                "generation_test": generation_test,
                "service_ready": status["connected"] and status["model_count"] > 0
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ollama service test failed: {str(e)}"
        )