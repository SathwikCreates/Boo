"""
Mood Analysis Service for extracting emotional tags from journal entries.
"""

from typing import List, Optional
import json
import logging
from datetime import datetime

from app.services.ollama import OllamaService, get_ollama_service
from app.db.repositories.preferences_repository import PreferencesRepository
from app.core.config import settings

logger = logging.getLogger(__name__)


class MoodAnalysisService:
    """Service for analyzing mood and emotional content from journal text."""
    
    def __init__(self, ollama_service: OllamaService):
        self.ollama_service = ollama_service
        self._mood_system_prompt = """You are a mood and emotion analyzer for personal journal entries. Your task is to identify the emotional states and moods expressed in the text.

INSTRUCTIONS:
1. Analyze the emotional content of the journal entry
2. Identify specific moods and emotional states
3. Return ONLY a JSON array of mood tags
4. Use simple, clear mood words (e.g., "happy", "stressed", "excited", "anxious", "grateful", "tired", "frustrated", "content", "overwhelmed", "peaceful")
5. Include 1-5 mood tags maximum
6. Focus on the dominant emotions expressed
7. Use consistent mood vocabulary

FORBIDDEN:
- Do not add explanations or commentary
- Do not include non-emotional descriptors
- Do not repeat similar moods
- Do not include activities or events, only emotions

EXAMPLE OUTPUT:
["happy", "excited", "grateful"]

Return only the JSON array, nothing else."""

    async def analyze_mood(self, text: str) -> List[str]:
        """
        Analyze the mood of the given text and return mood tags.
        
        Args:
            text: The journal text to analyze (preferably enhanced text)
            
        Returns:
            List of mood tags extracted from the text
        """
        if not text or not text.strip():
            return []
        
        start_time = datetime.now()
        
        try:
            # Get preferences from database
            model = await PreferencesRepository.get_value('ollama_model', settings.OLLAMA_DEFAULT_MODEL)
            temperature = await PreferencesRepository.get_value('ollama_temperature', 0.2)
            context_window = await PreferencesRepository.get_value('ollama_context_window', 4096)
            
            # Call LLM for mood analysis
            response = await self.ollama_service.generate(
                prompt=text,
                system=self._mood_system_prompt,
                model=model,
                options={
                    'temperature': temperature,
                    'num_ctx': context_window,
                    'num_gpu': -1  # Use all GPU layers for maximum performance
                }
            )
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Parse the response
            mood_tags = self._parse_mood_response(response.response.strip())
            
            logger.info(f"Mood analysis completed in {processing_time:.0f}ms, found {len(mood_tags)} moods: {mood_tags}")
            
            return mood_tags
        
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Mood analysis failed after {processing_time:.0f}ms: {str(e)}")
            return []  # Return empty list on failure, don't break the flow

    def _parse_mood_response(self, response: str) -> List[str]:
        """Parse the LLM response to extract mood tags."""
        try:
            # Try to parse as JSON first
            if response.startswith('[') and response.endswith(']'):
                mood_tags = json.loads(response)
                if isinstance(mood_tags, list):
                    # Clean and validate mood tags
                    cleaned_moods = []
                    for mood in mood_tags:
                        if isinstance(mood, str) and mood.strip():
                            cleaned_mood = mood.strip().lower()
                            # Basic validation - single word moods only
                            if len(cleaned_mood.split()) == 1 and len(cleaned_mood) <= 20:
                                cleaned_moods.append(cleaned_mood)
                    
                    return cleaned_moods[:5]  # Maximum 5 moods
            
            # Fallback: try to extract words from response
            words = response.lower().replace('[', '').replace(']', '').replace('"', '').replace("'", '')
            mood_candidates = [word.strip() for word in words.split(',')]
            
            # Filter valid mood words
            moods = []
            common_moods = {
                'happy', 'sad', 'excited', 'anxious', 'stressed', 'calm', 'angry', 'frustrated',
                'grateful', 'tired', 'energetic', 'peaceful', 'overwhelmed', 'content', 'worried',
                'hopeful', 'disappointed', 'proud', 'confused', 'relieved', 'nervous', 'confident',
                'lonely', 'loved', 'inspired', 'bored', 'surprised', 'scared', 'optimistic'
            }
            
            for mood in mood_candidates:
                clean_mood = mood.strip().lower()
                if clean_mood in common_moods and clean_mood not in moods:
                    moods.append(clean_mood)
                    if len(moods) >= 5:
                        break
            
            return moods
        
        except Exception as e:
            logger.warning(f"Failed to parse mood response '{response}': {str(e)}")
            return []


# Dependency injection
_mood_analysis_service: Optional[MoodAnalysisService] = None


async def get_mood_analysis_service() -> MoodAnalysisService:
    """Get the mood analysis service instance."""
    global _mood_analysis_service
    
    if _mood_analysis_service is None:
        ollama_service = await get_ollama_service()
        _mood_analysis_service = MoodAnalysisService(ollama_service)
    
    return _mood_analysis_service