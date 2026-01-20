from fastapi import APIRouter, HTTPException, Path
from typing import List

from app.api.schemas import (
    PreferenceUpdate,
    PreferenceResponse,
    PreferencesListResponse,
    PreferencesBulkUpdate,
    SuccessResponse
)
from app.db import PreferencesRepository
from app.models import Preferences

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("/", response_model=PreferencesListResponse)
async def list_preferences():
    """Get all user preferences"""
    try:
        preferences = await PreferencesRepository.get_all()
        
        preference_responses = [
            PreferenceResponse(
                id=pref.id,
                key=pref.key,
                value=pref.value,
                value_type=pref.value_type,
                description=pref.description,
                typed_value=pref.get_typed_value()
            )
            for pref in preferences
        ]
        
        return PreferencesListResponse(preferences=preference_responses)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get preferences: {str(e)}")


@router.get("/{key}", response_model=PreferenceResponse)
async def get_preference(key: str = Path(..., description="Preference key")):
    """Get a specific preference by key"""
    try:
        preference = await PreferencesRepository.get_by_key(key)
        
        if not preference:
            raise HTTPException(status_code=404, detail="Preference not found")
        
        return PreferenceResponse(
            id=preference.id,
            key=preference.key,
            value=preference.value,
            value_type=preference.value_type,
            description=preference.description,
            typed_value=preference.get_typed_value()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get preference: {str(e)}")


@router.put("/{key}", response_model=PreferenceResponse)
async def update_preference(
    key: str = Path(..., description="Preference key"),
    preference_data: PreferenceUpdate = ...
):
    """Update or create a preference"""
    try:
        # Ensure the key matches
        if preference_data.key != key:
            raise HTTPException(status_code=400, detail="Key in path must match key in body")
        
        # Update or create preference
        preference = await PreferencesRepository.set_value(
            key=preference_data.key,
            value=preference_data.value,
            value_type=preference_data.value_type,
            description=preference_data.description
        )
        
        return PreferenceResponse(
            id=preference.id,
            key=preference.key,
            value=preference.value,
            value_type=preference.value_type,
            description=preference.description,
            typed_value=preference.get_typed_value()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update preference: {str(e)}")


@router.post("/bulk", response_model=SuccessResponse)
async def bulk_update_preferences(preferences_data: PreferencesBulkUpdate):
    """Update multiple preferences at once"""
    try:
        updated_count = 0
        
        for pref_update in preferences_data.preferences:
            await PreferencesRepository.set_value(
                key=pref_update.key,
                value=pref_update.value,
                value_type=pref_update.value_type,
                description=pref_update.description
            )
            updated_count += 1
        
        return SuccessResponse(
            message=f"Successfully updated {updated_count} preferences",
            data={"updated_count": updated_count}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to bulk update preferences: {str(e)}")


@router.delete("/{key}", response_model=SuccessResponse)
async def delete_preference(key: str = Path(..., description="Preference key")):
    """Delete a preference"""
    try:
        # Check if preference exists
        preference = await PreferencesRepository.get_by_key(key)
        
        if not preference:
            raise HTTPException(status_code=404, detail="Preference not found")
        
        # Delete preference
        await PreferencesRepository.delete(key)
        
        return SuccessResponse(
            message="Preference deleted successfully",
            data={"key": key}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete preference: {str(e)}")


@router.get("/values/multiple")
async def get_multiple_preferences(keys: List[str]):
    """Get multiple preference values by keys"""
    try:
        if not keys:
            raise HTTPException(status_code=400, detail="At least one key must be provided")
        
        values = await PreferencesRepository.get_multiple(keys)
        
        return {
            "preferences": values,
            "requested_keys": keys,
            "found_keys": list(values.keys())
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get multiple preferences: {str(e)}")