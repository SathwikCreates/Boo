import { useState, useEffect } from 'react'
import { api } from '@/lib/api'

// Session state for voice toggle (persists during session)
let sessionVoiceEnabled: boolean | null = null
let sessionListeners: Array<(enabled: boolean) => void> = []

// Broadcast to all hooks when voice setting changes in session
const broadcastVoiceChange = (enabled: boolean) => {
  sessionVoiceEnabled = enabled
  sessionListeners.forEach(listener => listener(enabled))
}

export function useVoiceSettings() {
  const [voiceEnabled, setVoiceEnabledState] = useState<boolean>(false)
  const [loading, setLoading] = useState(true)
  const [lastUpdateCheck, setLastUpdateCheck] = useState<string | null>(null)

  // Update local state and broadcast to all hooks
  const setVoiceEnabled = (enabled: boolean) => {
    setVoiceEnabledState(enabled)
    broadcastVoiceChange(enabled)
  }

  // Load voice preference from database or session
  const loadVoicePreference = async (forceRefresh = false) => {
    try {
      // If we have session state and not forcing refresh, use that
      if (sessionVoiceEnabled !== null && !forceRefresh) {
        setVoiceEnabledState(sessionVoiceEnabled)
        setLoading(false)
        return
      }

      // Load from database
      const response = await api.getPreferences()
      if (response.success && response.data) {
        const voicePref = response.data.preferences.find(p => p.key === 'voice_enabled')
        // If preference exists, use it; if not, default to false (OFF)
        const enabled = voicePref ? (voicePref.typed_value === true || voicePref.typed_value === 'true') : false

        setVoiceEnabledState(enabled)
        sessionVoiceEnabled = enabled // Store in session
        broadcastVoiceChange(enabled) // Ensure all components sync
      } else {
        // API error - default to OFF
        setVoiceEnabledState(false)
        sessionVoiceEnabled = false
      }
    } catch (error) {
      console.error('Failed to load voice preference:', error)
      setVoiceEnabledState(false) // Default to off on error
      sessionVoiceEnabled = false
    } finally {
      setLoading(false)
    }
  }

  // Load voice preference from database or session on mount
  useEffect(() => {
    loadVoicePreference()

    // Initialize last update check
    const initialTimestamp = localStorage.getItem('voiceSettingsLastUpdated')
    setLastUpdateCheck(initialTimestamp)
  }, [])

  // Poll for settings changes via localStorage
  useEffect(() => {
    const checkForSettingsUpdates = () => {
      const currentTimestamp = localStorage.getItem('voiceSettingsLastUpdated')
      if (currentTimestamp && currentTimestamp !== lastUpdateCheck) {
        setLastUpdateCheck(currentTimestamp)
        loadVoicePreference(true)
      }
    }

    // Initial check
    checkForSettingsUpdates()

    // Check every 1 second
    const interval = setInterval(checkForSettingsUpdates, 1000)

    return () => clearInterval(interval)
  }, [lastUpdateCheck])

  // Listen for changes from other components
  useEffect(() => {
    const listener = (enabled: boolean) => {
      setVoiceEnabledState(enabled)
    }

    sessionListeners.push(listener)

    // Listen for settings page changes
    const handleSettingsChange = (event: CustomEvent) => {
      setVoiceEnabled(event.detail.voiceEnabled)
    }

    // Listen for any settings changes to refresh preferences
    const handleSettingsRefresh = async (event: CustomEvent) => {
      // If voice setting is provided in event detail, use it immediately
      if (event.detail && typeof event.detail.voiceEnabled === 'boolean') {
        setVoiceEnabled(event.detail.voiceEnabled)
      }

      // Also force refresh from database and update timestamp
      const timestamp = Date.now().toString()
      setLastUpdateCheck(timestamp)
      await loadVoicePreference(true)
    }

    window.addEventListener('voiceSettingChanged', handleSettingsChange as EventListener)
    window.addEventListener('settingsChanged', handleSettingsRefresh as unknown as EventListener)

    // Cleanup
    return () => {
      const index = sessionListeners.indexOf(listener)
      if (index > -1) {
        sessionListeners.splice(index, 1)
      }
      window.removeEventListener('voiceSettingChanged', handleSettingsChange as EventListener)
      window.removeEventListener('settingsChanged', handleSettingsRefresh as unknown as EventListener)
    }
  }, [])

  // Save to database (used by settings page)
  const saveVoicePreference = async (enabled: boolean) => {
    try {
      await api.updatePreference('voice_enabled', enabled.toString(), 'bool')
      setVoiceEnabled(enabled)
    } catch (error) {
      console.error('Failed to save voice preference:', error)
      throw error
    }
  }

  return {
    voiceEnabled,
    setVoiceEnabled,
    saveVoicePreference,
    loading
  }
}