"""
Ollama API models and data structures
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class OllamaModel(BaseModel):
    """Ollama model information"""
    name: str
    modified_at: datetime
    size: int
    digest: str
    details: Optional[Dict[str, Any]] = None
    
    @property
    def size_mb(self) -> float:
        """Get model size in MB"""
        return self.size / (1024 * 1024)
    
    @property
    def size_gb(self) -> float:
        """Get model size in GB"""
        return self.size / (1024 * 1024 * 1024)


class ModelInfo(BaseModel):
    """Detailed model information from show endpoint"""
    modelfile: str
    parameters: Optional[str] = None
    template: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class GenerateRequest(BaseModel):
    """Request for text generation"""
    model: str
    prompt: str
    system: Optional[str] = None
    template: Optional[str] = None
    context: Optional[List[int]] = None
    stream: bool = False
    raw: bool = False
    format: Optional[str] = None  # json
    options: Optional[Dict[str, Any]] = None
    
    class Config:
        extra = "forbid"


class GenerateResponse(BaseModel):
    """Response from text generation"""
    model: str
    created_at: datetime
    response: str
    done: bool
    context: Optional[List[int]] = None
    total_duration: Optional[int] = None
    load_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    prompt_eval_duration: Optional[int] = None
    eval_count: Optional[int] = None
    eval_duration: Optional[int] = None
    
    @property
    def total_duration_seconds(self) -> float:
        """Get total duration in seconds"""
        return self.total_duration / 1e9 if self.total_duration else 0
    
    @property
    def tokens_per_second(self) -> float:
        """Calculate tokens per second"""
        if self.eval_count and self.eval_duration:
            return self.eval_count / (self.eval_duration / 1e9)
        return 0


class ChatMessage(BaseModel):
    """Chat message for chat endpoint"""
    role: str  # system, user, assistant
    content: str
    images: Optional[List[str]] = None


class ChatRequest(BaseModel):
    """Request for chat completion"""
    model: str
    messages: List[ChatMessage]
    format: Optional[str] = None
    options: Optional[Dict[str, Any]] = None
    stream: bool = False
    keep_alive: Optional[str] = None


class ChatResponse(BaseModel):
    """Response from chat completion"""
    model: str
    created_at: datetime
    message: ChatMessage
    done: bool
    total_duration: Optional[int] = None
    load_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    prompt_eval_duration: Optional[int] = None
    eval_count: Optional[int] = None
    eval_duration: Optional[int] = None


def create_chat_request(
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    top_p: float = 1.0,
    frequency_penalty: float = 0.0,
    presence_penalty: float = 0.0,
    stream: bool = False
) -> ChatRequest:
    """Create a chat request with system and user prompts"""
    messages = []
    
    if system_prompt:
        messages.append(ChatMessage(role="system", content=system_prompt))
    
    messages.append(ChatMessage(role="user", content=user_prompt))
    
    options = {
        "temperature": temperature,
        "top_p": top_p,
        "frequency_penalty": frequency_penalty,
        "presence_penalty": presence_penalty
    }
    
    if max_tokens:
        options["num_predict"] = max_tokens
    
    return ChatRequest(
        model=model,
        messages=messages,
        options=options,
        stream=stream
    )


def create_completion_request(
    model: str,
    prompt: str,
    system: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    top_p: float = 1.0,
    stream: bool = False
) -> GenerateRequest:
    """Create a completion request"""
    options = {
        "temperature": temperature,
        "top_p": top_p
    }
    
    if max_tokens:
        options["num_predict"] = max_tokens
    
    return GenerateRequest(
        model=model,
        prompt=prompt,
        system=system,
        options=options,
        stream=stream
    )