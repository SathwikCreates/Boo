"""
Custom exceptions for Ollama service
"""


class OllamaException(Exception):
    """Base exception for Ollama service"""
    pass


class OllamaConnectionError(OllamaException):
    """Raised when unable to connect to Ollama"""
    pass


class OllamaModelNotFoundError(OllamaException):
    """Raised when requested model is not found"""
    pass


class OllamaTimeoutError(OllamaException):
    """Raised when Ollama request times out"""
    pass


class OllamaGenerationError(OllamaException):
    """Raised when text generation fails"""
    pass