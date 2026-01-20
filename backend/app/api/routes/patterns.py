from fastapi import APIRouter, HTTPException
from typing import List, Optional

from app.api.schemas import SuccessResponse
from app.services.patterns import PatternDetector, PatternType
from app.db.repositories import get_preferences_repository
from app.db.database import get_db

router = APIRouter(prefix="/patterns", tags=["patterns"])


@router.get("/check", response_model=SuccessResponse)
async def check_pattern_availability():
    """Check pattern detection availability - now always available"""
    try:
        db = get_db()
        
        # Get current entry count
        result = await db.fetch_one("SELECT COUNT(*) as count FROM entries")
        entry_count = result["count"] if result else 0
        
        return SuccessResponse(
            message="Pattern detection is available",
            data={
                "available": True,
                "entry_count": entry_count,
                "message": "Pattern analysis is available for all users"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check pattern availability: {str(e)}")


@router.post("/analyze", response_model=SuccessResponse)
async def analyze_patterns():
    """Manually trigger pattern analysis - available for all users"""
    try:
        pattern_detector = PatternDetector()
        
        # Run pattern analysis without threshold restrictions
        try:
            patterns = await pattern_detector.analyze_entries(min_entries=1)  # Allow analysis with just 1 entry
            
            return SuccessResponse(
                message=f"Pattern analysis complete",
                data={
                    "patterns_found": len(patterns),
                    "pattern_types": {
                        pattern_type.value: sum(1 for p in patterns if p.pattern_type == pattern_type)
                        for pattern_type in PatternType
                    }
                }
            )
        except Exception as analysis_error:
            print(f"Pattern analysis error: {analysis_error}")
            raise HTTPException(status_code=500, detail=f"Pattern analysis failed: {str(analysis_error)}")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze patterns: {str(e)}")


@router.get("/", response_model=SuccessResponse)
async def get_patterns():
    """Get all detected patterns"""
    try:
        pattern_detector = PatternDetector()
        patterns = await pattern_detector.get_patterns()
        
        # Convert patterns to response format
        pattern_data = []
        for pattern in patterns:
            data = pattern.to_dict()
            # Ensure JSON fields are parsed
            import json
            if isinstance(data.get("related_entries"), str):
                data["related_entries"] = json.loads(data["related_entries"])
            if isinstance(data.get("keywords"), str):
                data["keywords"] = json.loads(data["keywords"])
            pattern_data.append(data)
        
        return SuccessResponse(
            message=f"Retrieved {len(pattern_data)} patterns",
            data={
                "patterns": pattern_data,
                "total": len(pattern_data)
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get patterns: {str(e)}")


@router.get("/entries/{pattern_id}", response_model=SuccessResponse)
async def get_pattern_entries(pattern_id: int):
    """Get entries related to a specific pattern"""
    try:
        db = get_db()
        import json
        
        # Get pattern
        pattern_row = await db.fetch_one(
            "SELECT * FROM patterns WHERE id = ?", (pattern_id,)
        )
        
        if not pattern_row:
            raise HTTPException(status_code=404, detail="Pattern not found")
        
        # Parse related entries
        related_entries = json.loads(pattern_row["related_entries"])
        
        if not related_entries:
            return SuccessResponse(
                message=f"No entries found for pattern {pattern_id}",
                data={
                    "entries": [],
                    "pattern_id": pattern_id,
                    "total": 0
                }
            )
        
        # Fetch entries
        placeholders = ", ".join(["?" for _ in related_entries])
        entries = await db.fetch_all(
            f"""SELECT id, raw_text, enhanced_text, structured_summary, 
                       timestamp, mood_tags, word_count
                FROM entries 
                WHERE id IN ({placeholders})
                ORDER BY timestamp DESC""",
            tuple(related_entries)
        )
        
        # Convert to response format
        entry_data = []
        for entry in entries:
            data = dict(entry)
            if data.get("mood_tags"):
                data["mood_tags"] = json.loads(data["mood_tags"])
            entry_data.append(data)
        
        return SuccessResponse(
            message=f"Retrieved {len(entry_data)} entries for pattern {pattern_id}",
            data={
                "entries": entry_data,
                "pattern_id": pattern_id,
                "total": len(entry_data)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get pattern entries: {str(e)}")


@router.get("/keyword/{keyword}", response_model=SuccessResponse)
async def get_entries_by_keyword(keyword: str):
    """Get entries that contain a specific keyword"""
    try:
        db = get_db()
        import json
        
        # Try multiple search approaches
        search_terms = [keyword]
        
        # If it's a bigram, also search for individual words
        if ' ' in keyword:
            search_terms.extend(keyword.split())
        
        all_found_entries = []
        
        for term in search_terms:
            # Simple substring search
            entries = await db.fetch_all(
                """SELECT DISTINCT id, raw_text, enhanced_text, structured_summary, 
                          timestamp, mood_tags, word_count
                   FROM entries 
                   WHERE (raw_text IS NOT NULL AND LOWER(raw_text) LIKE LOWER(?))
                      OR (enhanced_text IS NOT NULL AND LOWER(enhanced_text) LIKE LOWER(?))
                      OR (structured_summary IS NOT NULL AND LOWER(structured_summary) LIKE LOWER(?))
                   ORDER BY timestamp DESC
                   LIMIT 20""",
                (f"%{term}%", f"%{term}%", f"%{term}%")
            )
            
            all_found_entries.extend(entries)
        
        # Remove duplicates by ID
        seen_ids = set()
        unique_entries = []
        for entry in all_found_entries:
            if entry['id'] not in seen_ids:
                seen_ids.add(entry['id'])
                unique_entries.append(entry)
        
        entries = unique_entries[:20]  # Limit to 20
        
        # If still no results, try word-based search
        if not entries:
            # Try searching for any word in the keyword
            words = keyword.lower().split()
            word_conditions = []
            word_params = []
            
            for word in words:
                if len(word) > 2:  # Skip very short words
                    word_conditions.extend([
                        "LOWER(raw_text) LIKE ?",
                        "LOWER(enhanced_text) LIKE ?",
                        "LOWER(structured_summary) LIKE ?"
                    ])
                    word_params.extend([f"%{word}%", f"%{word}%", f"%{word}%"])
            
            if word_conditions:
                query = f"""
                    SELECT DISTINCT id, raw_text, enhanced_text, structured_summary, 
                           timestamp, mood_tags, word_count
                    FROM entries 
                    WHERE {' OR '.join(word_conditions)}
                    ORDER BY timestamp DESC
                    LIMIT 20
                """
                entries = await db.fetch_all(query, tuple(word_params))
        
        # Convert to response format
        entry_data = []
        for entry in entries:
            data = dict(entry)
            if data.get("mood_tags"):
                data["mood_tags"] = json.loads(data["mood_tags"])
            entry_data.append(data)
        
        return SuccessResponse(
            message=f"Found {len(entry_data)} entries containing '{keyword}'",
            data={
                "entries": entry_data,
                "keyword": keyword,
                "total": len(entry_data)
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search entries by keyword: {str(e)}")