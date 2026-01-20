"""
Ollama service for local LLM integration
"""

import asyncio
import json
import logging
from typing import Optional, List, Dict, Any, AsyncGenerator
import httpx
from datetime import datetime

from app.core.config import settings
from .ollama_models import (
    OllamaModel,
    ModelInfo,
    GenerateRequest,
    GenerateResponse,
    ChatRequest,
    ChatResponse,
    ChatMessage
)
from .ollama_exceptions import (
    OllamaConnectionError,
    OllamaModelNotFoundError,
    OllamaTimeoutError,
    OllamaGenerationError
)

logger = logging.getLogger(__name__)


class OllamaService:
    """Service for interacting with Ollama API"""
    
    def __init__(self, base_url: Optional[str] = None, timeout: Optional[int] = None):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.timeout = timeout or settings.OLLAMA_TIMEOUT
        self._client: Optional[httpx.AsyncClient] = None
        self._available_models: List[OllamaModel] = []
        self._default_model = settings.OLLAMA_DEFAULT_MODEL
        self._connected = False
        self._last_health_check: Optional[datetime] = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()
    
    async def connect(self) -> bool:
        """Initialize connection to Ollama"""
        try:
            if self._client:
                await self._client.aclose()
            
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                headers={"Content-Type": "application/json"}
            )
            
            # Test connection
            response = await self._client.get("/api/tags")
            response.raise_for_status()
            
            self._connected = True
            self._last_health_check = datetime.now()
            logger.info(f"Connected to Ollama at {self.base_url}")
            
            # Load available models
            await self.refresh_models()
            
            return True
            
        except httpx.ConnectError as e:
            self._connected = False
            logger.error(f"Failed to connect to Ollama at {self.base_url}: {e}")
            raise OllamaConnectionError(f"Cannot connect to Ollama at {self.base_url}")
        except Exception as e:
            self._connected = False
            logger.error(f"Unexpected error connecting to Ollama: {e}")
            raise OllamaConnectionError(f"Connection failed: {str(e)}")
    
    async def disconnect(self):
        """Close connection to Ollama"""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._connected = False
        logger.info("Disconnected from Ollama")
    
    async def health_check(self) -> bool:
        """Check if Ollama is healthy and responsive"""
        if not self._client:
            return False
        
        try:
            response = await self._client.get("/api/tags", timeout=5)
            self._connected = response.status_code == 200
            self._last_health_check = datetime.now()
            return self._connected
        except Exception:
            self._connected = False
            return False
    
    async def ensure_connected(self):
        """Ensure we have a valid connection"""
        if not self._connected or not self._client:
            await self.connect()
        
        # Periodic health check
        if self._last_health_check:
            time_since_check = (datetime.now() - self._last_health_check).seconds
            if time_since_check > 30:  # Check every 30 seconds
                await self.health_check()
    
    async def list_models(self) -> List[OllamaModel]:
        """List all available models"""
        await self.ensure_connected()
        
        try:
            response = await self._client.get("/api/tags")
            response.raise_for_status()
            
            data = response.json()
            models = []
            
            for model_data in data.get("models", []):
                model = OllamaModel(
                    name=model_data["name"],
                    modified_at=datetime.fromisoformat(model_data["modified_at"].replace("Z", "+00:00")),
                    size=model_data["size"],
                    digest=model_data["digest"],
                    details=model_data.get("details")
                )
                models.append(model)
            
            self._available_models = models
            logger.info(f"Found {len(models)} available models")
            return models
            
        except httpx.TimeoutException:
            raise OllamaTimeoutError("Request timed out while listing models")
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            raise OllamaConnectionError(f"Failed to list models: {str(e)}")
    
    async def refresh_models(self) -> List[OllamaModel]:
        """Refresh the list of available models"""
        return await self.list_models()
    
    async def get_model_info(self, model_name: str) -> ModelInfo:
        """Get detailed information about a model"""
        await self.ensure_connected()
        
        try:
            response = await self._client.post(
                "/api/show",
                json={"name": model_name}
            )
            
            if response.status_code == 404:
                raise OllamaModelNotFoundError(f"Model '{model_name}' not found")
            
            response.raise_for_status()
            data = response.json()
            
            return ModelInfo(
                modelfile=data.get("modelfile", ""),
                parameters=data.get("parameters"),
                template=data.get("template"),
                details=data.get("details")
            )
            
        except httpx.TimeoutException:
            raise OllamaTimeoutError("Request timed out while getting model info")
        except OllamaModelNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to get model info: {e}")
            raise OllamaConnectionError(f"Failed to get model info: {str(e)}")
    
    async def model_exists(self, model_name: str) -> bool:
        """Check if a model exists"""
        models = await self.list_models()
        return any(model.name == model_name for model in models)
    
    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs
    ) -> GenerateResponse:
        """Generate text using Ollama"""
        await self.ensure_connected()
        
        model = model or self._default_model
        
        # Build options
        options = {
            "temperature": temperature,
            "num_gpu": -1,  # Use all GPU layers for maximum performance
            **kwargs
        }
        
        # Set context window - use from kwargs if provided, otherwise default
        if "num_ctx" not in options:
            options["num_ctx"] = 4096  # Default context length
        
        if max_tokens:
            options["num_predict"] = max_tokens
        
        request = GenerateRequest(
            model=model,
            prompt=prompt,
            system=system,
            options=options,
            stream=stream
        )
        
        try:
            response = await self._client.post(
                "/api/generate",
                json=request.dict(exclude_none=True),
                timeout=None if stream else self.timeout
            )
            
            if response.status_code == 404:
                raise OllamaModelNotFoundError(f"Model '{model}' not found")
            
            response.raise_for_status()
            
            if stream:
                # Return generator for streaming
                return self._stream_response(response)
            else:
                data = response.json()
                return GenerateResponse(**data)
                
        except httpx.TimeoutException:
            raise OllamaTimeoutError(f"Generation timed out after {self.timeout}s")
        except OllamaModelNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            raise OllamaGenerationError(f"Generation failed: {str(e)}")
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs
    ) -> ChatResponse:
        """Chat completion using Ollama"""
        await self.ensure_connected()
        
        model = model or self._default_model
        
        # Convert dict messages to ChatMessage objects
        chat_messages = []
        for msg in messages:
            chat_messages.append(ChatMessage(
                role=msg["role"],
                content=msg["content"]
            ))
        
        # Build options
        options = {
            "temperature": temperature,
            "num_gpu": -1,  # Use all GPU layers for maximum performance
            **kwargs
        }
        
        # Set context window - use from kwargs if provided, otherwise default
        if "num_ctx" not in options:
            options["num_ctx"] = 4096  # Default context length
        
        if max_tokens:
            options["num_predict"] = max_tokens
        
        request = ChatRequest(
            model=model,
            messages=chat_messages,
            options=options,
            stream=stream
        )
        
        try:
            response = await self._client.post(
                "/api/chat",
                json=request.dict(exclude_none=True),
                timeout=None if stream else self.timeout
            )
            
            if response.status_code == 404:
                raise OllamaModelNotFoundError(f"Model '{model}' not found")
            
            response.raise_for_status()
            
            if stream:
                # Return generator for streaming
                return self._stream_chat_response(response)
            else:
                data = response.json()
                return ChatResponse(**data)
                
        except httpx.TimeoutException:
            raise OllamaTimeoutError(f"Chat timed out after {self.timeout}s")
        except OllamaModelNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Chat failed: {e}")
            raise OllamaGenerationError(f"Chat failed: {str(e)}")
    
    async def _stream_response(self, response: httpx.Response) -> AsyncGenerator[GenerateResponse, None]:
        """Stream generation responses"""
        async for line in response.aiter_lines():
            if line:
                try:
                    data = json.loads(line)
                    yield GenerateResponse(**data)
                except Exception as e:
                    logger.error(f"Failed to parse streaming response: {e}")
    
    async def _stream_chat_response(self, response: httpx.Response) -> AsyncGenerator[ChatResponse, None]:
        """Stream chat responses"""
        async for line in response.aiter_lines():
            if line:
                try:
                    data = json.loads(line)
                    yield ChatResponse(**data)
                except Exception as e:
                    logger.error(f"Failed to parse streaming chat response: {e}")
    
    def get_available_models(self) -> List[str]:
        """Get list of available model names"""
        return [model.name for model in self._available_models]
    
    def set_default_model(self, model_name: str):
        """Set the default model"""
        self._default_model = model_name
        logger.info(f"Default model set to: {model_name}")
    
    def get_default_model(self) -> str:
        """Get the default model"""
        return self._default_model
    
    def is_connected(self) -> bool:
        """Check if connected to Ollama"""
        return self._connected
    
    async def generate_with_tools(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate text with function calling support.
        
        Args:
            request: Ollama request with tools parameter
            
        Returns:
            Ollama response with potential tool calls
        """
        await self.ensure_connected()
        
        try:
            # Send request to Ollama with tools
            response = await self._client.post(
                "/api/generate",
                json=request,
                timeout=self.timeout
            )
            
            if response.status_code == 404:
                model = request.get("model", "unknown")
                raise OllamaModelNotFoundError(f"Model '{model}' not found")
            
            response.raise_for_status()
            
            # Handle Ollama streaming response format (multiple JSON lines)
            response_text = response.text
            logger.info(f"Raw Ollama response: {response_text[:300]}...")
            
            # Ollama often returns multiple JSON objects separated by newlines
            # We need the last complete JSON object
            lines = response_text.strip().split('\n')
            
            # Try to parse from the last line backwards
            for line in reversed(lines):
                if line.strip():
                    try:
                        data = json.loads(line)
                        logger.info(f"Parsed Ollama data: {data}")
                        return data
                    except json.JSONDecodeError:
                        continue
            
            # If no valid JSON found, try parsing the entire response
            try:
                data = response.json()
                return data
            except json.JSONDecodeError:
                logger.error(f"Failed to parse Ollama response: {response_text[:200]}...")
                raise OllamaGenerationError("Invalid response format from Ollama")
                
        except httpx.TimeoutException:
            raise OllamaTimeoutError(f"Generation timed out after {self.timeout}s")
        except OllamaModelNotFoundError:
            raise
        except httpx.HTTPStatusError as e:
            raise OllamaGenerationError(f"HTTP error {e.response.status_code}: {e.response.text}")
        except Exception as e:
            logger.error(f"Error generating with tools: {e}")
            raise OllamaGenerationError(f"Generation failed: {str(e)}")

    async def test_connection(self) -> Dict[str, Any]:
        """Test connection and return status info"""
        try:
            await self.connect()
            models = await self.list_models()
            
            return {
                "connected": True,
                "base_url": self.base_url,
                "model_count": len(models),
                "models": [model.name for model in models],
                "default_model": self._default_model,
                "default_model_available": self._default_model in [m.name for m in models]
            }
        except Exception as e:
            return {
                "connected": False,
                "base_url": self.base_url,
                "error": str(e),
                "error_type": type(e).__name__
            }


# Global Ollama service instance
_ollama_service: Optional[OllamaService] = None


async def get_ollama_service() -> OllamaService:
    """Get global Ollama service instance"""
    global _ollama_service
    
    if _ollama_service is None:
        _ollama_service = OllamaService()
        # Don't auto-connect, let it connect on first use
    
    return _ollama_service