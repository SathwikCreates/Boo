import { useState, useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Calendar as CalendarComponent } from '@/components/ui/calendar'
import { Mic, MicOff, Loader2, Keyboard, CheckCircle, Plus, FileText, Pen, BookOpen, Sparkles, Edit3, Save, X, Star, Lightbulb, Calendar, Clock, AlertCircle } from 'lucide-react'
import { useToast } from '@/components/ui/use-toast'
import { motion, AnimatePresence } from 'framer-motion'
import { api } from '@/lib/api'
import { wsClient } from '@/lib/websocket'
import type { STTState, TranscriptionResult } from '@/lib/websocket'

// Recording states based on backend implementation
const RecordingState = {
  IDLE: 'idle',
  RECORDING: 'recording',
  PROCESSING: 'processing',
  TRANSCRIBING: 'transcribing',
  ENHANCING: 'enhancing',
  SUCCESS: 'success'
}

// View modes configuration (same as home page)
const viewModes = [
  {
    icon: FileText,
    title: "Raw Transcription",
    description: "Your exact words, unfiltered and authentic",
    gradient: "from-blue-500 to-blue-600",
    mode: "raw"
  },
  {
    icon: Pen,
    title: "Enhanced Style",
    description: "Improved grammar and tone while preserving your intent",
    gradient: "from-purple-500 to-pink-500",
    mode: "enhanced"
  },
  {
    icon: BookOpen,
    title: "Structured Summary",
    description: "Organized into coherent themes and key points",
    gradient: "from-emerald-500 to-teal-500",
    mode: "structured"
  }
]

// Quirky loading messages
const loadingMessages = [
  "Your memories are being created...",
  "Your voice is heard...",
  "Weaving your thoughts together...",
  "AI is polishing your words...",
  "Crafting your story...",
  "Organizing your thoughts...",
  "Making magic happen...",
  "Your journal is coming to life...",
  "Processing your wisdom...",
  "Creating something beautiful..."
]

interface CreatedEntries {
  raw: {
    id: number
    raw_text: string
    timestamp: string
  }
  enhanced?: {
    id: number
    enhanced_text: string
  }
  structured?: {
    id: number
    structured_summary: string
  }
}

function NewEntryPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const [text, setText] = useState('')
  const [recordingState, setRecordingState] = useState(RecordingState.IDLE)
  const [isProcessing, setIsProcessing] = useState(false)
  const [createdEntries, setCreatedEntries] = useState<CreatedEntries | null>(null)
  const [processingMetadata, setProcessingMetadata] = useState<any>(null)
  const [currentHotkey, setCurrentHotkey] = useState('F8')
  const [isConnected, setIsConnected] = useState(false)
  const [processingJobId, setProcessingJobId] = useState<string | null>(null)
  const [recordingSource, setRecordingSource] = useState<'hotkey' | 'button' | null>(null)

  // Auto-save state
  const [autoSaveEnabled, setAutoSaveEnabled] = useState(true)
  const [autoSaveInterval, setAutoSaveInterval] = useState(30) // seconds
  const [lastAutoSave, setLastAutoSave] = useState<Date | null>(null)
  const [isAutoSaving, setIsAutoSaving] = useState(false)
  const [autoSaveCountdown, setAutoSaveCountdown] = useState<number | null>(null)
  const [hasDraftLoaded, setHasDraftLoaded] = useState(false)
  const [isManualSaving, setIsManualSaving] = useState(false)
  const autoSaveTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const countdownIntervalRef = useRef<NodeJS.Timeout | null>(null)

  // Backfill modal state
  const [showBackfillModal, setShowBackfillModal] = useState(false)
  const [backfillDate, setBackfillDate] = useState(() => {
    const today = new Date()
    return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
  })
  const [backfillHour, setBackfillHour] = useState(() => {
    const now = new Date()
    let hour = now.getHours()
    return hour === 0 ? 12 : hour > 12 ? hour - 12 : hour
  })
  const [backfillMinute, setBackfillMinute] = useState(() => {
    return new Date().getMinutes()
  })
  const [backfillAmPm, setBackfillAmPm] = useState<'AM' | 'PM'>(() => {
    return new Date().getHours() >= 12 ? 'PM' : 'AM'
  })
  const [showBackfillCalendar, setShowBackfillCalendar] = useState(false)

  // Temporary state for calendar popup (before Apply)
  const [tempDate, setTempDate] = useState(() => {
    const today = new Date()
    return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
  })
  const [tempHour, setTempHour] = useState(() => {
    const now = new Date()
    let hour = now.getHours()
    return hour === 0 ? 12 : hour > 12 ? hour - 12 : hour
  })
  const [tempMinute, setTempMinute] = useState(() => {
    return new Date().getMinutes()
  })
  const [tempAmPm, setTempAmPm] = useState<'AM' | 'PM'>(() => {
    return new Date().getHours() >= 12 ? 'PM' : 'AM'
  })

  // New state for UI flow
  const [showInputUI, setShowInputUI] = useState(true)
  const [showResults, setShowResults] = useState(false)
  const [currentLoadingMessage, setCurrentLoadingMessage] = useState('')
  const [currentReviewTip, setCurrentReviewTip] = useState('')

  // Edit state
  const [editingCard, setEditingCard] = useState<string | null>(null)
  const [showOverlay, setShowOverlay] = useState(false)
  const [overlayContent, setOverlayContent] = useState('')
  const [overlayMode, setOverlayMode] = useState('')

  const { toast } = useToast()
  const textAreaRef = useRef<HTMLTextAreaElement>(null)
  const isStartingRef = useRef(false) // Prevent multiple simultaneous recording attempts

  // Helper function to ensure toast content is valid
  const safeToast = (params: Parameters<typeof toast>[0]) => {
    if (!params.title?.trim() && !params.description?.toString()?.trim()) {
      return // Don't show empty toasts
    }
    // Add shorter duration for quicker dismissal
    toast({
      ...params,
      duration: 2000 // 2 seconds for quick dismissal
    })
  }

  // Helper functions for time conversion and validation
  const convertTo24Hour = (hour: number, minute: number, amPm: 'AM' | 'PM'): string => {
    let hour24 = hour
    if (amPm === 'AM' && hour === 12) {
      hour24 = 0
    } else if (amPm === 'PM' && hour !== 12) {
      hour24 = hour + 12
    }
    return `${hour24.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`
  }

  const getFormattedTime = (): string => {
    return convertTo24Hour(backfillHour, backfillMinute, backfillAmPm)
  }

  // Check if selected date/time is in the future
  const isSelectedTimeFuture = (): boolean => {
    if (!backfillDate) return false
    const selectedDateTime = new Date(`${backfillDate}T${getFormattedTime()}`)
    return selectedDateTime > new Date()
  }

  // Check if temp date/time is in the future (for popup validation)
  const isTempTimeFuture = (): boolean => {
    if (!tempDate) return false
    const tempTime = convertTo24Hour(tempHour, tempMinute, tempAmPm)
    const selectedDateTime = new Date(`${tempDate}T${tempTime}`)
    return selectedDateTime > new Date()
  }

  // Check if selected date is today
  const isSelectedDateToday = (): boolean => {
    if (!backfillDate) return false
    const selectedDate = new Date(backfillDate)
    const today = new Date()
    return selectedDate.toDateString() === today.toDateString()
  }

  // Funny error messages for future time validation
  const futureTimeMessages = [
    "Whoa there, Doc Brown. No journaling from the future. Pick a time that's already happened.",
    "Unless you've got a working time machine, try selecting a past time, not a prophecy.",
    "Future entries are how sci-fi thrillers start. Let's not.",
    "Boo can't read the future... yet. Pick a time you've actually lived, mystic.",
    "Future time selected. Plot twist: you haven't done that yet. Try again.",
    "Nice try, Nostradamus. But Boo only reflects on what has been, not what will be.",
    "Unless you're journaling from a wormhole, select a time that exists.",
    "Back to the past, buddy. Boo doesn't support premonitions... yet.",
    "Time machines are sold separately. Please enter something from the actual timeline."
  ]

  const reviewTips = [
    "AI did its best, but it's not a mind reader. Yet.",
    "Your voice said 'chicken', but the diary thinks you said 'existential crisis'. Double check!",
    "This entry was transcribed by a sleep-deprived robot. Maybe proofread it?",
    "Review before you regret—unless you *meant* to write 'fluffy despair'.",
    "Typos happen. Even AI ones. Give it a look before saving!",
    "Edit your entry unless you're cool with 'banana thoughts' becoming a theme.",
    "One small review for you, one giant leap for diary accuracy.",
    "AI listens well, but it doesn't always *understand*. Like your ex.",
    "Save responsibly. Your future self will thank you. Or sue you.",
    "Read twice, save once. Trust issues? Valid.",
    "If the AI heard 'my cat is the president,' maybe double check before saving.",
    "Voice-to-text is magical. But even magic needs proofreading.",
    "If this looks like it was written by a haunted typewriter, maybe give it a once-over.",
    "Typos have feelings too, but maybe don't let them live in your journal forever.",
    "It's all fun and games until 'went jogging' becomes 'ate fog king'.",
    "Just because the AI is confident doesn't mean it's *correct*.",
    "Boo heard something. It might not be what you said. Check it.",
    "Avoid future cringe—review your entry like your inner editor is watching.",
    "If something feels... off, it probably is. Read it again, brave soul.",
    "Even Shakespeare proofread (probably). Be like Shakespeare. Sort of.",
    "Boo doesn't judge. But typos do. Silently. Forever.",
    "Double check now or discover embarrassing poetry later. Your call."
  ]

  // Get random funny error message
  const getRandomFutureTimeMessage = (): string => {
    return futureTimeMessages[Math.floor(Math.random() * futureTimeMessages.length)]
  }

  // Get random review tip
  const getRandomReviewTip = (): string => {
    return reviewTips[Math.floor(Math.random() * reviewTips.length)]
  }

  // Reset state when navigating back to /new (sidebar click)
  useEffect(() => {
    if (location.pathname === '/new') {
      // Only reset if we're in results view, not during normal usage
      if (showResults && !isProcessing) {
        startNewEntry()
      }
    }
  }, [location.pathname])

  // WebSocket setup and event handlers
  useEffect(() => {
    // Subscribe to connection changes first (before connecting)
    const unsubscribeConnection = wsClient.onConnectionChange((connected) => {
      console.log('WebSocket connection state changed:', connected)
      setIsConnected(connected)
      if (connected) {
        // Subscribe to STT channels
        wsClient.subscribeToChannels(['stt', 'recording', 'transcription'])
      }
    })

    // Connect to WebSocket with retry logic
    const connectWithRetry = async () => {
      try {
        await wsClient.connect()
        // Check if connected and update state
        if (wsClient.isConnected()) {
          console.log('WebSocket connected successfully')
          setIsConnected(true)
          wsClient.subscribeToChannels(['stt', 'recording', 'transcription'])
        }
      } catch (error) {
        console.error('Initial WebSocket connection failed:', error)
        // Don't show toast on initial connection failure - let user trigger manually
        setIsConnected(false)
      }
    }

    connectWithRetry()

    // Subscribe to state changes
    const unsubscribeState = wsClient.onStateChange((state: STTState) => {
      console.log('STT State:', state)
      // Reset the starting flag when we get any state update from backend
      isStartingRef.current = false

      // Map backend states to frontend states
      if (state.state === 'idle') {
        setRecordingState(RecordingState.IDLE)
      } else if (state.state === 'recording') {
        setRecordingState(RecordingState.RECORDING)
      } else if (state.state === 'processing') {
        setRecordingState(RecordingState.PROCESSING)
      } else if (state.state === 'transcribing') {
        setRecordingState(RecordingState.TRANSCRIBING)
      }
    })

    // Subscribe to transcription results
    const unsubscribeTranscription = wsClient.onTranscription((result: TranscriptionResult) => {
      console.log('Transcription result:', result)
      if (result.text) {
        // Accumulate text with space continuation
        setText(prevText => {
          if (!prevText) return result.text
          // Add space for continuation
          return prevText + ' ' + result.text
        })
        setRecordingState(RecordingState.IDLE)
      }
    })

    // Subscribe to errors
    const unsubscribeError = wsClient.onError((error: string) => {
      console.error('WebSocket error:', error)
      // Only show toast for critical errors, not connection state changes or recording state conflicts
      const shouldSkipError = error.includes('connection') ||
        error.includes('WebSocket') ||
        error.includes('Cannot start recording in state') ||
        error.includes('Failed to start STT recording') ||
        !error.trim()

      if (!shouldSkipError) {
        // Attempt automatic pipeline recovery
        console.log('Attempting automatic recording pipeline recovery...')

        // Reset recording state and clear any stuck states
        setRecordingState(RecordingState.IDLE)
        setRecordingSource(null)
        isStartingRef.current = false

        // Try to reinitialize the WebSocket connection and reset server-side recording
        setTimeout(async () => {
          try {
            if (!wsClient.isConnected()) {
              console.log('Reconnecting WebSocket for pipeline recovery...')
              await wsClient.connect()
              if (wsClient.isConnected()) {
                wsClient.subscribeToChannels(['stt', 'recording', 'transcription'])
                // Reset server-side recording session
                wsClient.resetRecording()
                console.log('Pipeline recovery successful - WebSocket reconnected and server reset')

                // Show recovery success message instead of error
                // Force blur immediately and with longer delay
                if (document.activeElement && document.activeElement !== document.body) {
                  (document.activeElement as HTMLElement).blur()
                }
                setTimeout(() => {
                  // Blur again before showing toast
                  if (document.activeElement && document.activeElement !== document.body) {
                    (document.activeElement as HTMLElement).blur()
                  }
                  safeToast({
                    title: "🔄 Recording recovered",
                    description: "Pipeline automatically restored. You can record again.",
                  })
                }, 50)
                return
              }
            } else {
              // WebSocket is connected, reset server-side recording and channels
              wsClient.resetRecording()
              wsClient.subscribeToChannels(['stt', 'recording', 'transcription'])

              // Force blur immediately and with longer delay
              if (document.activeElement && document.activeElement !== document.body) {
                (document.activeElement as HTMLElement).blur()
              }
              setTimeout(() => {
                // Blur again before showing toast
                if (document.activeElement && document.activeElement !== document.body) {
                  (document.activeElement as HTMLElement).blur()
                }
                safeToast({
                  title: "🔄 Recording recovered",
                  description: "Pipeline automatically restored. You can record again.",
                })
              }, 50)
              return
            }
          } catch (recoveryError) {
            console.error('Pipeline recovery failed:', recoveryError)
          }

          // If recovery failed, show the original error
          if (document.activeElement && document.activeElement !== document.body) {
            (document.activeElement as HTMLElement).blur()
          }
          safeToast({
            title: "❌ Recording failed",
            description: error.trim() || "An unknown error occurred",
          })
        }, 100)
      } else {
        setRecordingState(RecordingState.IDLE)
      }
    })

    // Load current preferences (hotkey and auto-save)
    const initialize = async () => {
      await loadPreferences()
      // Load draft after preferences are loaded
      setTimeout(() => loadLatestDraft(), 100)
    }
    initialize()

    // Cleanup on unmount
    return () => {
      unsubscribeConnection()
      unsubscribeState()
      unsubscribeTranscription()
      unsubscribeError()
      // Cleanup auto-save timeout
      if (autoSaveTimeoutRef.current) {
        clearTimeout(autoSaveTimeoutRef.current)
      }
    }
  }, [toast])

  // Close backfill calendar when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Element
      if (showBackfillCalendar && !target.closest('.backfill-calendar-container')) {
        setShowBackfillCalendar(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [showBackfillCalendar])

  // Reset date/time picker to current values on component mount
  useEffect(() => {
    const now = new Date()
    const todayDate = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
    const currentHour = now.getHours()
    const currentMinute = now.getMinutes()

    setBackfillDate(todayDate)
    setTempDate(todayDate)
    setBackfillHour(currentHour > 12 ? currentHour - 12 : currentHour === 0 ? 12 : currentHour)
    setBackfillMinute(currentMinute)
    setBackfillAmPm(currentHour >= 12 ? 'PM' : 'AM')
    setTempHour(currentHour > 12 ? currentHour - 12 : currentHour === 0 ? 12 : currentHour)
    setTempMinute(currentMinute)
    setTempAmPm(currentHour >= 12 ? 'PM' : 'AM')
  }, []) // Empty dependency array = run once on mount

  // Listen for F8 hotkey press events (HOLD to record)
  useEffect(() => {
    const handleKeyDown = async (e: KeyboardEvent) => {
      // Check if it's the recording hotkey (F8)
      if (e.key === currentHotkey || e.key.toUpperCase() === currentHotkey.toUpperCase()) {
        if (!e.repeat && recordingState === RecordingState.IDLE) {
          e.preventDefault()
          setRecordingSource('hotkey')
          await startRecording()
        } else if (e.repeat) {
          // Prevent repeated F8 presses while already recording
          e.preventDefault()
        }
      }
    }

    const handleKeyUp = (e: KeyboardEvent) => {
      // Check if it's the recording hotkey (F8)
      if (e.key === currentHotkey || e.key.toUpperCase() === currentHotkey.toUpperCase()) {
        if (recordingState === RecordingState.RECORDING) {
          e.preventDefault()
          stopRecording()
          setRecordingSource(null)
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('keyup', handleKeyUp)

    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('keyup', handleKeyUp)
    }
  }, [currentHotkey, recordingState])

  const loadPreferences = async () => {
    try {
      const response = await api.getPreferences()
      if (response.success && response.data && response.data.preferences) {
        // Load hotkey preference
        const hotkey = response.data.preferences.find((pref: any) => pref.key === 'hotkey')
        if (hotkey && hotkey.typed_value) {
          setCurrentHotkey(hotkey.typed_value)
        }

        // Load auto-save preferences
        const autoSavePref = response.data.preferences.find((pref: any) => pref.key === 'auto_save')
        if (autoSavePref && autoSavePref.typed_value !== undefined) {
          setAutoSaveEnabled(autoSavePref.typed_value)
        }

        const autoSaveIntervalPref = response.data.preferences.find((pref: any) => pref.key === 'auto_save_interval')
        if (autoSaveIntervalPref && autoSaveIntervalPref.typed_value) {
          setAutoSaveInterval(autoSaveIntervalPref.typed_value)
        }
      }
    } catch (error) {
      console.error('Failed to load preferences:', error)
    }
  }

  // Auto-save functionality
  const loadLatestDraft = async () => {
    if (hasDraftLoaded) return // Only load once per session

    try {
      // Try to load from backend first
      try {
        const response = await api.request('/drafts/latest')
        console.log('Backend draft response:', response)

        if (response.success && (response.data as any)?.content) {
          const draftSource = (response.data as any).metadata?.source || 'unknown'
          const draftTime = (response.data as any).updated_at || (response.data as any).created_at

          setText((response.data as any).content)
          setLastAutoSave(new Date(draftTime))
          setHasDraftLoaded(true)

          console.log(`Loaded ${draftSource} draft from backend:`, {
            content_length: (response.data as any).content.length,
            created_at: (response.data as any).created_at,
            updated_at: (response.data as any).updated_at,
            source: draftSource
          })

          toast({
            title: 'Draft loaded',
            description: `Your previous ${draftSource} draft has been restored`
          })
          return
        } else {
          console.log('No valid draft found in backend response')
        }
      } catch (backendError) {
        console.log('Backend draft not available, checking localStorage:', backendError)
      }

      // Fallback to localStorage
      const draftData = localStorage.getItem('boo_draft_new_entry')
      if (draftData) {
        const draft = JSON.parse(draftData)
        if (draft.content && draft.content.trim()) {
          const draftSource = draft.source || 'unknown'
          setText(draft.content)
          setLastAutoSave(new Date(draft.timestamp))
          setHasDraftLoaded(true)

          console.log(`Loaded ${draftSource} draft from localStorage:`, {
            content_length: draft.content.length,
            timestamp: draft.timestamp,
            source: draftSource
          })

          toast({
            title: 'Draft loaded',
            description: `Your previous ${draftSource} draft has been restored`
          })
        }
      }
    } catch (error) {
      console.error('Failed to load draft:', error)
      // Silently fail - don't disrupt user experience
    }
  }

  const performAutoSave = async (content: string) => {
    if (!content.trim() || isAutoSaving || isManualSaving) return

    setIsAutoSaving(true)
    try {
      // Try to save to backend first, fallback to localStorage
      try {
        const response = await api.request('/drafts/save', {
          method: 'POST',
          body: JSON.stringify({
            content: content.trim(),
            timestamp: new Date().toISOString(),
            metadata: { source: 'auto' } // Mark as auto save
          })
        })

        if (response.success) {
          setLastAutoSave(new Date())
          console.log('Auto-saved to backend successfully:', response.data)
          return
        }
      } catch (backendError) {
        console.log('Backend auto-save not available, using localStorage')
      }

      // Fallback to localStorage
      const draftData = {
        content: content.trim(),
        timestamp: new Date().toISOString(),
        source: 'auto'
      }
      localStorage.setItem('boo_draft_new_entry', JSON.stringify(draftData))
      setLastAutoSave(new Date())
      console.log('Auto-saved to localStorage successfully')

    } catch (error) {
      console.error('Auto-save failed completely:', error)
      // Silently fail - don't disrupt user experience
    } finally {
      setIsAutoSaving(false)
    }
  }

  const clearAllDrafts = async () => {
    // Clear the text
    setText('')
    setAutoSaveCountdown(null)
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current)
    }
    if (autoSaveTimeoutRef.current) {
      clearTimeout(autoSaveTimeoutRef.current)
    }

    // Mark that user has intentionally cleared - prevent auto-loading
    setHasDraftLoaded(true)

    // Clear drafts from backend and localStorage
    try {
      // Try to clear from backend
      try {
        const response = await api.request('/drafts/latest')
        if (response.success && (response.data as any)?.id) {
          await api.request(`/drafts/${(response.data as any).id}`, {
            method: 'DELETE'
          })
          console.log('Cleared draft from backend successfully')
        }
      } catch (backendError) {
        console.log('Backend draft clear not available')
      }

      // Clear from localStorage
      localStorage.removeItem('boo_draft_new_entry')
      console.log('Cleared draft from localStorage')

      // Reset auto-save state
      setLastAutoSave(null)
      setIsAutoSaving(false)

      toast({
        title: 'All cleared',
        description: 'Content and drafts have been cleared'
      })

    } catch (error) {
      console.error('Failed to clear drafts:', error)
      // Still show success since text was cleared
      toast({
        title: 'Content cleared',
        description: 'Text cleared, but draft cleanup may be incomplete'
      })
    }
  }

  const clearDraftsWithoutToast = async () => {
    // Clear drafts from backend and localStorage without showing toast notifications
    setAutoSaveCountdown(null)
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current)
    }
    if (autoSaveTimeoutRef.current) {
      clearTimeout(autoSaveTimeoutRef.current)
    }

    // Mark that drafts have been handled
    setHasDraftLoaded(true)

    try {
      // Try to clear from backend
      try {
        const response = await api.request('/drafts/latest')
        if (response.success && (response.data as any)?.id) {
          await api.request(`/drafts/${(response.data as any).id}`, {
            method: 'DELETE'
          })
          console.log('Cleared draft from backend successfully')
        }
      } catch (backendError) {
        console.log('Backend draft clear not available')
      }

      // Clear from localStorage
      localStorage.removeItem('boo_draft_new_entry')
      console.log('Cleared draft from localStorage')

      // Reset auto-save state
      setLastAutoSave(null)
      setIsAutoSaving(false)

    } catch (error) {
      console.error('Failed to clear drafts:', error)
      // Silently fail - don't disrupt user experience
    }
  }

  const performManualSave = async () => {
    if (!text.trim() || isManualSaving) return

    setIsManualSaving(true)

    // Cancel any pending auto-save to avoid conflicts
    if (autoSaveTimeoutRef.current) {
      clearTimeout(autoSaveTimeoutRef.current)
    }
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current)
    }
    setAutoSaveCountdown(null)

    try {
      // Try to save to backend first, fallback to localStorage
      try {
        const response = await api.request('/drafts/save', {
          method: 'POST',
          body: JSON.stringify({
            content: text.trim(),
            timestamp: new Date().toISOString(),
            metadata: { source: 'manual' } // Mark as manual save
          })
        })

        if (response.success) {
          setLastAutoSave(new Date())
          console.log('Manual save to backend successfully:', response.data)
          toast({
            title: 'Draft saved',
            description: 'Your draft has been saved successfully'
          })
          return
        }
      } catch (backendError) {
        console.log('Backend manual save not available, using localStorage')
      }

      // Fallback to localStorage
      const draftData = {
        content: text.trim(),
        timestamp: new Date().toISOString(),
        source: 'manual'
      }
      localStorage.setItem('boo_draft_new_entry', JSON.stringify(draftData))
      setLastAutoSave(new Date())
      console.log('Manual save to localStorage successfully')
      toast({
        title: 'Draft saved',
        description: 'Your draft has been saved to local storage'
      })

    } catch (error) {
      console.error('Manual save failed completely:', error)
      toast({
        title: 'Save failed',
        description: 'Failed to save draft',
        variant: 'destructive'
      })
    } finally {
      setIsManualSaving(false)
    }
  }

  // Auto-save effect - triggers when text changes
  useEffect(() => {
    if (!autoSaveEnabled || !text.trim() || isProcessing) {
      // Clear countdown when not auto-saving
      setAutoSaveCountdown(null)
      if (countdownIntervalRef.current) {
        clearInterval(countdownIntervalRef.current)
      }
      return
    }

    // Clear existing timeout and countdown
    if (autoSaveTimeoutRef.current) {
      clearTimeout(autoSaveTimeoutRef.current)
    }
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current)
    }

    // Start countdown
    setAutoSaveCountdown(autoSaveInterval)

    // Update countdown every second
    countdownIntervalRef.current = setInterval(() => {
      setAutoSaveCountdown(prev => {
        if (prev === null || prev <= 1) {
          return null
        }
        return prev - 1
      })
    }, 1000)

    // Set timeout for auto-save
    autoSaveTimeoutRef.current = setTimeout(() => {
      performAutoSave(text)
      setAutoSaveCountdown(null)
      if (countdownIntervalRef.current) {
        clearInterval(countdownIntervalRef.current)
      }
    }, autoSaveInterval * 1000) // Convert seconds to milliseconds

    // Cleanup function
    return () => {
      if (autoSaveTimeoutRef.current) {
        clearTimeout(autoSaveTimeoutRef.current)
      }
      if (countdownIntervalRef.current) {
        clearInterval(countdownIntervalRef.current)
      }
    }
  }, [text, autoSaveEnabled, autoSaveInterval, isProcessing])

  const startRecording = async () => {
    // Only proceed if we're truly idle and not already starting
    if (isStartingRef.current || recordingState !== RecordingState.IDLE) {
      console.log('Start recording blocked - already in progress or not idle:', {
        isStarting: isStartingRef.current,
        currentState: recordingState
      })
      return
    }

    // Check actual WebSocket connection state
    if (!wsClient.isConnected()) {
      console.log('WebSocket not connected, attempting recovery...')
      try {
        await wsClient.connect()
        if (wsClient.isConnected()) {
          wsClient.subscribeToChannels(['stt', 'recording', 'transcription'])
          console.log('WebSocket reconnected successfully')
        } else {
          throw new Error('Failed to reconnect')
        }
      } catch (error) {
        safeToast({
          title: "Connection Error",
          description: "Please ensure connection is established",
          variant: "destructive"
        })
        return
      }
    }

    isStartingRef.current = true
    console.log('Starting recording...')

    // Add timeout to prevent stuck states
    const startTimeout = setTimeout(() => {
      if (isStartingRef.current && recordingState === RecordingState.IDLE) {
        console.log('Recording start timeout - resetting state')
        isStartingRef.current = false
        setRecordingState(RecordingState.IDLE)
      }
    }, 5000) // 5 second timeout

    // Clear timeout when state changes (handled in state change handler)
    const originalRef = isStartingRef.current

    wsClient.startRecording()

    // Auto-clear timeout if state changes quickly
    setTimeout(() => {
      if (originalRef === isStartingRef.current && recordingState !== RecordingState.IDLE) {
        clearTimeout(startTimeout)
      }
    }, 1000)
  }

  const stopRecording = () => {
    if (recordingState === RecordingState.RECORDING) {
      setRecordingState(RecordingState.PROCESSING)
      wsClient.stopRecording()
    }
  }

  const toggleRecording = async () => {
    if (recordingState === RecordingState.IDLE) {
      setRecordingSource('button')
      await startRecording()
    } else if (recordingState === RecordingState.RECORDING) {
      stopRecording()
      setRecordingSource(null)
    }
  }

  // Loading message cycling effect
  useEffect(() => {
    let interval: NodeJS.Timeout

    if (isProcessing && !showResults) {
      // Cycle through loading messages
      let messageIndex = 0
      setCurrentLoadingMessage(loadingMessages[0])

      interval = setInterval(() => {
        messageIndex = (messageIndex + 1) % loadingMessages.length
        setCurrentLoadingMessage(loadingMessages[messageIndex])
      }, 2000) // Change message every 2 seconds
    }

    return () => {
      if (interval) clearInterval(interval)
    }
  }, [isProcessing, showResults])

  const createEntries = async () => {
    if (!text.trim()) {
      safeToast({
        title: "No content",
        description: "Please record or type something first",
        variant: "destructive"
      })
      return
    }

    // Hide input UI with animation
    setShowInputUI(false)
    setIsProcessing(true)
    setRecordingState(RecordingState.ENHANCING)
    setCreatedEntries(null)
    setProcessingMetadata(null)

    try {
      // Process text only (no database operations)
      const response = await api.processTextOnly(
        text.trim(),
        ['raw', 'enhanced', 'structured']
      )

      if (response.success && response.data) {
        const { results, raw_text } = response.data

        // Extract processing metadata with priority: structured > enhanced > raw
        let metadata = null
        if (results.structured?.processing_metadata) {
          metadata = results.structured.processing_metadata
        } else if (results.enhanced?.processing_metadata) {
          metadata = results.enhanced.processing_metadata
        } else if (results.raw?.processing_metadata) {
          metadata = results.raw.processing_metadata
        }

        setProcessingMetadata(metadata)

        // Store processed results in state for display
        console.log('Processing results:', results)  // Debug log
        setCreatedEntries({
          raw: {
            id: 0, // Temporary ID since not in database yet
            raw_text: raw_text,
            timestamp: new Date().toISOString()
          },
          enhanced: results.enhanced ? {
            id: 0,
            enhanced_text: results.enhanced.processed_text
          } : undefined,
          structured: results.structured ? {
            id: 0,
            structured_summary: results.structured.processed_text
          } : undefined
        })

        // Show results immediately
        setRecordingState(RecordingState.SUCCESS)
        setCurrentReviewTip(getRandomReviewTip())  // Set tip once before showing results
        setShowResults(true)
        setTimeout(() => setRecordingState(RecordingState.IDLE), 2000)

        // Clear processing state
        setText('')
        setIsProcessing(false)
        setProcessingJobId(null)

      } else {
        throw new Error(response.error || 'Failed to process entries')
      }
    } catch (error) {
      setRecordingState(RecordingState.IDLE)
      safeToast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to process entries",
        variant: "destructive"
      })
      setIsProcessing(false)
    }
  }

  const pollEmbeddingStatus = async (entryId: number) => {
    const maxAttempts = 20 // 20 seconds max
    const pollInterval = 1000 // Check every second
    let attempts = 0

    const poll = async () => {
      if (attempts >= maxAttempts) {
        // Timeout - embeddings are taking too long
        safeToast({
          title: "⏱️ Embeddings processing",
          description: "Embedding generation is taking longer than expected, but will complete in the background",
        })
        return
      }

      attempts++

      try {
        const response = await api.getEntry(entryId)
        if (response.success && response.data) {
          const entry = response.data

          // Check if embeddings are now available
          if (entry.embeddings && entry.embeddings.length > 0) {
            // Embeddings are ready!
            safeToast({
              title: "✨ Embeddings ready!",
              description: "Your entry has been indexed for semantic search and pattern analysis",
            })
            return
          }
        }

        // Still no embeddings, continue polling
        setTimeout(poll, pollInterval)
      } catch (error) {
        // Silent fail - don't spam user with embedding polling errors
        console.error('Failed to check embedding status:', error)
        return
      }
    }

    // Start polling after a short delay to let the backend start processing
    setTimeout(poll, 2000)
  }

  const pollJobStatus = async (jobId: string) => {
    const maxAttempts = 30
    const pollInterval = 1000
    let attempts = 0

    const poll = async () => {
      if (attempts >= maxAttempts) {
        setRecordingState(RecordingState.IDLE)
        setIsProcessing(false)
        safeToast({
          title: "Processing timeout",
          description: "Entry processing is taking longer than expected",
          variant: "destructive"
        })
        return
      }

      attempts++

      try {
        const response = await api.getJobStatus(jobId)
        if (response.success && response.data) {
          const { status, result, error } = response.data

          if (status === 'completed' && result) {
            // Update with processed entries
            setCreatedEntries(prev => ({
              ...prev!,
              enhanced: result.enhanced ? {
                id: result.entry_id,
                enhanced_text: result.enhanced
              } : undefined,
              structured: result.structured ? {
                id: result.entry_id,
                structured_summary: result.structured
              } : undefined
            }))

            // Show success state and results
            setRecordingState(RecordingState.SUCCESS)
            setCurrentReviewTip(getRandomReviewTip())  // Set tip once before showing results
            setShowResults(true)
            setTimeout(() => setRecordingState(RecordingState.IDLE), 2000)

            // Success toast with checkmarks
            safeToast({
              title: "✓ Entries created!",
              description: (
                <div className="space-y-1 mt-2">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="h-3 w-3 text-green-500" />
                    <span className="text-sm">Raw transcription saved</span>
                  </div>
                  {result.enhanced && (
                    <div className="flex items-center gap-2">
                      <CheckCircle className="h-3 w-3 text-green-500" />
                      <span className="text-sm">Enhanced style created</span>
                    </div>
                  )}
                  {result.structured && (
                    <div className="flex items-center gap-2">
                      <CheckCircle className="h-3 w-3 text-green-500" />
                      <span className="text-sm">Structured summary generated</span>
                    </div>
                  )}
                  <div className="flex items-center gap-2">
                    <Loader2 className="h-3 w-3 animate-spin text-blue-400" />
                    <span className="text-sm text-blue-400">Generating embeddings...</span>
                  </div>
                </div>
              ),
            })

            // Start polling for embedding completion
            if (result.entry_id) {
              pollEmbeddingStatus(result.entry_id)
            }

            // Clear for next entry
            setText('')
            setIsProcessing(false)
            setProcessingJobId(null)

          } else if (status === 'failed') {
            throw new Error(error || 'Processing failed')
          } else {
            // Still processing, continue polling
            setTimeout(poll, pollInterval)
          }
        }
      } catch (error) {
        setRecordingState(RecordingState.IDLE)
        setIsProcessing(false)
        safeToast({
          title: "Error",
          description: "Failed to check processing status",
          variant: "destructive"
        })
      }
    }

    poll()
  }

  const startNewEntry = () => {
    // Reset all state
    setText('')
    setCreatedEntries(null)
    setProcessingMetadata(null)
    setIsProcessing(false)
    setProcessingJobId(null)
    setRecordingState(RecordingState.IDLE)
    setShowInputUI(true)
    setShowResults(false)
    setCurrentLoadingMessage('')
    setEditingCard(null)
    setShowOverlay(false)
    // Reset auto-save state
    setLastAutoSave(null)
    setIsAutoSaving(false)
    setAutoSaveCountdown(null)
    setHasDraftLoaded(false) // Allow draft loading again
    setIsManualSaving(false)

    // Reset backfill date/time to current values
    const now = new Date()
    const todayDate = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
    const currentHour = now.getHours()
    const currentMinute = now.getMinutes()

    setBackfillDate(todayDate)
    setTempDate(todayDate)
    setBackfillHour(currentHour > 12 ? currentHour - 12 : currentHour === 0 ? 12 : currentHour)
    setBackfillMinute(currentMinute)
    setBackfillAmPm(currentHour >= 12 ? 'PM' : 'AM')
    setTempHour(currentHour > 12 ? currentHour - 12 : currentHour === 0 ? 12 : currentHour)
    setTempMinute(currentMinute)
    setTempAmPm(currentHour >= 12 ? 'PM' : 'AM')

    if (autoSaveTimeoutRef.current) {
      clearTimeout(autoSaveTimeoutRef.current)
    }
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current)
    }
  }

  const backToEdit = () => {
    // Return to edit mode but keep the original raw text
    const originalText = createdEntries?.raw?.raw_text || ''
    setText(originalText)
    setCreatedEntries(null)
    setProcessingMetadata(null)
    setIsProcessing(false)
    setProcessingJobId(null)
    setRecordingState(RecordingState.IDLE)
    setShowInputUI(true)
    setShowResults(false)
    setCurrentLoadingMessage('')
    setEditingCard(null)
    setShowOverlay(false)
  }

  const handleCardEdit = (mode: string) => {
    let content = ''
    if (mode === 'raw' && createdEntries?.raw) {
      content = createdEntries.raw.raw_text
    } else if (mode === 'enhanced' && createdEntries?.enhanced) {
      content = createdEntries.enhanced.enhanced_text
    } else if (mode === 'structured' && createdEntries?.structured) {
      content = createdEntries.structured.structured_summary
    }

    setOverlayContent(content)
    setOverlayMode(mode)
    setShowOverlay(true)
  }

  const handleSaveEdit = () => {
    if (!createdEntries) return

    const updatedEntries = { ...createdEntries }

    if (overlayMode === 'raw' && updatedEntries.raw) {
      updatedEntries.raw.raw_text = overlayContent
    } else if (overlayMode === 'enhanced' && updatedEntries.enhanced) {
      updatedEntries.enhanced.enhanced_text = overlayContent
    } else if (overlayMode === 'structured' && updatedEntries.structured) {
      updatedEntries.structured.structured_summary = overlayContent
    }

    setCreatedEntries(updatedEntries)
    setShowOverlay(false)
    setOverlayContent('')
    setOverlayMode('')
  }

  const handleAddToDiary = async () => {
    if (!createdEntries) return

    try {
      // Save entry to database with all three texts and processing metadata
      // Use selected date/time if available, otherwise backend will use current time
      const selectedDateTime = backfillDate && backfillHour && backfillMinute && backfillAmPm
        ? `${backfillDate}T${getFormattedTime()}`
        : undefined

      const response = await api.createEntryWithAllTexts(
        createdEntries.raw.raw_text,
        createdEntries.enhanced?.enhanced_text,
        createdEntries.structured?.structured_summary,
        'raw',
        processingMetadata,
        selectedDateTime
      )

      if (response.success && response.data) {
        const createdEntry = response.data

        // Clear drafts silently (without toast notification)
        await clearDraftsWithoutToast()

        safeToast({
          title: "✓ Added to diary!",
          description: "Entry saved successfully. Generating embeddings...",
        })

        // Start polling for embedding completion
        if (createdEntry.id) {
          pollEmbeddingStatus(createdEntry.id)
        }

        // Trigger mood analysis in background if enhanced text is available
        if (createdEntry.id && createdEntries.enhanced?.enhanced_text) {
          try {
            await api.analyzeEntryMood(createdEntry.id)
            // Show mood analysis toast
            setTimeout(() => {
              safeToast({
                title: "✓ Moods added!",
                description: "Emotional analysis completed for your entry",
              })
            }, 1500) // Show after 1.5 seconds to not conflict with main toast
          } catch (error) {
            console.error('Mood analysis failed:', error)
            // Don't show error toast - mood analysis is supplementary
          }
        }

        // Redirect to view entries page to see the saved entry
        setTimeout(() => {
          navigate('/entries')
        }, 1000)

      } else {
        throw new Error(response.error || 'Failed to save entry')
      }

    } catch (error) {
      safeToast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to add entries to diary",
        variant: "destructive"
      })
    }
  }

  const truncateText = (text: string, maxLength: number) => {
    if (text.length <= maxLength) return text
    return text.substring(0, maxLength).trim() + '...'
  }

  const getStateMessage = () => {
    switch (recordingState) {
      case RecordingState.RECORDING:
        if (recordingSource === 'hotkey') {
          return `Recording... Release ${currentHotkey} to stop`
        } else {
          return "Recording... Click button to stop"
        }
      case RecordingState.PROCESSING:
        return "Processing audio..."
      case RecordingState.TRANSCRIBING:
        return "Converting speech to text..."
      case RecordingState.ENHANCING:
        return "Creating enhanced versions..."
      case RecordingState.SUCCESS:
        return "Entries created!"
      default:
        return `Hold ${currentHotkey} to record`
    }
  }

  const getStateIcon = () => {
    switch (recordingState) {
      case RecordingState.RECORDING:
        return <div className="h-2 w-2 bg-red-500 rounded-full animate-pulse" />
      case RecordingState.PROCESSING:
      case RecordingState.TRANSCRIBING:
      case RecordingState.ENHANCING:
        return <Loader2 className="h-4 w-4 animate-spin" />
      case RecordingState.SUCCESS:
        return <CheckCircle className="h-4 w-4 text-green-500" />
      default:
        return null
    }
  }

  return (
    <div className="h-screen flex flex-col p-4 md:p-6 overflow-hidden relative">
      <div className="max-w-6xl mx-auto w-full flex flex-col flex-1">
        {/* Header - Always shown */}
        <div className="flex items-center justify-between mb-4 min-h-[40px]">
          <h2 className="text-2xl font-bold text-white">New Entry</h2>
          <div className="flex items-center gap-2 flex-shrink-0">
            <AnimatePresence>
              {recordingState !== RecordingState.IDLE && showInputUI && (
                <motion.div
                  key={recordingState}
                  initial={{ width: 0, paddingLeft: 0, paddingRight: 0 }}
                  animate={{ width: "auto", paddingLeft: 16, paddingRight: 16 }}
                  exit={{ width: 0, paddingLeft: 0, paddingRight: 0 }}
                  transition={{
                    duration: 0.15,
                    ease: "easeOut"
                  }}
                  className="relative overflow-hidden py-2 rounded-md font-medium shadow-md transition-all duration-300 flex items-center justify-center bg-primary/10 border border-primary/20 text-primary max-w-xs shrink-0"
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-secondary/10 opacity-70 transition-opacity duration-300" />
                  <div className="relative z-10 flex items-center gap-2 whitespace-nowrap">
                    {getStateIcon()}
                    <span className="text-sm font-medium">{getStateMessage()}</span>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Input UI - Hide with animation when processing */}
        <AnimatePresence>
          {showInputUI && (
            <motion.div
              initial={{ opacity: 1, scale: 1 }}
              exit={{
                opacity: 0,
                scale: 0.95,
                y: -20,
                transition: { duration: 0.4, ease: "easeInOut" }
              }}
              className="flex-1 flex flex-col overflow-hidden"
            >
              <Card className="p-6 flex-1 flex flex-col overflow-hidden">
                <div className="relative flex-1 flex flex-col overflow-hidden">
                  <Textarea
                    ref={textAreaRef}
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder={`Start typing or hold ${currentHotkey} to speak...`}
                    className="flex-1 resize-none pr-16 text-sm leading-relaxed text-white placeholder:text-gray-400 bg-transparent border-border focus:border-primary/50 transition-colors max-w-none w-full focus-visible:ring-1 focus-visible:ring-offset-0"
                    disabled={recordingState !== RecordingState.IDLE || isProcessing}
                  />

                  {/* Voice Recording Button & Hotkey Indicator */}
                  <div className="absolute bottom-4 right-4 flex flex-col items-center gap-2 pointer-events-auto">
                    <button
                      className={`relative overflow-hidden group p-3 rounded-full font-medium shadow-md hover:shadow-lg hover:scale-[1.02] transition-all duration-300 cursor-pointer inline-flex items-center justify-center focus:outline-none ${recordingState === RecordingState.RECORDING
                        ? 'bg-red-500/20 border border-red-500/30 text-red-500 animate-pulse'
                        : 'bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20'
                        }`}
                      onClick={toggleRecording}
                      disabled={!isConnected || (recordingState !== RecordingState.IDLE && recordingState !== RecordingState.RECORDING)}
                    >
                      <div className={`absolute inset-0 bg-gradient-to-r ${recordingState === RecordingState.RECORDING
                        ? 'from-red-500/10 to-red-400/10'
                        : 'from-primary/10 to-secondary/10'
                        } opacity-0 group-hover:opacity-100 transition-opacity duration-300`} />

                      <span className="relative z-10">
                        {recordingState === RecordingState.RECORDING ? (
                          <div className="flex items-center justify-center w-5 h-5">
                            <div className="w-3 h-3 bg-red-500 rounded-sm"></div>
                          </div>
                        ) : (
                          <Mic className="h-5 w-5" />
                        )}
                      </span>
                    </button>
                    <div className="flex flex-col items-center gap-1 text-xs text-muted-foreground">
                      <span>{recordingState === RecordingState.RECORDING ? 'Click to stop' : 'Click to start'}</span>
                      <div className="flex items-center gap-1">
                        <Keyboard className="h-3 w-3" />
                        <span>Hold {currentHotkey}</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Word count and auto-save status */}
                <div className="mt-2 flex items-center justify-between text-sm text-muted-foreground">
                  <span>{text.trim().split(/\s+/).filter(Boolean).length} words</span>

                  {/* Auto-save status */}
                  {autoSaveEnabled && (
                    <div className="flex items-center gap-2">
                      {isAutoSaving ? (
                        <div className="flex items-center gap-1 text-blue-400">
                          <Loader2 className="h-3 w-3 animate-spin" />
                          <span className="text-xs">Saving...</span>
                        </div>
                      ) : autoSaveCountdown !== null && text.trim() ? (
                        <div className="flex items-center gap-1 text-yellow-400">
                          <div className="h-3 w-3 rounded-full bg-yellow-400 animate-pulse" />
                          <span className="text-xs">
                            Auto-save in {autoSaveCountdown}s
                          </span>
                        </div>
                      ) : lastAutoSave && text.trim() ? (
                        <div className="flex items-center gap-1 text-green-400">
                          <CheckCircle className="h-3 w-3" />
                          <span className="text-xs">
                            Saved {new Date(lastAutoSave).toLocaleTimeString([], {
                              hour: '2-digit',
                              minute: '2-digit'
                            })}
                          </span>
                        </div>
                      ) : null}
                    </div>
                  )}
                </div>

                {/* Action Buttons */}
                <div className="mt-4 flex justify-between items-center">
                  <div className="flex gap-3">
                    <button
                      onClick={clearAllDrafts}
                      disabled={isProcessing || recordingState !== RecordingState.IDLE}
                      className="relative overflow-hidden group px-5 py-2.5 rounded-lg font-semibold shadow-lg hover:shadow-xl hover:scale-[1.02] transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-gray-600/20 border-2 border-gray-500/30 text-gray-200 hover:bg-gray-500/30 hover:text-white hover:border-gray-400/50 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <div className="absolute inset-0 bg-gradient-to-r from-gray-500/20 to-gray-400/20 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                      <span className="relative z-10 font-semibold transition-colors duration-300">
                        Clear All
                      </span>
                    </button>

                    <button
                      onClick={performManualSave}
                      disabled={isManualSaving || !text.trim() || recordingState !== RecordingState.IDLE}
                      className="relative overflow-hidden group px-5 py-2.5 rounded-lg font-semibold shadow-lg hover:shadow-xl hover:scale-[1.02] transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-green-600/20 border-2 border-green-500/30 text-green-200 hover:bg-green-500/30 hover:text-green-100 hover:border-green-400/50 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <div className="absolute inset-0 bg-gradient-to-r from-green-500/20 to-emerald-500/20 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                      <span className="relative z-10 font-semibold transition-colors duration-300 flex items-center">
                        {isManualSaving ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Saving...
                          </>
                        ) : (
                          'Save Draft'
                        )}
                      </span>
                    </button>
                  </div>

                  <button
                    onClick={createEntries}
                    disabled={isProcessing || !text.trim() || recordingState !== RecordingState.IDLE}
                    className="relative overflow-hidden group px-8 py-3 rounded-md font-medium shadow-md hover:shadow-lg hover:scale-[1.02] transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20"
                  >
                    <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-secondary/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                    <span className="relative z-10 text-primary font-medium group-hover:text-primary transition-colors duration-300 flex items-center">
                      {isProcessing ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <Sparkles className="mr-2 h-4 w-4" />
                      )}
                      Process Entries
                    </span>
                  </button>
                </div>
              </Card>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Loading State and Results - Wrapped in single AnimatePresence with wait mode */}
        <AnimatePresence mode="wait">
          {isProcessing && !showResults ? (
            <motion.div
              key="loading"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              transition={{ duration: 0.4, ease: "easeInOut" }}
              className="flex-1 flex items-center justify-center px-4"
            >
              <div className="text-center space-y-6 max-w-md mx-auto">
                <motion.div
                  animate={{
                    rotate: 360,
                    scale: [1, 1.1, 1]
                  }}
                  transition={{
                    rotate: { duration: 2, repeat: Infinity, ease: "linear" },
                    scale: { duration: 2, repeat: Infinity, ease: "easeInOut" }
                  }}
                >
                  <Sparkles className="w-16 h-16 text-primary mx-auto" />
                </motion.div>

                <motion.p
                  key={currentLoadingMessage}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.5 }}
                  className="text-xl text-white font-medium"
                >
                  {currentLoadingMessage}
                </motion.p>
              </div>
            </motion.div>
          ) : showResults && createdEntries &&
            createdEntries.raw?.raw_text &&
            createdEntries.enhanced?.enhanced_text &&
            createdEntries.structured?.structured_summary ? (
            <motion.div
              key="results"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, ease: "easeOut" }}
              className="flex-1 flex flex-col overflow-visible"
            >
              {/* AI Processing Tip */}
              <div className="mb-6 relative overflow-hidden rounded-lg">
                <motion.div
                  initial={{ x: "-100%" }}
                  animate={{ x: 0 }}
                  transition={{ duration: 0.5, ease: "easeOut" }}
                  className="p-4 bg-yellow-400/5 border border-yellow-400/30 rounded-lg"
                >
                  <div className="flex items-start gap-3">
                    <Lightbulb className="h-5 w-5 text-yellow-400 flex-shrink-0 mt-0.5 drop-shadow-[0_0_8px_rgba(250,204,21,0.6)] animate-pulse" />
                    <div>
                      <p className="text-sm text-yellow-200 font-medium mb-1">
                        Review Before Saving
                      </p>
                      <p className="text-xs text-gray-300">
                        {currentReviewTip}
                      </p>
                    </div>
                  </div>
                </motion.div>
              </div>

              <div className="grid md:grid-cols-3 gap-6 flex-1 mb-6">
                {viewModes.map((mode, index) => {
                  let content = ''
                  let hasContent = false

                  if (mode.mode === 'raw' && createdEntries.raw) {
                    content = createdEntries.raw.raw_text
                    hasContent = true
                  } else if (mode.mode === 'enhanced' && createdEntries.enhanced) {
                    content = createdEntries.enhanced.enhanced_text
                    hasContent = true
                  } else if (mode.mode === 'structured' && createdEntries.structured) {
                    content = createdEntries.structured.structured_summary
                    hasContent = true
                  }

                  // Truncate text to fit without scroll - estimate ~500 chars for good fit
                  const displayContent = hasContent ? truncateText(content, 500) : 'Processing...'

                  return (
                    <motion.div
                      key={mode.mode}
                      initial={{ opacity: 0, y: 30, scale: 0.9 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      transition={{
                        duration: 0.5,
                        delay: index * 0.1,
                        type: "spring",
                        stiffness: 300,
                        damping: 24
                      }}
                      whileHover={{
                        y: -6,
                        scale: 1.015,
                        transition: {
                          type: "spring",
                          stiffness: 400,
                          damping: 10
                        }
                      }}
                    >
                      <Card
                        className="h-full bg-card/50 backdrop-blur-sm border-border/50 hover:border-primary/30 transition-all duration-300 overflow-hidden group relative cursor-pointer"
                        onClick={() => handleCardEdit(mode.mode)}
                      >
                        {/* Gradient overlay */}
                        <div className={`absolute inset-0 bg-gradient-to-br ${mode.gradient} opacity-0 group-hover:opacity-5 transition-opacity duration-300`} />

                        {/* Shimmer effect */}
                        <div className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/10 to-transparent group-hover:translate-x-full transition-transform duration-700" />

                        <CardHeader className="pb-2 relative">
                          <motion.div
                            className={`w-12 h-12 rounded-xl bg-gradient-to-br ${mode.gradient} flex items-center justify-center mb-4 shadow-lg shadow-primary/20 relative`}
                            whileHover={{
                              scale: 1.1,
                              rotate: 5
                            }}
                            transition={{ type: "spring", stiffness: 300, damping: 10 }}
                          >
                            <mode.icon className="h-6 w-6 text-white" />
                            <div className={`absolute inset-0 rounded-xl bg-gradient-to-br ${mode.gradient} opacity-10`} />
                          </motion.div>

                          <div className="flex items-center justify-between mb-1">
                            <CardTitle className="text-lg font-bold text-white group-hover:text-primary transition-colors duration-300">
                              {mode.title}
                            </CardTitle>

                            {/* Edit Icon - inline with title */}
                            <div
                              className="opacity-0 group-hover:opacity-100 transition-opacity duration-300 cursor-pointer"
                              onClick={(e) => {
                                e.stopPropagation()
                                handleCardEdit(mode.mode)
                              }}
                            >
                              <div className="bg-primary/20 backdrop-blur-sm rounded-full p-1.5 border border-primary/30 hover:bg-primary/30 transition-colors">
                                <Edit3 className="h-3.5 w-3.5 text-primary" />
                              </div>
                            </div>
                          </div>
                          <CardDescription className="text-gray-400 text-xs leading-tight mb-3">
                            {mode.description}
                          </CardDescription>
                        </CardHeader>

                        <CardContent className="relative flex-1 pt-0">
                          <div className="bg-muted/20 rounded-lg p-4 h-full min-h-[280px] flex flex-col">
                            <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap flex-1">
                              {displayContent}
                            </p>
                          </div>
                        </CardContent>
                      </Card>
                    </motion.div>
                  )
                })}
              </div>

              {/* Action Buttons */}
              <div className="flex justify-center gap-4">
                {/* Back to Edit Button */}
                <motion.button
                  onClick={backToEdit}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, delay: 0.3 }}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  className="relative overflow-hidden group px-6 py-4 rounded-xl font-semibold shadow-lg hover:shadow-xl transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-gray-500/10 border border-gray-500/20 text-gray-400 hover:bg-gray-500/20 hover:text-gray-300"
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-gray-500/10 to-gray-400/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                  <span className="relative z-10 font-semibold transition-colors duration-300 flex items-center">
                    <Edit3 className="mr-2 h-5 w-5" />
                    Back to Edit
                  </span>
                </motion.button>

                {/* Add to Boo Button */}
                <motion.button
                  onClick={handleAddToDiary}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, delay: 0.4 }}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  className="relative overflow-hidden group px-8 py-4 rounded-xl font-semibold shadow-lg hover:shadow-xl transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20"
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-secondary/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                  <span className="relative z-10 text-primary font-semibold group-hover:text-primary transition-colors duration-300 flex items-center">
                    <BookOpen className="mr-2 h-5 w-5" />
                    Add to Boo
                  </span>
                </motion.button>

                {/* Start Over Button */}
                <motion.button
                  onClick={startNewEntry}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, delay: 0.5 }}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  className="relative overflow-hidden group px-6 py-4 rounded-xl font-semibold shadow-lg hover:shadow-xl transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-gray-500/10 border border-gray-500/20 text-gray-400 hover:bg-gray-500/20 hover:text-gray-300"
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-gray-500/10 to-gray-400/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                  <span className="relative z-10 font-semibold transition-colors duration-300 flex items-center">
                    <Plus className="mr-2 h-5 w-5" />
                    Start Over
                  </span>
                </motion.button>

                {/* Choose Date & Time Button */}
                <motion.button
                  onClick={() => {
                    // Reset to current date/time when opening modal
                    const now = new Date()
                    // Use local date instead of UTC to avoid timezone issues
                    const todayDate = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
                    const currentHour = now.getHours()
                    const currentMinute = now.getMinutes()

                    console.log('BEFORE RESET - backfillDate:', backfillDate)
                    console.log('RESETTING TO:', todayDate, currentHour, currentMinute)

                    setBackfillDate(todayDate)
                    setBackfillHour(currentHour > 12 ? currentHour - 12 : currentHour === 0 ? 12 : currentHour)
                    setBackfillMinute(currentMinute)
                    setBackfillAmPm(currentHour >= 12 ? 'PM' : 'AM')

                    setTempDate(todayDate)
                    setTempHour(currentHour > 12 ? currentHour - 12 : currentHour === 0 ? 12 : currentHour)
                    setTempMinute(currentMinute)
                    setTempAmPm(currentHour >= 12 ? 'PM' : 'AM')

                    console.log('AFTER RESET - should be updated on next render')
                    setShowBackfillModal(true)
                  }}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, delay: 0.6 }}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  className="relative overflow-hidden group px-6 py-4 rounded-xl font-semibold shadow-lg hover:shadow-xl transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-blue-500/10 border border-blue-500/20 text-blue-400 hover:bg-blue-500/20 hover:text-blue-300"
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-blue-500/10 to-blue-400/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                  <span className="relative z-10 font-semibold transition-colors duration-300 flex items-center">
                    <Calendar className="mr-2 h-5 w-5" />
                    Choose Date & Time
                  </span>
                </motion.button>
              </div>
            </motion.div>
          ) : null}
        </AnimatePresence>

        {/* Overlay Edit Modal */}
        <AnimatePresence>
          {showOverlay && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
              onClick={() => setShowOverlay(false)}
            >
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                transition={{ duration: 0.3 }}
                className="bg-card/90 backdrop-blur-xl border border-border/50 rounded-2xl shadow-2xl max-w-4xl w-full max-h-[80vh] flex flex-col overflow-hidden"
                onClick={(e) => e.stopPropagation()}
              >
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-border/50">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${viewModes.find(m => m.mode === overlayMode)?.gradient || 'from-primary to-secondary'
                      } flex items-center justify-center`}>
                      {overlayMode === 'raw' && <FileText className="h-5 w-5 text-white" />}
                      {overlayMode === 'enhanced' && <Pen className="h-5 w-5 text-white" />}
                      {overlayMode === 'structured' && <BookOpen className="h-5 w-5 text-white" />}
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-white">
                        Edit {viewModes.find(m => m.mode === overlayMode)?.title}
                      </h3>
                      <p className="text-sm text-gray-400">
                        Make changes to your {overlayMode} entry
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => setShowOverlay(false)}
                    className="p-2 rounded-full hover:bg-muted/50 transition-colors"
                  >
                    <X className="h-5 w-5 text-gray-400" />
                  </button>
                </div>

                {/* Content */}
                <div className="flex-1 p-6 overflow-hidden">
                  <Textarea
                    value={overlayContent}
                    onChange={(e) => setOverlayContent(e.target.value)}
                    className="w-full h-full min-h-[400px] resize-none text-sm leading-relaxed text-white placeholder:text-gray-400 bg-muted/20 border-border focus:border-primary/50 transition-colors"
                    placeholder="Edit your content here..."
                  />
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between p-6 border-t border-border/50">
                  <div className="text-sm text-gray-400">
                    {overlayContent.trim().split(/\s+/).filter(Boolean).length} words
                  </div>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => setShowOverlay(false)}
                      className="px-4 py-2 rounded-lg border border-border/50 text-gray-400 hover:bg-muted/50 transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleSaveEdit}
                      className="px-6 py-2 rounded-lg bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 transition-colors flex items-center gap-2"
                    >
                      <Save className="h-4 w-4" />
                      Save Changes
                    </button>
                  </div>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Backfill Entry Modal */}
        <AnimatePresence>
          {showBackfillModal && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
              onClick={() => {
                setShowBackfillModal(false)
                setShowBackfillCalendar(false)
              }}
            >
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                transition={{ duration: 0.3 }}
                className="bg-card/90 backdrop-blur-xl border border-border/50 rounded-2xl shadow-2xl max-w-md w-full"
                onClick={(e) => e.stopPropagation()}
              >
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-border/50">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center">
                      <Calendar className="h-5 w-5 text-white" />
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-white">
                        Backfill Entry
                      </h3>
                      <p className="text-sm text-gray-400">
                        Choose a date and time for this entry
                      </p>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setShowBackfillModal(false)
                      setShowBackfillCalendar(false)
                    }}
                    className="h-8 w-8 p-0 text-blue-300 drop-shadow-[0_0_4px_rgba(147,197,253,0.6)] hover:bg-muted/50 hover:text-white hover:drop-shadow-[0_0_6px_rgba(255,255,255,0.6)]"
                    title="Close modal"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>

                {/* Content */}
                <div className="p-6">
                  <div className="space-y-4">
                    <div className="space-y-3">
                      <div className="flex items-center gap-2">
                        <Calendar className="h-4 w-4 text-blue-400" />
                        <div className="relative flex-1 backfill-calendar-container">
                          <button
                            type="button"
                            onClick={() => {
                              // Always reset to current date/time when opening calendar
                              const now = new Date()
                              const todayDate = now.toISOString().split('T')[0]
                              const currentHour = now.getHours()
                              const currentMinute = now.getMinutes()

                              // Set BOTH backfill and temp values to current time
                              setBackfillDate(todayDate)
                              setBackfillHour(currentHour > 12 ? currentHour - 12 : currentHour === 0 ? 12 : currentHour)
                              setBackfillMinute(currentMinute)
                              setBackfillAmPm(currentHour >= 12 ? 'PM' : 'AM')

                              setTempDate(todayDate)
                              setTempHour(currentHour > 12 ? currentHour - 12 : currentHour === 0 ? 12 : currentHour)
                              setTempMinute(currentMinute)
                              setTempAmPm(currentHour >= 12 ? 'PM' : 'AM')
                              setShowBackfillCalendar(!showBackfillCalendar)
                            }}
                            className="w-full bg-background/50 border border-border rounded-lg px-3 py-2 text-white text-sm text-left hover:bg-background/70 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors duration-200"
                          >
                            {backfillDate ? new Date(`${backfillDate}T${getFormattedTime()}`).toLocaleString('en-US', {
                              weekday: 'short',
                              year: 'numeric',
                              month: 'short',
                              day: 'numeric',
                              hour: 'numeric',
                              minute: '2-digit',
                              hour12: true
                            }) : 'Select date and time'}
                          </button>
                          {showBackfillCalendar && (
                            <>
                              {/* Background blur overlay */}
                              <div
                                className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[99]"
                                onClick={() => setShowBackfillCalendar(false)}
                              />
                              {/* Calendar popup - positioned to avoid clipping */}
                              <div className="fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-[100] min-w-[320px]">
                                <div className="bg-card/95 backdrop-blur-xl border border-border/70 rounded-lg shadow-2xl p-4">
                                  <CalendarComponent
                                    selected={tempDate}
                                    maxDate={new Date()}
                                    onSelect={(date) => {
                                      setTempDate(date)
                                      // Don't auto-close - let user set time too
                                    }}
                                    className="shadow-lg border border-border/50"
                                  />
                                  {/* Time picker */}
                                  <div className="mt-4 space-y-3">
                                    <div className="flex items-center gap-3">
                                      <Clock className="h-4 w-4 text-purple-400" />
                                      <div className="flex items-center gap-2">
                                        {/* Hour Input */}
                                        <input
                                          type="number"
                                          min="1"
                                          max="12"
                                          value={tempHour}
                                          onChange={(e) => {
                                            const hour = parseInt(e.target.value) || 1
                                            if (hour >= 1 && hour <= 12) {
                                              setTempHour(hour)
                                            }
                                          }}
                                          className="w-16 px-3 py-2 bg-background/70 border border-border/70 rounded-lg text-white text-sm text-center focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500 hover:bg-background/80 transition-colors"
                                        />

                                        <span className="text-white">:</span>

                                        {/* Minute Input */}
                                        <input
                                          type="number"
                                          min="0"
                                          max="59"
                                          value={tempMinute.toString().padStart(2, '0')}
                                          onChange={(e) => {
                                            const minute = parseInt(e.target.value) || 0
                                            if (minute >= 0 && minute <= 59) {
                                              setTempMinute(minute)
                                            }
                                          }}
                                          className="w-16 px-3 py-2 bg-background/70 border border-border/70 rounded-lg text-white text-sm text-center focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500 hover:bg-background/80 transition-colors"
                                        />

                                        {/* AM/PM Toggle */}
                                        <button
                                          type="button"
                                          onClick={() => setTempAmPm(tempAmPm === 'AM' ? 'PM' : 'AM')}
                                          className="ml-2 px-3 py-2 bg-gradient-to-br from-blue-500 to-purple-600 text-white text-sm font-medium rounded-lg hover:from-blue-600 hover:to-purple-700 transition-all duration-200 hover:scale-105 shadow-md"
                                        >
                                          {tempAmPm}
                                        </button>
                                      </div>
                                    </div>
                                    {/* Validation Error */}
                                    <AnimatePresence>
                                      {isTempTimeFuture() && (
                                        <motion.div
                                          initial={{ opacity: 0, height: 0, marginTop: 0 }}
                                          animate={{ opacity: 1, height: "auto", marginTop: 12 }}
                                          exit={{ opacity: 0, height: 0, marginTop: 0 }}
                                          transition={{ duration: 0.3, ease: "easeInOut" }}
                                          className="overflow-hidden"
                                        >
                                          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 flex items-start gap-2">
                                            <AlertCircle className="h-4 w-4 text-red-400 flex-shrink-0 mt-0.5" />
                                            <p className="text-red-400 text-xs leading-relaxed">
                                              {getRandomFutureTimeMessage()}
                                            </p>
                                          </div>
                                        </motion.div>
                                      )}
                                    </AnimatePresence>

                                    {/* Apply button */}
                                    <Button
                                      onClick={() => {
                                        if (!isTempTimeFuture()) {
                                          // Apply temp values to main state
                                          setBackfillDate(tempDate)
                                          setBackfillHour(tempHour)
                                          setBackfillMinute(tempMinute)
                                          setBackfillAmPm(tempAmPm)
                                          setShowBackfillCalendar(false)
                                        }
                                      }}
                                      disabled={isTempTimeFuture()}
                                      className="w-full bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white border-0 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                      Apply
                                    </Button>
                                  </div>
                                </div>
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                    </div>

                    <p className="text-xs text-gray-400">
                      Entry will be saved with the selected date/time to maintain your diary timeline
                    </p>
                  </div>
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between p-6 border-t border-border/50">
                  <button
                    onClick={() => {
                      setShowBackfillModal(false)
                      setShowBackfillCalendar(false)
                    }}
                    className="px-6 py-2 rounded-lg border border-border/50 text-gray-400 hover:bg-muted/50 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => {
                      if (!isSelectedTimeFuture()) {
                        setShowBackfillModal(false)
                        setShowBackfillCalendar(false)
                      }
                    }}
                    disabled={!backfillDate || isSelectedTimeFuture()}
                    className="relative overflow-hidden group px-8 py-3 rounded-md font-medium shadow-md hover:shadow-lg hover:scale-[1.02] transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
                  >
                    <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-secondary/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                    <span className="relative z-10 text-primary font-medium group-hover:text-primary transition-colors duration-300">
                      Save
                    </span>
                  </button>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

export default NewEntryPage