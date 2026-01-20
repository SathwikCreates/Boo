import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Calendar as CalendarComponent } from '@/components/ui/calendar'
import {
  Upload,
  FileAudio2,
  Loader2,
  CheckCircle,
  FileText,
  Pen,
  BookOpen,
  X,
  Edit3,
  Save,
  Play,
  Pause,
  AlertCircle,
  Calendar,
  Clock,
  Eye,
  Sparkles,
  Lightbulb,
  Plus,
  Mic
} from 'lucide-react'
import { useToast } from '@/components/ui/use-toast'
import { motion, AnimatePresence } from 'framer-motion'
import { api } from '@/lib/api'

// View modes configuration (same as NewEntryPage)
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

// Transcription-specific quirky loading messages
const transcriptionMessages = [
  "Listening to your voice...",
  "Decoding your audio waves...",
  "Converting speech to thoughts...",
  "Your voice is being transcribed...",
  "Turning audio into words...",
  "Capturing your spoken memories...",
  "Processing your voice recording...",
  "Translating sound waves to text...",
  "Your audio story is unfolding...",
  "Creating text from your voice..."
]

const SUPPORTED_FORMATS = ['.wav', '.mp3', '.m4a', '.aac', '.ogg', '.flac', '.webm']
const MAX_FILE_SIZE = 100 * 1024 * 1024 // 100MB in bytes

interface TranscriptionResult {
  transcription: string
  duration: number
  confidence?: number
}

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

function VoiceUploadPage() {
  const navigate = useNavigate()
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [transcriptionResult, setTranscriptionResult] = useState<TranscriptionResult | null>(null)
  const [editedTranscription, setEditedTranscription] = useState('')
  const [isTranscribing, setIsTranscribing] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const [transcriptionProgress, setTranscriptionProgress] = useState(0)
  const [currentLoadingMessage, setCurrentLoadingMessage] = useState('')
  const [createdEntries, setCreatedEntries] = useState<CreatedEntries | null>(null)
  const [processingMetadata, setProcessingMetadata] = useState<any>(null)
  const [showModal, setShowModal] = useState(false)
  const [showResults, setShowResults] = useState(false)
  const [currentReviewTip, setCurrentReviewTip] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [showTranscriptionCard, setShowTranscriptionCard] = useState(false)
  const [showOverlay, setShowOverlay] = useState(false)
  const [overlayContent, setOverlayContent] = useState('')
  const [overlayMode, setOverlayMode] = useState('')
  const [showUploadCard, setShowUploadCard] = useState(true)

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
  const [showHourDropdown, setShowHourDropdown] = useState(false)
  const [showMinuteDropdown, setShowMinuteDropdown] = useState(false)
  const [useCustomDateTime, setUseCustomDateTime] = useState(false)
  const [showCalendar, setShowCalendar] = useState(false)
  const [entryDateTime, setEntryDateTime] = useState('')

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

  const { toast } = useToast()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const audioRef = useRef<HTMLAudioElement>(null)
  const loadingMessageIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const progressIntervalRef = useRef<NodeJS.Timeout | null>(null)

  // Helper function to ensure toast content is valid (same as NewEntryPage)
  const safeToast = (params: Parameters<typeof toast>[0]) => {
    if (!params.title?.trim() && !params.description?.toString()?.trim()) {
      return // Don't show empty toasts
    }
    toast({
      ...params,
      duration: params.duration || 3000
    })
  }

  // Helper functions for time conversion
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


  // Cleanup function
  useEffect(() => {
    return () => {
      if (loadingMessageIntervalRef.current) {
        clearInterval(loadingMessageIntervalRef.current)
      }
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current)
      }
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl)
      }
    }
  }, [audioUrl])

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

  // Loading message cycling effect for processing (same as NewEntryPage)
  useEffect(() => {
    let interval: NodeJS.Timeout

    if (isProcessing && !showResults) {
      // Cycle through processing messages (same as NewEntryPage)
      const processingMessages = [
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

      let messageIndex = 0
      setCurrentLoadingMessage(processingMessages[0])

      interval = setInterval(() => {
        messageIndex = (messageIndex + 1) % processingMessages.length
        setCurrentLoadingMessage(processingMessages[messageIndex])
      }, 2000) // Change message every 2 seconds
    }

    return () => {
      if (interval) clearInterval(interval)
    }
  }, [isProcessing, showResults])

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

  // Validate file format and size
  const validateFile = (file: File): string | null => {
    const extension = '.' + file.name.split('.').pop()?.toLowerCase()

    if (!SUPPORTED_FORMATS.includes(extension)) {
      return `Unsupported file format. Please use one of: ${SUPPORTED_FORMATS.join(', ')}`
    }

    if (file.size > MAX_FILE_SIZE) {
      return `File too large. Maximum size is ${MAX_FILE_SIZE / (1024 * 1024)}MB. Please break this into smaller parts.`
    }

    return null
  }

  // Handle file selection
  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    const validationError = validateFile(file)
    if (validationError) {
      setError(validationError)
      safeToast({
        title: "Invalid File",
        description: validationError,
        variant: "destructive"
      })
      return
    }

    setSelectedFile(file)
    setError(null)
    setTranscriptionResult(null)
    setEditedTranscription('')
    setCreatedEntries(null)
    setProcessingMetadata(null)

    // Create audio URL for preview
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl)
    }
    const newAudioUrl = URL.createObjectURL(file)
    setAudioUrl(newAudioUrl)
  }

  // Handle drag and drop
  const handleDragOver = (event: React.DragEvent) => {
    event.preventDefault()
  }

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault()
    const file = event.dataTransfer.files[0]
    if (!file) return

    const validationError = validateFile(file)
    if (validationError) {
      setError(validationError)
      safeToast({
        title: "Invalid File",
        description: validationError,
        variant: "destructive"
      })
      return
    }

    setSelectedFile(file)
    setError(null)
    setTranscriptionResult(null)
    setEditedTranscription('')
    setCreatedEntries(null)
    setProcessingMetadata(null)

    // Create audio URL for preview
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl)
    }
    const newAudioUrl = URL.createObjectURL(file)
    setAudioUrl(newAudioUrl)
  }

  // Start cycling loading messages and progress
  const startLoadingEffects = () => {
    let messageIndex = 0
    setCurrentLoadingMessage(transcriptionMessages[0])
    setTranscriptionProgress(0)

    // Cycle loading messages
    loadingMessageIntervalRef.current = setInterval(() => {
      messageIndex = (messageIndex + 1) % transcriptionMessages.length
      setCurrentLoadingMessage(transcriptionMessages[messageIndex])
    }, 2000)

    // Simulate progress
    let progress = 0
    progressIntervalRef.current = setInterval(() => {
      progress += Math.random() * 15 + 5 // Random increment between 5-20
      if (progress > 95) progress = 95 // Cap at 95% until completion
      setTranscriptionProgress(progress)
    }, 800)
  }

  // Stop loading effects
  const stopLoadingEffects = () => {
    if (loadingMessageIntervalRef.current) {
      clearInterval(loadingMessageIntervalRef.current)
      loadingMessageIntervalRef.current = null
    }
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current)
      progressIntervalRef.current = null
    }
    setTranscriptionProgress(100)
  }

  // Handle audio transcription
  const handleTranscribe = async () => {
    if (!selectedFile) return

    setIsTranscribing(true)
    setError(null)
    startLoadingEffects()

    try {
      // Create form data for file upload
      const formData = new FormData()
      formData.append('audio_file', selectedFile)

      // Upload and transcribe the file
      const response = await api.uploadAndTranscribeAudio(formData)

      if (response.success && response.data) {
        // Handle double-nested response structure
        const actualData = (response.data as any).data || response.data
        console.log('Actual transcription data:', actualData) // Debug log
        const result: TranscriptionResult = {
          transcription: actualData.transcription,
          duration: actualData.duration || 0,
          confidence: actualData.confidence
        }

        setTranscriptionResult(result)
        setEditedTranscription(result.transcription)
        setShowTranscriptionCard(true)
        // Don't auto-open modal - let user click "View & Edit" button

        safeToast({
          title: "✓ Transcription Complete!",
          description: "Your audio has been converted to text successfully.",
        })
      } else {
        throw new Error(response.error || 'Failed to transcribe audio')
      }
    } catch (error) {
      console.error('Transcription error:', error)
      const errorMessage = error instanceof Error ? error.message : 'Failed to transcribe audio'
      setError(errorMessage)
      safeToast({
        title: "Transcription Failed",
        description: errorMessage,
        variant: "destructive"
      })
    } finally {
      setIsTranscribing(false)
      stopLoadingEffects()
    }
  }

  // Handle process entry (same pattern as NewEntryPage)
  const handleProcessEntry = async () => {
    if (!editedTranscription?.trim()) return

    // Hide modal and all cards first
    setShowModal(false)
    setShowTranscriptionCard(false)
    setShowUploadCard(false)

    // Clear current results and hide existing cards
    setCreatedEntries(null)
    setProcessingMetadata(null)
    setShowResults(false)

    // Small delay to ensure UI updates before showing loading
    setTimeout(() => {
      setIsProcessing(true)
    }, 100)

    try {
      const response = await api.processTextOnly(
        editedTranscription?.trim() || '',
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
        setCreatedEntries({
          raw: {
            id: 0,
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

        // Show results immediately (like NewEntryPage)
        setCurrentReviewTip(getRandomReviewTip())  // Set tip once before showing results
        setShowResults(true)
        setShowUploadCard(false)
      } else {
        throw new Error(response.error || 'Failed to process entry')
      }
    } catch (error) {
      console.error('Processing error:', error)
      safeToast({
        title: "Processing Failed",
        description: error instanceof Error ? error.message : "Failed to process entry",
        variant: "destructive"
      })
    } finally {
      setIsProcessing(false)
    }
  }

  // Handle save entries to diary (same as NewEntryPage)
  const handleSaveEntries = async () => {
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
        safeToast({
          title: "✨ Entry saved to diary!",
          description: "Your voice note has been added to your journal.",
        })

        // Redirect to view entries page to see the saved entry
        setTimeout(() => {
          navigate('/entries')
        }, 1000)

        // Trigger mood analysis in background if enhanced text is available
        if (createdEntry.id && createdEntries.enhanced?.enhanced_text) {
          try {
            await api.analyzeEntryMood(createdEntry.id)
            // Show mood analysis toast
            setTimeout(() => {
              safeToast({
                title: "✓ Moods added!",
                description: "AI detected moods and tagged your entry.",
              })
            }, 1500) // Show after 1.5 seconds to not conflict with main toast
          } catch (error) {
            console.error('Mood analysis failed:', error)
            // Don't show error toast - mood analysis is supplementary
          }
        }

        // Reset state (like NewEntryPage)
        setSelectedFile(null)
        setTranscriptionResult(null)
        setEditedTranscription('')
        setCreatedEntries(null)
        setProcessingMetadata(null)
        setShowModal(false)
        setShowResults(false)
        setShowTranscriptionCard(false)
        setShowUploadCard(true)

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
        if (audioUrl) {
          URL.revokeObjectURL(audioUrl)
          setAudioUrl(null)
        }
        if (fileInputRef.current) {
          fileInputRef.current.value = ''
        }
      } else {
        throw new Error(response.error || 'Failed to save entry')
      }
    } catch (error) {
      console.error('Save error:', error)
      safeToast({
        title: "Save Failed",
        description: error instanceof Error ? error.message : "Failed to save entry",
        variant: "destructive"
      })
    }
  }

  // Toggle audio playback
  const togglePlayback = () => {
    if (!audioRef.current) return

    if (isPlaying) {
      audioRef.current.pause()
      setIsPlaying(false)
    } else {
      audioRef.current.play()
      setIsPlaying(true)
    }
  }

  // Handle audio events
  const handleAudioEnded = () => {
    setIsPlaying(false)
  }

  // Handle card editing
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

  // Handle save edit
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

  // Truncate text helper (same as NewEntryPage)
  const truncateText = (text: string, maxLength: number) => {
    if (text.length <= maxLength) return text
    return text.substring(0, maxLength).trim() + '...'
  }

  return (
    <>
      <div className="h-screen flex flex-col p-4 md:p-6 overflow-hidden relative">
        <div className="max-w-6xl mx-auto w-full flex flex-col flex-1">
          {/* Header - Always shown */}
          <div className="flex items-center justify-between mb-4 min-h-[40px]">
            <h2 className="text-2xl font-bold text-white">Voice Upload</h2>
            <div className="flex items-center gap-2 flex-shrink-0">
              {!transcriptionResult && (
                <p className="text-gray-400 text-sm">
                  Upload and transcribe your voice notes from offline recordings
                </p>
              )}
            </div>
          </div>

          {/* Upload Area */}
          {showUploadCard && (
            <Card className="bg-card/50 backdrop-blur-sm border-border/50 mb-4">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-3">
                  <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center">
                    <FileAudio2 className="h-3.5 w-3.5 text-white" />
                  </div>
                  <div>
                    <CardTitle className="text-white text-lg">Upload Audio File</CardTitle>
                    <CardDescription className="text-gray-400 text-sm">
                      Select or drag your voice recording to get started
                    </CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                {/* File Upload Area */}
                <div
                  className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors ${error ? 'border-red-500/50 bg-red-500/5' : 'border-border/50 hover:border-primary/50 hover:bg-primary/5'
                    }`}
                  onDragOver={handleDragOver}
                  onDrop={handleDrop}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".wav,.mp3,.m4a,.aac,.ogg,.flac,.webm"
                    onChange={handleFileSelect}
                    className="hidden"
                  />

                  {selectedFile ? (
                    <div className="space-y-6">
                      <div className="flex items-center justify-center">
                        <div className="w-12 h-12 rounded-full bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center">
                          <FileAudio2 className="h-6 w-6 text-white" />
                        </div>
                      </div>
                      <div>
                        <p className="text-white font-medium">{selectedFile.name}</p>
                        <p className="text-gray-400 text-sm">
                          {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                        </p>
                      </div>

                      {/* Action Buttons - All in one line */}
                      <div className="flex items-center justify-between gap-2">
                        {/* Choose File - Left */}
                        <button
                          onClick={() => fileInputRef.current?.click()}
                          className="relative overflow-hidden group px-3 py-2 rounded-md font-medium shadow-md hover:shadow-lg hover:scale-[1.02] transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 w-[120px]"
                        >
                          <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-secondary/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                          <span className="relative z-10 text-primary font-medium group-hover:text-primary transition-colors duration-300 flex items-center whitespace-nowrap text-sm">
                            <Upload className="mr-2 h-3 w-3" />
                            Choose File
                          </span>
                        </button>

                        {/* Audio Preview - Center */}
                        {audioUrl && (
                          <button
                            onClick={togglePlayback}
                            className="relative overflow-hidden group px-3 py-2 rounded-md font-medium shadow-md hover:shadow-lg hover:scale-[1.02] transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 w-[100px]"
                          >
                            <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-secondary/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                            <span className="relative z-10 text-primary font-medium group-hover:text-primary transition-colors duration-300 flex items-center text-sm">
                              {isPlaying ? (
                                <>
                                  <Pause className="mr-2 h-3 w-3" />
                                  Pause
                                </>
                              ) : (
                                <>
                                  <Play className="mr-2 h-3 w-3" />
                                  Preview
                                </>
                              )}
                            </span>
                          </button>
                        )}

                        {/* Transcribe - Right */}
                        <button
                          onClick={handleTranscribe}
                          disabled={isTranscribing}
                          className="relative overflow-hidden group px-3 py-2 rounded-md font-medium shadow-md hover:shadow-lg hover:scale-[1.02] transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 w-[120px] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
                        >
                          <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-secondary/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                          <span className="relative z-10 text-primary font-medium group-hover:text-primary transition-colors duration-300 flex items-center text-sm">
                            {isTranscribing ? (
                              <>
                                <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                                Transcribing...
                              </>
                            ) : (
                              <>
                                <Mic className="mr-2 h-3 w-3" />
                                Transcribe
                              </>
                            )}
                          </span>
                        </button>
                      </div>

                      {/* Hidden Audio Element */}
                      {audioUrl && (
                        <audio
                          ref={audioRef}
                          src={audioUrl}
                          onEnded={handleAudioEnded}
                          className="hidden"
                        />
                      )}
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <div className="flex items-center justify-center">
                        <div className="w-12 h-12 rounded-full bg-muted/50 flex items-center justify-center">
                          <Upload className="h-6 w-6 text-muted-foreground" />
                        </div>
                      </div>
                      <div>
                        <p className="text-white font-medium mb-2">Drop your audio file here</p>
                        <p className="text-gray-400 text-sm mb-4">
                          or click to browse your files
                        </p>
                        <button
                          onClick={() => fileInputRef.current?.click()}
                          className="relative overflow-hidden group px-8 py-3 rounded-md font-medium shadow-md hover:shadow-lg hover:scale-[1.02] transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20"
                        >
                          <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-secondary/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                          <span className="relative z-10 text-primary font-medium group-hover:text-primary transition-colors duration-300">
                            Choose File
                          </span>
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                {/* Error Display */}
                {error && (
                  <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 flex items-center gap-2">
                    <AlertCircle className="h-4 w-4 text-red-400" />
                    <p className="text-red-400 text-sm">{error}</p>
                  </div>
                )}

                {/* Supported Formats */}
                <div className="mt-4 text-center">
                  <p className="text-gray-400 text-xs">
                    Supported formats: {SUPPORTED_FORMATS.join(', ')} • Max size: {MAX_FILE_SIZE / (1024 * 1024)}MB
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Transcription Status - Single Container to Prevent Layout Shift */}
          {!showResults && (
            <div className="mb-6 min-h-[120px]">
              <AnimatePresence mode="wait">
                {isTranscribing && (
                  <motion.div
                    key="progress"
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    transition={{ duration: 0.2, ease: "easeInOut" }}
                  >
                    <Card className="bg-card/50 backdrop-blur-sm border-border/50">
                      <CardContent className="pt-6">
                        <div className="space-y-4">
                          <div className="flex items-center gap-3">
                            <Loader2 className="h-5 w-5 animate-spin text-primary" />
                            <div>
                              <p className="text-white font-medium">Transcribing Your Audio</p>
                              <p className="text-gray-400 text-sm">{currentLoadingMessage}</p>
                            </div>
                          </div>
                          <Progress value={transcriptionProgress} className="h-2" />
                        </div>
                      </CardContent>
                    </Card>
                  </motion.div>
                )}

                {transcriptionResult && !showModal && showTranscriptionCard && (
                  <motion.div
                    key="success"
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    transition={{ duration: 0.2, ease: "easeInOut" }}
                  >
                    <Card className="bg-card/50 backdrop-blur-sm border-border/50">
                      <CardContent className="pt-4">
                        <div className="space-y-3">
                          {/* Success Header */}
                          <div className="flex items-center gap-3 mb-3">
                            <CheckCircle className="h-5 w-5 text-green-500" />
                            <div>
                              <p className="text-white font-medium">Transcription Complete!</p>
                              <p className="text-gray-400 text-sm">
                                {transcriptionResult.duration ? `${Math.round(transcriptionResult.duration)}s audio processed` : 'Audio processed successfully'}
                              </p>
                            </div>
                          </div>


                          {/* Action Buttons */}
                          <div className="flex gap-3 justify-center">
                            <button
                              onClick={() => setShowModal(true)}
                              className="relative overflow-hidden group px-8 py-3 rounded-md font-medium shadow-md hover:shadow-lg hover:scale-[1.02] transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20"
                            >
                              <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-secondary/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                              <span className="relative z-10 text-primary font-medium group-hover:text-primary transition-colors duration-300 flex items-center">
                                <Eye className="mr-2 h-4 w-4" />
                                View & Edit Transcription
                              </span>
                            </button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}

          {/* Transcription Modal */}
          <AnimatePresence>
            {showModal && transcriptionResult && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
                className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-6"
                onClick={() => setShowModal(false)}
              >
                <motion.div
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  transition={{ duration: 0.3 }}
                  className="bg-card/90 backdrop-blur-xl border border-border/50 rounded-2xl shadow-2xl max-w-6xl w-full max-h-[92vh] min-h-[600px] flex flex-col overflow-hidden mx-auto"
                  onClick={(e) => e.stopPropagation()}
                >
                  {/* Modal Header */}
                  <div className="px-6 py-4 border-b border-border/50">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center">
                          <FileText className="h-4 w-4 text-white" />
                        </div>
                        <div>
                          <h3 className="text-lg font-semibold text-white">Transcription Result</h3>
                          <p className="text-sm text-gray-400">
                            {transcriptionResult.duration ? `${Math.round(transcriptionResult.duration)}s audio` : ''}
                            {transcriptionResult.confidence && ` • ${Math.round(transcriptionResult.confidence * 100)}% confidence`}
                          </p>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setShowModal(false)
                          setShowUploadCard(true)
                        }}
                        className="h-8 w-8 p-0 text-blue-300 drop-shadow-[0_0_4px_rgba(147,197,253,0.6)] hover:bg-muted/50 hover:text-white hover:drop-shadow-[0_0_6px_rgba(255,255,255,0.6)]"
                        title="Close modal"
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>

                  {/* Modal Content */}
                  <div className="flex-1 overflow-y-auto p-6">
                    <div className="space-y-6">
                      {/* Transcription Text Area */}
                      <div>
                        <Textarea
                          value={editedTranscription}
                          onChange={(e) => setEditedTranscription(e.target.value)}
                          placeholder="Your transcribed text will appear here..."
                          className="min-h-[400px] bg-background/50 border-border text-white placeholder:text-gray-400 resize-none"
                        />
                      </div>

                      {/* Process Button */}
                      <div className="flex justify-center">
                        <button
                          onClick={handleProcessEntry}
                          disabled={!editedTranscription?.trim() || isProcessing}
                          className="relative overflow-hidden group px-8 py-3 rounded-md font-medium shadow-md hover:shadow-lg hover:scale-[1.02] transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
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

                      {/* Processed Results */}
                      <AnimatePresence>
                        {createdEntries && (
                          <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -20 }}
                            className="space-y-4"
                          >
                            <div className="grid gap-4">
                              {viewModes.map((mode, index) => {


                                const content = mode.mode === 'raw' ? createdEntries.raw.raw_text :
                                  mode.mode === 'enhanced' ? createdEntries.enhanced?.enhanced_text :
                                    createdEntries.structured?.structured_summary

                                return (
                                  <motion.div
                                    key={mode.mode}
                                    initial={{ opacity: 0, y: 20 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: index * 0.1 }}
                                  >
                                    <Card className="bg-card/30 backdrop-blur-sm border-border/30">
                                      <CardHeader className="pb-3">
                                        <div className="flex items-center gap-3">
                                          <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${mode.gradient} flex items-center justify-center`}>
                                            <mode.icon className="h-4 w-4 text-white" />
                                          </div>
                                          <div>
                                            <CardTitle className="text-base text-white">{mode.title}</CardTitle>
                                            <CardDescription className="text-xs text-gray-400">
                                              {mode.description}
                                            </CardDescription>
                                          </div>
                                        </div>
                                      </CardHeader>
                                      <CardContent>
                                        <p className="text-sm text-gray-200 leading-relaxed whitespace-pre-wrap">
                                          {content}
                                        </p>
                                      </CardContent>
                                    </Card>
                                  </motion.div>
                                )
                              })}
                            </div>

                            {/* Save Button */}
                            <div className="flex justify-center pt-4">
                              <Button
                                onClick={handleSaveEntries}
                                className="bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white border-0 px-8"
                              >
                                <Save className="mr-2 h-4 w-4" />
                                Add to Boo
                              </Button>
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  </div>
                </motion.div>
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
                    onClick={() => {
                      // Clear processed results and go back to raw transcription state
                      setCreatedEntries(null)
                      setProcessingMetadata(null)
                      setShowResults(false)
                      setShowModal(true)
                    }}
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
                    onClick={handleSaveEntries}
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
                    onClick={() => {
                      setSelectedFile(null)
                      setTranscriptionResult(null)
                      setEditedTranscription('')
                      setCreatedEntries(null)
                      setProcessingMetadata(null)
                      setShowModal(false)
                      setShowResults(false)
                      setShowTranscriptionCard(false)
                      setShowUploadCard(true)
                      setUseCustomDateTime(false)
                      setShowCalendar(false)
                      setEntryDateTime(new Date().toISOString().slice(0, 16))
                      if (audioUrl) {
                        URL.revokeObjectURL(audioUrl)
                        setAudioUrl(null)
                      }
                      if (fileInputRef.current) {
                        fileInputRef.current.value = ''
                      }
                    }}
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

                  {/* Backfill Entry Button */}
                  <motion.button
                    onClick={() => {
                      // Reset to current date/time when opening modal
                      const now = new Date()
                      const todayDate = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
                      const currentHour = now.getHours()
                      const currentMinute = now.getMinutes()

                      setBackfillDate(todayDate)
                      setBackfillHour(currentHour > 12 ? currentHour - 12 : currentHour === 0 ? 12 : currentHour)
                      setBackfillMinute(currentMinute)
                      setBackfillAmPm(currentHour >= 12 ? 'PM' : 'AM')

                      setTempDate(todayDate)
                      setTempHour(currentHour > 12 ? currentHour - 12 : currentHour === 0 ? 12 : currentHour)
                      setTempMinute(currentMinute)
                      setTempAmPm(currentHour >= 12 ? 'PM' : 'AM')

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
        </div>
      </div>

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
              <div className="flex items-center justify-between px-6 py-4 border-b border-border/50">
                <div className="flex items-center gap-3">
                  <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${overlayMode === 'raw' ? 'from-blue-500 to-blue-600' :
                    overlayMode === 'enhanced' ? 'from-purple-500 to-pink-500' :
                      'from-emerald-500 to-teal-500'
                    } flex items-center justify-center`}>
                    {overlayMode === 'raw' ? <FileText className="h-4 w-4 text-white" /> :
                      overlayMode === 'enhanced' ? <Pen className="h-4 w-4 text-white" /> :
                        <BookOpen className="h-4 w-4 text-white" />}
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-white">
                      Edit {overlayMode === 'raw' ? 'Raw Transcription' :
                        overlayMode === 'enhanced' ? 'Enhanced Style' :
                          'Structured Summary'}
                    </h3>
                    <p className="text-sm text-gray-400">Make changes to your content below</p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowOverlay(false)}
                  className="h-8 w-8 p-0 text-blue-300 drop-shadow-[0_0_4px_rgba(147,197,253,0.6)] hover:bg-muted/50 hover:text-white hover:drop-shadow-[0_0_6px_rgba(255,255,255,0.6)]"
                  title="Close modal"
                >
                  <X className="h-4 w-4" />
                </Button>
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
                    className="px-4 py-2 text-gray-400 hover:text-white transition-colors"
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
              setShowHourDropdown(false)
              setShowMinuteDropdown(false)
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
                    setShowHourDropdown(false)
                    setShowMinuteDropdown(false)
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
                            const todayDate = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
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
    </>
  )
}

export default VoiceUploadPage