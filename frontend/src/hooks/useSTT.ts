import { useState, useEffect, useRef } from 'react'
import { wsClient } from '@/lib/websocket'
import type { STTState, TranscriptionResult } from '@/lib/websocket'

// Recording states based on backend implementation (same as NewEntryPage)
const RecordingState = {
  IDLE: 'idle',
  RECORDING: 'recording',
  PROCESSING: 'processing',
  TRANSCRIBING: 'transcribing'
}

export function useSTT() {
  const [recordingState, setRecordingState] = useState(RecordingState.IDLE)
  const [transcription, setTranscription] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  
  const isStartingRef = useRef(false) // Prevent multiple simultaneous recording attempts

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
        // Don't show error on initial connection failure - let user trigger manually
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
        // Just set the text, don't accumulate here - that's handled in the component
        setTranscription(result.text)
        setRecordingState(RecordingState.IDLE)
      }
    })

    // Subscribe to errors
    const unsubscribeError = wsClient.onError((error: string) => {
      console.error('WebSocket error:', error)
      // Only show error for critical errors, not connection state changes or recording state conflicts
      const shouldSkipError = error.includes('connection') || 
                             error.includes('WebSocket') || 
                             error.includes('Cannot start recording in state') ||
                             error.includes('Failed to start STT recording') ||
                             !error.trim()
      
      if (!shouldSkipError) {
        setError(error.trim() || "An unknown error occurred")
      }
      setRecordingState(RecordingState.IDLE)
    })

    // Cleanup on unmount
    return () => {
      unsubscribeConnection()
      unsubscribeState()
      unsubscribeTranscription()
      unsubscribeError()
    }
  }, [])

  const startRecording = async () => {
    // Only proceed if we're truly idle and not already starting
    if (isStartingRef.current || recordingState !== RecordingState.IDLE) {
      return
    }
    
    // Check actual WebSocket connection state
    if (!wsClient.isConnected()) {
      setError("Please ensure connection is established")
      return
    }
    
    isStartingRef.current = true
    // Don't reset the flag immediately - let the state change handler reset it
    wsClient.startRecording()
  }

  const stopRecording = () => {
    if (recordingState === RecordingState.RECORDING) {
      setRecordingState(RecordingState.PROCESSING)
      wsClient.stopRecording()
    }
  }

  return {
    recordingState,
    transcription,
    error,
    isConnected,
    startRecording,
    stopRecording,
    isRecording: recordingState === RecordingState.RECORDING,
    isTranscribing: recordingState === RecordingState.PROCESSING || recordingState === RecordingState.TRANSCRIBING
  }
}

// Export the WebSocket client methods for direct use if needed
export { wsClient }