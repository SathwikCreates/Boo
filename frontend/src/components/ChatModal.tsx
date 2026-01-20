import { useState, useEffect, useRef, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Mic, MicOff, Send, Volume2, X, Loader2 } from 'lucide-react'
import { api } from '@/lib/api'
import { wsClient } from '@/lib/websocket'
import type { STTState, TranscriptionResult } from '@/lib/websocket'
import { motion, AnimatePresence } from 'framer-motion'
import { useToast } from '@/components/ui/use-toast'
import { useVoiceSettings } from '@/hooks/useVoiceSettings'

// Typewriter Text Component for chat messages
interface TypewriterTextProps {
  text: string
  isActive: boolean
  className?: string
  onComplete?: () => void
}

function TypewriterText({ text, isActive, className = '', onComplete }: TypewriterTextProps) {
  const [displayedText, setDisplayedText] = useState('')
  const [currentIndex, setCurrentIndex] = useState(0)

  useEffect(() => {
    if (!isActive) {
      setDisplayedText(text)
      setCurrentIndex(text.length)
      return
    }

    if (currentIndex < text.length) {
      const timer = setTimeout(() => {
        setDisplayedText(text.slice(0, currentIndex + 1))
        setCurrentIndex(currentIndex + 1)
      }, 25) // Faster than the main card (25ms vs 80ms)

      return () => clearTimeout(timer)
    } else if (onComplete && currentIndex === text.length) {
      onComplete()
    }
  }, [currentIndex, text, isActive, onComplete])

  // Reset when text changes
  useEffect(() => {
    if (isActive) {
      setDisplayedText('')
      setCurrentIndex(0)
    } else {
      setDisplayedText(text)
      setCurrentIndex(text.length)
    }
  }, [text, isActive])

  return (
    <span className={className}>
      {displayedText}
      {isActive && currentIndex < text.length && (
        <motion.span
          animate={{ opacity: [1, 0] }}
          transition={{ duration: 0.8, repeat: Infinity }}
          className="text-primary"
        >
          |
        </motion.span>
      )}
    </span>
  )
}

interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  isStreaming?: boolean
}

interface ChatModalProps {
  isOpen: boolean
  onClose: (transcription: string, duration: number, messageCount: number, searchQueries: string[]) => void
  onEndChat: (transcription: string, duration: number, messageCount: number, searchQueries: string[]) => void
}

function ChatModal({ isOpen, onClose, onEndChat }: ChatModalProps) {
  const { voiceEnabled, setVoiceEnabled } = useVoiceSettings()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputText, setInputText] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [memoryEnabled, setMemoryEnabled] = useState(true) // Session-level memory setting
  const [processingMessage, setProcessingMessage] = useState('')
  const [isToolCall, setIsToolCall] = useState(false)
  const [searchQueries, setSearchQueries] = useState<string[]>([])
  const [startTime, setStartTime] = useState<Date | null>(null)
  const [audioPlaying, setAudioPlaying] = useState(false)
  const [ttsInitialized, setTtsInitialized] = useState(false)
  const audioContextRef = useRef<AudioContext | null>(null)
  const currentAudioSourceRef = useRef<AudioBufferSourceNode | null>(null)
  const { toast } = useToast()

  // Track processing stages per entry for consolidated completion notification
  const [processingStages, setProcessingStages] = useState<Record<number, Set<string>>>({})

  // Helper function to ensure toast content is valid (same as NewEntryPage)
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

  // Handle processing status updates from WebSocket
  const handleProcessingStatusUpdate = (data: any) => {
    const { type, entry_id, message } = data

    // Track completion stages for each entry
    if (entry_id && (type === 'chat_entry_embedding_completed' || type === 'chat_entry_mood_completed')) {
      setProcessingStages(prev => {
        const entryStages = prev[entry_id] || new Set()
        const newStages = new Set(entryStages)

        if (type === 'chat_entry_embedding_completed') {
          newStages.add('embedding')
        } else if (type === 'chat_entry_mood_completed') {
          newStages.add('mood')
        }

        // Check if all processing is complete (both embedding and mood analysis)
        if (newStages.has('embedding') && newStages.has('mood')) {
          // Show consolidated completion toast
          safeToast({
            title: "✅ Entry added",
            description: "Your entry has been saved and fully processed",
            duration: 4000
          })

          // Clean up tracking for this entry
          const updatedStages = { ...prev }
          delete updatedStages[entry_id]
          return updatedStages
        }

        return { ...prev, [entry_id]: newStages }
      })
      return
    }

    switch (type) {
      case 'chat_entry_processing_started':
        // Optional: show processing start notification (could be too noisy)
        console.log(`Processing started for chat entry ${entry_id}`)
        break

      case 'chat_entry_processing_completed':
        safeToast({
          title: "✅ Entry processed",
          description: "Your chat entry has been fully processed and saved",
          duration: 4000
        })
        break

      case 'chat_entry_processing_failed':
        safeToast({
          title: "❌ Processing failed",
          description: "Failed to process your chat entry",
          variant: "destructive",
          duration: 4000
        })
        break

      default:
        console.log('Unknown processing status:', type)
    }
  }

  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const messageIdCounter = useRef(0)

  // STT state management - exact same as NewEntryPage
  const RecordingState = {
    IDLE: 'idle',
    RECORDING: 'recording',
    PROCESSING: 'processing',
    TRANSCRIBING: 'transcribing'
  }

  const [recordingState, setRecordingState] = useState(RecordingState.IDLE)
  const [sttTranscription, setSttTranscription] = useState('')
  const [sttError, setSttError] = useState<string | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [recordingSource, setRecordingSource] = useState<'hotkey' | 'button' | null>(null)
  const isStartingRef = useRef(false)

  // Load hotkey from preferences - exact same as NewEntryPage
  const [currentHotkey, setCurrentHotkey] = useState('F8')

  const loadPreferences = async () => {
    try {
      const response = await api.getPreferences()
      if (response.success && response.data && response.data.preferences) {
        // Load hotkey preference
        const hotkey = response.data.preferences.find((pref: any) => pref.key === 'hotkey')
        if (hotkey && hotkey.typed_value) {
          setCurrentHotkey(hotkey.typed_value)
        }

        // Load memory setting for this session
        const memoryEnabledPref = response.data.preferences.find((pref: any) => pref.key === 'memory_enabled')
        if (memoryEnabledPref !== undefined) {
          setMemoryEnabled(memoryEnabledPref.typed_value !== false)
        }
      }
    } catch (error) {
      console.error('Failed to load preferences:', error)
    }
  }

  useEffect(() => {
    loadPreferences()
  }, [])

  // WebSocket connection and STT state management - exact same as NewEntryPage
  useEffect(() => {
    const safeToast = (toastProps: any) => {
      try {
        toast(toastProps)
      } catch (error) {
        console.error('Toast error:', error)
      }
    }

    // Subscribe to connection changes first (before connecting)
    const unsubscribeConnection = wsClient.onConnectionChange((connected) => {
      console.log('WebSocket connection state changed:', connected)
      setIsConnected(connected)
      if (connected) {
        // Subscribe to STT channels and processing channel
        wsClient.subscribeToChannels(['stt', 'recording', 'transcription', 'processing'])
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
          wsClient.subscribeToChannels(['stt', 'recording', 'transcription', 'processing'])
        }
      } catch (error) {
        console.error('Initial WebSocket connection failed:', error)
        // Don't show error on initial connection failure - let user trigger manually
        setIsConnected(false)
      }
    }

    if (isOpen) {
      connectWithRetry()
    }

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
        setSttTranscription(result.text)
        setRecordingState(RecordingState.IDLE)
        // Text will be added to input via the useEffect that watches sttTranscription
      }
    })

    // Subscribe to processing status updates
    const unsubscribeProcessing = wsClient.onMessage('*', (message) => {
      // Only handle processing-related messages
      if (message.data?.type?.includes('chat_entry_processing') ||
        message.data?.type?.includes('chat_entry_embedding') ||
        message.data?.type?.includes('chat_entry_mood') ||
        (message.data?.job?.type?.includes('chat_entry_processing')) ||
        (message.data?.job?.type?.includes('chat_entry_embedding')) ||
        (message.data?.job?.type?.includes('chat_entry_mood'))) {
        console.log('Processing status update:', message)
        // Handle both direct type and job.type formats
        const statusData = message.data?.job || message.data
        handleProcessingStatusUpdate(statusData)
      }
    })

    // Subscribe to errors
    const unsubscribeError = wsClient.onError((error: string) => {
      console.error('WebSocket error:', error)
      // Only show error for critical errors
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
                wsClient.subscribeToChannels(['stt', 'recording', 'transcription', 'processing'])
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
              wsClient.subscribeToChannels(['stt', 'recording', 'transcription', 'processing'])

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
          setSttError(error.trim() || "An unknown error occurred")
          setTimeout(() => {
            if (document.activeElement && document.activeElement !== document.body) {
              (document.activeElement as HTMLElement).blur()
            }
            safeToast({
              title: "❌ Recording failed",
              description: error || "Failed to process speech",
            })
          }, 10)
        }, 100)
      } else {
        setRecordingState(RecordingState.IDLE)
      }
    })

    // Cleanup on unmount or when modal closes
    return () => {
      unsubscribeConnection()
      unsubscribeState()
      unsubscribeTranscription()
      unsubscribeProcessing()
      unsubscribeError()
    }
  }, [isOpen, toast])

  // Listen for hotkey press events (HOLD to record) - exact same as NewEntryPage
  useEffect(() => {
    const handleKeyDown = async (e: KeyboardEvent) => {
      // Check if it's the recording hotkey
      if (e.key === currentHotkey || e.key.toUpperCase() === currentHotkey.toUpperCase()) {
        if (!e.repeat && recordingState === RecordingState.IDLE) {
          e.preventDefault()
          setRecordingSource('hotkey')
          await startRecording()
        } else if (e.repeat) {
          // Prevent repeated key presses while already recording
          e.preventDefault()
        }
      }
    }

    const handleKeyUp = (e: KeyboardEvent) => {
      // Check if it's the recording hotkey
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

  // Initialize modal without immediate greeting
  useEffect(() => {
    if (isOpen) {
      setStartTime(new Date())
      if (voiceEnabled) {
        initializeTTS()
      }

      // Set up delayed greeting - only show if user hasn't sent anything in 10 seconds and isn't actively using STT or typing
      const greetingTimer = setTimeout(() => {
        // Only show greeting if no messages have been sent yet, no STT activity, and no text in input
        if (messages.length === 0 && recordingState === RecordingState.IDLE && !inputText.trim()) {
          initializeChat()
        }
      }, 10000) // 10 seconds

      return () => clearTimeout(greetingTimer)
    } else {
      // Reset state when modal closes
      setMessages([])
      setInputText('')
      setSearchQueries([])
      setStartTime(null)
      setTtsInitialized(false)
      // Stop any playing audio
      if (currentAudioSourceRef.current) {
        try {
          currentAudioSourceRef.current.stop()
        } catch (e) {
          // Audio might already be stopped
        }
        currentAudioSourceRef.current = null
      }
      // Close AudioContext
      if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
        audioContextRef.current.close()
        audioContextRef.current = null
      }
    }
  }, [isOpen, messages.length, recordingState, inputText])

  // Initialize TTS when voice is enabled
  useEffect(() => {
    if (isOpen && voiceEnabled && !ttsInitialized) {
      initializeTTS()
    }
    // Stop audio if voice is disabled
    if (!voiceEnabled && currentAudioSourceRef.current) {
      try {
        currentAudioSourceRef.current.stop()
      } catch (e) {
        // Audio might already be stopped
      }
      currentAudioSourceRef.current = null
      setAudioPlaying(false)
    }
  }, [voiceEnabled, isOpen, ttsInitialized])

  // Update input when STT transcription changes - accumulate text with space continuation
  useEffect(() => {
    if (sttTranscription) {
      setInputText(prevText => {
        if (!prevText) return sttTranscription
        // Add space for continuation
        return prevText + ' ' + sttTranscription
      })
      // Clear the transcription after adding it to prevent duplicates
      setSttTranscription('')
    }
  }, [sttTranscription])

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight
    }
  }, [messages])


  const initializeChat = async () => {
    try {
      const response = await api.getDiaryGreeting()
      if (response.success && response.data) {
        // Ensure we extract the actual string content
        const greetingText = typeof response.data === 'string' ? response.data :
          (response.data as any)?.data ||
          String(response.data)

        const greetingMessage: ChatMessage = {
          id: messageIdCounter.current++,
          role: 'assistant',
          content: greetingText,
          timestamp: new Date(),
          isStreaming: true // Enable typewriter animation
        }
        setMessages([greetingMessage])

        // TTS will be handled by the TypewriterText onComplete callback
      }
    } catch (error) {
      console.error('Failed to get greeting:', error)
      // Fallback greeting
      const fallbackGreeting: ChatMessage = {
        id: messageIdCounter.current++,
        role: 'assistant',
        content: "Hi! I'm Boo, your diary companion. You can type or use the voice button to talk with me. What's on your mind?",
        timestamp: new Date(),
        isStreaming: true // Enable typewriter animation
      }
      setMessages([fallbackGreeting])

      // TTS will be handled by the TypewriterText onComplete callback
    }
  }

  const initializeTTS = async () => {
    try {
      const response = await api.initializeTTS()
      if (response.success) {
        setTtsInitialized(true)
        console.log('TTS initialized successfully')
      }
    } catch (error) {
      console.error('Failed to initialize TTS:', error)
      // Don't show error to user, just disable TTS silently
    }
  }

  const initializeAudioContext = () => {
    if (!audioContextRef.current) {
      try {
        audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)()

        // Resume AudioContext if it's suspended (required by some browsers)
        if (audioContextRef.current.state === 'suspended') {
          audioContextRef.current.resume()
        }
      } catch (error) {
        console.error('Failed to create AudioContext:', error)
        return false
      }
    }
    return true
  }

  const stripTTSProblematicChars = (text: string): string => {
    // Remove markdown emphasis (*, **) and hash symbols
    let cleanText = text.replace(/\*+/g, '')
      .replace(/#/g, '') // Remove hash/pound symbols

    // Remove emojis (common Unicode ranges)
    cleanText = cleanText
      // Emoticons (😀-😿)
      .replace(/[\u{1F600}-\u{1F64F}]/gu, '')
      // Symbols & pictographs (🌀-🗿)
      .replace(/[\u{1F300}-\u{1F5FF}]/gu, '')
      // Transport & map symbols (🚀-🛿)
      .replace(/[\u{1F680}-\u{1F6FF}]/gu, '')
      // Supplemental symbols (🤀-🧿)
      .replace(/[\u{1F900}-\u{1F9FF}]/gu, '')
      // Extended pictographs (🪀-🫿)
      .replace(/[\u{1FA70}-\u{1FAFF}]/gu, '')
      // Miscellaneous symbols (☀-⛿)
      .replace(/[\u{2600}-\u{26FF}]/gu, '')
      // Dingbats (✀-➿)
      .replace(/[\u{2700}-\u{27BF}]/gu, '')

    // Clean up extra whitespace that might result from removals
    cleanText = cleanText.replace(/\s+/g, ' ').trim()

    return cleanText
  }

  const playAudioForMessage = async (text: string) => {
    if (!voiceEnabled || !ttsInitialized || audioPlaying) return

    try {
      setAudioPlaying(true)

      // Apply second-level stripping: Remove TTS-problematic characters when voice is ON
      const ttsText = stripTTSProblematicChars(text)

      // Initialize AudioContext if needed
      if (!initializeAudioContext()) {
        // Fallback to HTML audio
        await playAudioFallback(ttsText)
        return
      }

      // Synthesize speech (non-streaming for natural voice resonance)
      const audioBlob = await api.synthesizeSpeech(ttsText, false)
      const arrayBuffer = await audioBlob.arrayBuffer()

      // Decode audio data using AudioContext
      const audioBuffer = await audioContextRef.current!.decodeAudioData(arrayBuffer)

      // Create and configure audio source
      const source = audioContextRef.current!.createBufferSource()
      source.buffer = audioBuffer
      source.connect(audioContextRef.current!.destination)

      // Handle playback end
      source.onended = () => {
        setAudioPlaying(false)
        currentAudioSourceRef.current = null
      }

      // Store reference and start playback
      currentAudioSourceRef.current = source
      source.start(0)

    } catch (error) {
      console.error('AudioContext playback failed, trying fallback:', error)
      // Fallback to HTML audio (also strip problematic chars)
      const ttsText = stripTTSProblematicChars(text)
      await playAudioFallback(ttsText)
    }
  }

  const playAudioFallback = async (text: string) => {
    try {
      // Note: text should already be cleaned by caller
      // Synthesize speech (non-streaming for natural voice resonance)
      const audioBlob = await api.synthesizeSpeech(text, false)
      const audioUrl = URL.createObjectURL(audioBlob)

      // Create and play audio using HTML Audio
      const audio = new Audio(audioUrl)
      audio.onended = () => {
        setAudioPlaying(false)
        URL.revokeObjectURL(audioUrl)
      }
      audio.onerror = () => {
        setAudioPlaying(false)
        URL.revokeObjectURL(audioUrl)
        console.error('HTML Audio playback failed')
      }

      await audio.play()
    } catch (error) {
      console.error('All audio playback methods failed:', error)
      setAudioPlaying(false)
    }
  }



  // Recording functions - exact same as NewEntryPage
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
          wsClient.subscribeToChannels(['stt', 'recording', 'transcription', 'processing'])
          console.log('WebSocket reconnected successfully')
        } else {
          throw new Error('Failed to reconnect')
        }
      } catch (error) {
        // Remove focus to prevent focus ring on hotkey-triggered toasts
        if (document.activeElement && document.activeElement !== document.body) {
          (document.activeElement as HTMLElement).blur()
        }
        setTimeout(() => {
          safeToast({
            title: "Connection Error",
            description: "Please ensure connection is established",
            variant: "destructive"
          })
        }, 10)
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

  const getRecordingStatusText = () => {
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
        return "Transcribing speech..."
      default:
        return ""
    }
  }

  const handleSendMessage = async () => {
    if (!inputText.trim() || isProcessing) return

    const userMessage: ChatMessage = {
      id: messageIdCounter.current++,
      role: 'user',
      content: inputText.trim(),
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
    setInputText('')
    setIsProcessing(true)

    // Set initial processing message
    setProcessingMessage('Analyzing your question...')

    // Send message to AI
    try {
      const conversationHistory = messages.map(msg => ({
        role: msg.role,
        content: msg.content
      }))

      const response = await api.sendDiaryChatMessage(
        userMessage.content,
        conversationHistory,
        undefined, // conversationId
        memoryEnabled
      )

      if (response.success && response.data) {
        // Extract chat data from nested response structure
        const chatData = (response.data as any).data || response.data

        // Check if tool calls were made
        const hasToolCalls = chatData.tool_calls_made?.length > 0
        setIsToolCall(hasToolCalls)

        // Show progressive status updates using enhanced processing phases
        if (chatData.processing_phases && chatData.processing_phases.length > 0) {
          for (let i = 0; i < chatData.processing_phases.length; i++) {
            const phase = chatData.processing_phases[i]
            setProcessingMessage(phase.message)

            // Add a shorter delay between phases for better responsiveness
            if (i < chatData.processing_phases.length - 1) {
              await new Promise(resolve => setTimeout(resolve, 350))
            }
          }
        }

        // Update search queries
        if (chatData.search_queries_used?.length > 0) {
          setSearchQueries(prev => [...prev, ...chatData.search_queries_used])
        }

        // Extract the actual response text from the nested structure
        const responseText = typeof chatData.response === 'string' ? chatData.response :
          String(chatData.response || 'No response received')

        // Check for successful add_entry_to_diary tool calls and show toast
        if (hasToolCalls && chatData.tool_calls_made) {
          for (const toolCall of chatData.tool_calls_made) {
            if (toolCall.name === 'add_entry_to_diary' && toolCall.result?.success) {
              // Show immediate success toast for entry creation
              safeToast({
                title: "💾 Entry saved",
                description: "Your note has been saved to your diary and is being processed",
                duration: 3000
              })
              break // Only show one toast even if multiple entries were added
            }
          }
        }

        // Create AI response message
        const aiMessage: ChatMessage = {
          id: messageIdCounter.current++,
          role: 'assistant',
          content: responseText,
          timestamp: new Date(),
          isStreaming: true // We'll simulate streaming
        }

        setMessages(prev => [...prev, aiMessage])

        // TTS will be handled by the TypewriterText onComplete callback

      } else {
        console.error('Response not successful or missing data:', response)
        // Add fallback AI message for failed responses
        const errorMessage: ChatMessage = {
          id: messageIdCounter.current++,
          role: 'assistant',
          content: 'I apologize, but I encountered an issue processing your message. Please try again.',
          timestamp: new Date()
        }
        setMessages(prev => [...prev, errorMessage])
      }
    } catch (error) {
      console.error('Failed to send message:', error)
      // Remove focus to prevent focus ring on toasts
      if (document.activeElement && document.activeElement !== document.body) {
        (document.activeElement as HTMLElement).blur()
      }
      setTimeout(() => {
        safeToast({
          title: 'Failed to send message',
          description: 'Please check your connection and try again'
        })
      }, 10)
    } finally {
      setIsProcessing(false)
      setProcessingMessage('')
      setIsToolCall(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const getTranscription = () => {
    return messages.map(msg => {
      const speaker = msg.role === 'user' ? 'You' : 'Boo'
      const time = msg.timestamp.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit'
      })
      return `[${time}] ${speaker}: ${msg.content}`
    }).join('\n')
  }

  const getDuration = () => {
    if (!startTime) return 0
    return Math.floor((new Date().getTime() - startTime.getTime()) / 1000)
  }

  const handleEndChat = () => {
    const transcription = getTranscription()
    const duration = getDuration()
    const messageCount = messages.length
    onEndChat(transcription, duration, messageCount, searchQueries)
  }

  const handleClose = () => {
    const transcription = getTranscription()
    const duration = getDuration()
    const messageCount = messages.length
    onClose(transcription, duration, messageCount, searchQueries)
  }

  if (!isOpen) return null

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        className="bg-card/90 backdrop-blur-xl border border-border/50 rounded-2xl shadow-2xl max-w-5xl w-full h-[90vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-6 pt-6 pb-4 border-b border-border/50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                <Send className="h-4 w-4 text-white" />
              </div>
              <div>
                <h2 className="text-xl font-semibold text-white">Talk to Boo</h2>
                <p className="text-sm text-gray-400">Your AI journal companion</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Label htmlFor="modal-voice-toggle" className="text-sm text-gray-300">
                  Voice
                </Label>
                <Switch
                  id="modal-voice-toggle"
                  checked={voiceEnabled}
                  onCheckedChange={setVoiceEnabled}
                />
                <Volume2 className={`h-4 w-4 ${voiceEnabled ? 'text-primary' : 'text-muted-foreground'}`} />
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleEndChat}
                className="h-10 w-10 p-0 text-blue-300 drop-shadow-[0_0_4px_rgba(147,197,253,0.6)] hover:bg-muted/50 hover:text-white hover:drop-shadow-[0_0_6px_rgba(255,255,255,0.6)]"
                title="Close"
              >
                <X className="h-5 w-5" />
              </Button>
            </div>
          </div>
        </div>

        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Messages Area */}
          <div className="flex-1 px-6 py-4 overflow-y-auto space-y-4" ref={scrollAreaRef}>
            <div className="space-y-4">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${message.role === 'user' ? 'justify-start' : 'justify-end'}`}
                >
                  <div
                    className={`max-w-[70%] px-4 py-2 rounded-lg ${message.role === 'user'
                        ? 'bg-gradient-to-br from-blue-500/20 to-cyan-500/20 border border-blue-500/30 text-white'
                        : 'bg-gradient-to-br from-purple-500/20 to-pink-500/20 border border-purple-500/30 text-white'
                      }`}
                  >
                    <p className="text-sm whitespace-pre-wrap">
                      {message.role === 'assistant' && message.isStreaming ? (
                        <TypewriterText
                          text={message.content}
                          isActive={true}
                          onComplete={() => {
                            setMessages(prev => prev.map(msg =>
                              msg.id === message.id
                                ? { ...msg, isStreaming: false }
                                : msg
                            ))

                            // Play TTS when typewriter animation completes
                            if (voiceEnabled && ttsInitialized) {
                              playAudioForMessage(message.content)
                            }
                          }}
                        />
                      ) : (
                        message.content
                      )}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Processing Indicator */}
          {isProcessing && (
            <div className="px-6 py-2 border-t">
              <div className={`flex items-center gap-2 text-sm ${isToolCall ? 'text-green-600 dark:text-green-400' : 'text-muted-foreground'}`}>
                <Loader2 className="h-3 w-3 animate-spin" />
                <span>{typeof processingMessage === 'string' ? processingMessage : 'Processing...'}</span>
              </div>
            </div>
          )}

          {/* Audio Playing Indicator */}
          {audioPlaying && voiceEnabled && (
            <div className="px-6 py-2 border-t">
              <div className="flex items-center gap-2 text-sm text-primary">
                <Volume2 className="h-3 w-3 animate-pulse" />
                <span>Speaking...</span>
              </div>
            </div>
          )}

          {/* Input Area */}
          <div className="border-t px-6 py-2">
            <div className="relative">
              {/* Large text input area */}
              <textarea
                ref={inputRef as any}
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={handleKeyPress}
                placeholder={`Type your message, use the mic, or hold ${currentHotkey} to record...`}
                disabled={isProcessing || recordingState !== RecordingState.IDLE}
                className="w-full h-24 p-4 pr-28 pb-14 resize-none rounded-lg bg-background/50 border border-border text-white placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/50 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
                rows={3}
              />

              {/* Buttons positioned inside at bottom right with breathing room */}
              <div className="absolute bottom-3 right-3 flex flex-col gap-2">
                <button
                  onClick={toggleRecording}
                  disabled={isProcessing || recordingState === RecordingState.PROCESSING || recordingState === RecordingState.TRANSCRIBING}
                  className={`relative overflow-hidden group p-2 rounded-lg font-medium shadow-lg hover:shadow-xl transition-all duration-300 cursor-pointer inline-flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed w-8 h-8 ${recordingState === RecordingState.RECORDING
                      ? 'bg-red-500/20 border border-red-500/30 text-red-400 hover:bg-red-500/30'
                      : 'bg-gradient-to-br from-purple-500/20 to-pink-500/20 border border-purple-500/30 text-purple-300 hover:from-purple-500/30 hover:to-pink-500/30'
                    }`}
                >
                  <div className={`absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 ${recordingState === RecordingState.RECORDING
                      ? 'bg-gradient-to-r from-red-500/10 to-red-600/10'
                      : 'bg-gradient-to-r from-purple-500/10 to-pink-500/10'
                    }`} />
                  <span className="relative z-10">
                    {recordingState === RecordingState.RECORDING ? (
                      <MicOff className="h-4 w-4" />
                    ) : (
                      <Mic className="h-4 w-4" />
                    )}
                  </span>
                </button>
                <button
                  onClick={handleSendMessage}
                  disabled={!inputText.trim() || isProcessing}
                  className="relative overflow-hidden group p-2 rounded-lg font-medium shadow-lg hover:shadow-xl hover:scale-[1.02] transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-primary/20 border border-primary/40 text-primary hover:bg-primary/30 disabled:opacity-50 disabled:cursor-not-allowed w-8 h-8"
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-primary/20 to-secondary/20 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                  <span className="relative z-10">
                    <Send className="h-4 w-4" />
                  </span>
                </button>
              </div>
            </div>
            {/* Always show recording status area to prevent layout shift */}
            <div className="mt-2 h-4 flex items-center">
              {(recordingState !== RecordingState.IDLE) && (
                <p className="text-xs text-muted-foreground">
                  {getRecordingStatusText()}
                </p>
              )}
            </div>
            {sttError && (
              <p className="text-xs text-destructive mt-2">{sttError}</p>
            )}
          </div>

        </div>
      </motion.div>
    </motion.div>
  )
}

export default ChatModal