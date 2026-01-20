"""
Smart Auto-Tagging Service for Boo Diary

This service automatically detects and tags entry content with semantic labels
to improve searchability and organization without showing tags to users.
"""

import re
import logging
from typing import List, Dict, Any, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)


class SmartTaggingService:
    """Service for automatically tagging diary entries based on content patterns."""
    
    def __init__(self):
        """Initialize the smart tagging service."""
        self.pattern_cache = {}
    
    @lru_cache(maxsize=100)
    def detect_patterns(self, text: str) -> List[str]:
        """Detect patterns in text and return appropriate tags."""
        if not text or not text.strip():
            return []
        
        text_lower = text.lower().strip()
        tags = []
        
        # 1. Question detection
        if self._contains_questions(text):
            tags.append("question")
        
        # 2. Idea/Concept detection
        if self._contains_ideas(text_lower):
            tags.append("idea")
        
        # 3. Action item/TODO detection
        if self._contains_action_items(text_lower):
            tags.append("todo")
        
        # 4. Decision detection
        if self._contains_decisions(text_lower):
            tags.append("decision")
        
        # 5. Learning detection
        if self._contains_learning(text_lower):
            tags.append("learning")
        
        # 6. Reference/Link detection
        if self._contains_references(text):
            tags.append("reference")
        
        # 7. Meeting notes detection
        if self._contains_meeting_patterns(text_lower):
            tags.append("meeting")
        
        # 8. Project mentions
        project_tags = self._detect_project_mentions(text_lower)
        tags.extend(project_tags)
        
        return list(set(tags))  # Remove duplicates
    
    def _contains_questions(self, text: str) -> bool:
        """Detect if text contains questions."""
        return bool(re.search(r'\?', text))
    
    def _contains_ideas(self, text_lower: str) -> bool:
        """Detect if text contains ideas or concepts."""
        idea_patterns = [
            r'\bidea\b', r'\bthought\b', r'\bconcept\b', r'\bnotion\b',
            r'\bwhat if\b', r'\bmaybe\b', r'\bcould\b', r'\bmight\b',
            r'\bbrainstorm\b', r'\binsight\b', r'\binspiration\b',
            r'\bpotential\b', r'\bpossibility\b', r'\bapproach\b',
            r'\bstrategy\b', r'\bsolution\b', r'\binnovation\b'
        ]
        return any(re.search(pattern, text_lower) for pattern in idea_patterns)
    
    def _contains_action_items(self, text_lower: str) -> bool:
        """Detect action items and TODOs."""
        action_patterns = [
            r'\btodo\b', r'\bto-do\b', r'\btask\b', r'\bneed to\b',
            r'\bshould\b', r'\bmust\b', r'\bhave to\b', r'\bremember to\b',
            r'\baction\b', r'\bfollow up\b', r'\bfollowup\b',
            r'\b\[\s*\]\b',  # Empty checkbox
            r'\b- \[ \]\b',  # Markdown checkbox
            r'\bdo\b.*\btomorrow\b', r'\bdo\b.*\bnext\b'
        ]
        return any(re.search(pattern, text_lower) for pattern in action_patterns)
    
    def _contains_decisions(self, text_lower: str) -> bool:
        """Detect decisions made."""
        decision_patterns = [
            r'\bdecided\b', r'\bdecision\b', r'\bchose\b', r'\bgoing with\b',
            r'\bwill go\b', r'\bwill use\b', r'\bwill do\b', r'\bwill try\b',
            r'\bfinal\b', r'\bconclusion\b', r'\bresolved\b', r'\bsettled\b'
        ]
        return any(re.search(pattern, text_lower) for pattern in decision_patterns)
    
    def _contains_learning(self, text_lower: str) -> bool:
        """Detect learning content."""
        learning_patterns = [
            r'\btil\b', r'\btoday i learned\b', r'\blearned\b', r'\bdiscovered\b',
            r'\brealized\b', r'\bunderstood\b', r'\bfigured out\b',
            r'\binsight\b', r'\brevelation\b', r'\bknowledge\b',
            r'\bskill\b', r'\bstudied\b', r'\bresearch\b'
        ]
        return any(re.search(pattern, text_lower) for pattern in learning_patterns)
    
    def _contains_references(self, text: str) -> bool:
        """Detect references, links, and resources."""
        # URL patterns
        url_pattern = r'https?://[^\s]+|www\.[^\s]+|[^\s]+\.(com|org|net|edu|gov)'
        
        # Book/article patterns
        reference_patterns = [
            url_pattern,
            r'\bbook\b.*\btitle\b', r'\barticle\b.*\bby\b',
            r'\bpaper\b', r'\bresource\b', r'\blink\b',
            r'\breference\b', r'\bsource\b', r'\bdocumentation\b'
        ]
        
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in reference_patterns)
    
    def _contains_meeting_patterns(self, text_lower: str) -> bool:
        """Detect meeting notes."""
        meeting_patterns = [
            r'\bmeeting\b', r'\bcall\b', r'\bdiscussion\b', r'\bconference\b',
            r'\bagenda\b', r'\bminutes\b', r'\battendees\b', r'\baction items\b',
            r'\bnext steps\b', r'\bpresentation\b', r'\bstakeholder\b'
        ]
        return any(re.search(pattern, text_lower) for pattern in meeting_patterns)
    
    def _detect_project_mentions(self, text_lower: str) -> List[str]:
        """Detect project-specific mentions."""
        project_tags = []
        
        # Common project keywords
        project_patterns = {
            'project:web': [r'\bwebsite\b', r'\bweb app\b', r'\bfrontend\b', r'\bbackend\b', r'\bapi\b'],
            'project:mobile': [r'\bmobile\b', r'\bapp\b', r'\bios\b', r'\bandroid\b'],
            'project:ml': [r'\bmachine learning\b', r'\bml\b', r'\bai\b', r'\bmodel\b', r'\balgorithm\b'],
            'project:research': [r'\bresearch\b', r'\bpaper\b', r'\bstudy\b', r'\banalysis\b'],
            'project:startup': [r'\bstartup\b', r'\bbusiness\b', r'\bcompany\b', r'\bproduct\b']
        }
        
        for tag, patterns in project_patterns.items():
            if any(re.search(pattern, text_lower) for pattern in patterns):
                project_tags.append(tag)
        
        return project_tags
    
    def generate_smart_tags(self, text: str) -> Dict[str, Any]:
        """Generate smart tags for an entry."""
        if not text or not text.strip():
            return {"tags": [], "metadata": {}}
        
        # Detect patterns
        tags = self.detect_patterns(text)
        
        # Generate metadata
        metadata = {
            "auto_tagged": True,
            "tag_count": len(tags),
            "word_count": len(text.split()),
            "has_questions": "question" in tags,
            "has_actions": "todo" in tags,
            "has_ideas": "idea" in tags
        }
        
        logger.debug(f"Generated tags for text: {tags}")
        
        return {
            "tags": tags,
            "metadata": metadata
        }
    
    def enhance_processing_metadata(self, existing_metadata: Optional[Dict[str, Any]], smart_tags: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance existing processing metadata with smart tags."""
        if existing_metadata is None:
            existing_metadata = {}
        
        # Add smart tagging data
        existing_metadata["smart_tags"] = smart_tags["tags"]
        existing_metadata["tagging_metadata"] = smart_tags["metadata"]
        
        return existing_metadata


# Global service instance
_smart_tagging_service: Optional[SmartTaggingService] = None


def get_smart_tagging_service() -> SmartTaggingService:
    """Get the global smart tagging service instance."""
    global _smart_tagging_service
    if _smart_tagging_service is None:
        _smart_tagging_service = SmartTaggingService()
    return _smart_tagging_service