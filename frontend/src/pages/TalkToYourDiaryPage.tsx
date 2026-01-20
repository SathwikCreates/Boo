import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Mic, MessageSquare, Trash2, Volume2, Download, ChevronLeft, ChevronRight, Clock, Loader2 } from 'lucide-react'
import { api } from '@/lib/api'
import { format } from 'date-fns'
import { motion, AnimatePresence } from 'framer-motion'
import { useToast } from '@/components/ui/use-toast'
import { useVoiceSettings } from '@/hooks/useVoiceSettings'

// Typewriter Text Component
interface TypewriterTextProps {
  text: string
  delay?: number
  className?: string
}

function TypewriterText({ text, delay = 0, className = '' }: TypewriterTextProps) {
  const [displayedText, setDisplayedText] = useState('')
  const [currentIndex, setCurrentIndex] = useState(0)
  const [startTyping, setStartTyping] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => {
      setStartTyping(true)
    }, delay * 1000)

    return () => clearTimeout(timer)
  }, [delay])

  useEffect(() => {
    if (!startTyping) return

    if (currentIndex < text.length) {
      const timer = setTimeout(() => {
        setDisplayedText(text.slice(0, currentIndex + 1))
        setCurrentIndex(currentIndex + 1)
      }, 80) // 80ms per character

      return () => clearTimeout(timer)
    }
  }, [currentIndex, text, startTyping])

  return (
    <motion.p 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: startTyping ? 1 : 0, y: 0 }}
      transition={{ duration: 0.3 }}
      className={className}
    >
      {displayedText}
      {currentIndex < text.length && (
        <motion.span
          animate={{ opacity: [1, 0] }}
          transition={{ duration: 0.8, repeat: Infinity }}
          className="text-primary"
        >
          |
        </motion.span>
      )}
    </motion.p>
  )
}
import ChatModal from '@/components/ChatModal'
import SaveDiscardModal from '@/components/SaveDiscardModal'
import ConversationDetailModal from '@/components/ConversationDetailModal'

// Types
interface Conversation {
  id: number
  timestamp: string
  duration: number
  transcription: string
  conversation_type: string
  message_count: number
  search_queries_used: string[]
  created_at: string
  updated_at?: string
  embedding?: string | null
  summary?: string | null
  key_topics?: string[] | null
}

function TalkToYourDiaryPage() {
  const { voiceEnabled, setVoiceEnabled } = useVoiceSettings()
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [isChatModalOpen, setIsChatModalOpen] = useState(false)
  const [isSaveModalOpen, setIsSaveModalOpen] = useState(false)
  const [currentTranscription, setCurrentTranscription] = useState('')
  const [conversationToSave, setConversationToSave] = useState<{
    transcription: string
    duration: number
    messageCount: number
    searchQueries: string[]
  } | null>(null)
  const [loading, setLoading] = useState(false)
  const [isPreparing, setIsPreparing] = useState(false)
  const [preparingMessageIndex, setPreparingMessageIndex] = useState(0)
  const [selectedConversation, setSelectedConversation] = useState<Conversation | null>(null)
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [conversationToDelete, setConversationToDelete] = useState<Conversation | null>(null)
  const [deleting, setDeleting] = useState(false)
  
  // Pagination state
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const pageSize = 6 // Show 6 conversations per page
  
  const { toast } = useToast()

  // Preparing messages for loading animation
  const preparingMessages = [
    "Getting ready to listen…",
    "Opening the pages of your story…",
    "Collecting my thoughts for you…",
    "Tuning in to your frequency…",
    "Clearing a space for our conversation…",
    "Setting the stage for our chat…",
    "Taking a deep (digital) breath…",
    "Finding the right words…",
    "Preparing a comfortable silence…",
    "Letting ideas settle before we begin…",
    "Adjusting to your wavelength…",
    "Almost ready to begin…"
  ]

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

  // Load conversations on mount
  useEffect(() => {
    loadConversations()
  }, [])

  // Rotate preparing messages while loading
  useEffect(() => {
    if (!isPreparing) return

    const interval = setInterval(() => {
      setPreparingMessageIndex((prev) => (prev + 1) % preparingMessages.length)
    }, 2000) // Change message every 2 seconds

    return () => clearInterval(interval)
  }, [isPreparing, preparingMessages.length])

  const loadConversations = async () => {
    setLoading(true)
    try {
      const response = await api.getConversations()
      console.log('API Response:', response) // Debug log
      
      if (response.success && response.data) {
        console.log('Response data:', response.data) // Debug log
        
        // Handle nested response structure from SuccessResponse
        const conversationsData = response.data.data || response.data
        
        if (conversationsData && conversationsData.conversations) {
          console.log('Conversations found:', conversationsData.conversations.length) // Debug log
          setConversations(conversationsData.conversations)
          // Calculate total pages
          const total = conversationsData.total || conversationsData.conversations.length
          setTotalPages(Math.ceil(total / pageSize))
        } else {
          console.log('No conversations field in response, conversationsData:', conversationsData) // Debug log
          setConversations([])
          setTotalPages(1)
        }
      } else {
        console.log('Response not successful or no data') // Debug log
        // No conversations yet or empty response
        setConversations([])
        setTotalPages(1)
      }
    } catch (error) {
      console.error('Failed to load conversations:', error)
      setConversations([])
      safeToast({
        title: 'Failed to load conversations',
        description: 'Please check your connection and try again'
      })
    } finally {
      setLoading(false)
    }
  }

  const handleStartChat = async () => {
    setIsPreparing(true)
    setPreparingMessageIndex(0)
    
    try {
      // Wait for model to be FULLY ready
      await api.preheatDiaryChat()
      
      // Only open modal after preheat succeeds
      setIsChatModalOpen(true)
    } catch (error) {
      console.error('Failed to preheat Boo:', error)
      safeToast({
        title: "Failed to initialize Boo",
        description: "Please try again",
        variant: "destructive"
      })
    } finally {
      setIsPreparing(false)
    }
  }

  const handleChatEnd = (transcription: string, duration: number, messageCount: number, searchQueries: string[]) => {
    setCurrentTranscription(transcription)
    setConversationToSave({
      transcription,
      duration,
      messageCount,
      searchQueries
    })
    setIsChatModalOpen(false)
    setIsSaveModalOpen(true)
  }

  const handleChatClose = async (transcription: string, duration: number, messageCount: number, searchQueries: string[]) => {
    // Store conversation data for the save modal
    setCurrentTranscription(transcription)
    setConversationToSave({
      transcription,
      duration,
      messageCount,
      searchQueries
    })
    
    // Close ChatModal first
    setIsChatModalOpen(false)
    
    // Wait for ChatModal exit animation to complete (300ms) then show SaveDiscardModal
    setTimeout(() => {
      setIsSaveModalOpen(true)
    }, 300)
  }

  const handleSaveConversation = async () => {
    if (!conversationToSave) return

    try {
      await api.createConversation({
        transcription: conversationToSave.transcription,
        conversation_type: 'chat',
        duration: conversationToSave.duration,
        message_count: conversationToSave.messageCount,
        search_queries_used: conversationToSave.searchQueries
      })
      safeToast({
        title: 'Conversation saved',
        description: 'Your chat with Boo has been saved successfully'
      })
      loadConversations()
      setIsSaveModalOpen(false)
      setConversationToSave(null)
    } catch (error) {
      console.error('Failed to save conversation:', error)
      safeToast({
        title: 'Failed to save conversation',
        description: 'Please try again'
      })
    }
  }

  const handleDiscardConversation = () => {
    setIsSaveModalOpen(false)
    setConversationToSave(null)
    setCurrentTranscription('')
  }

  const handleDeleteConversation = async (id: number) => {
    setDeleting(true)
    try {
      await api.deleteConversation(id)
      safeToast({
        title: 'Conversation deleted',
        description: 'The conversation has been removed successfully'
      })
      loadConversations()
    } catch (error) {
      console.error('Failed to delete conversation:', error)
      safeToast({
        title: 'Failed to delete conversation',
        description: 'Please try again'
      })
    } finally {
      setDeleting(false)
      setShowDeleteDialog(false)
      setConversationToDelete(null)
    }
  }

  const confirmDelete = (conversation: Conversation, e: React.MouseEvent) => {
    e.stopPropagation()
    setConversationToDelete(conversation)
    setShowDeleteDialog(true)
  }

  const openConversationDetail = (conversation: Conversation) => {
    setSelectedConversation(conversation)
    setIsDetailModalOpen(true)
  }

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const getConversationPreview = (transcription: string) => {
    // Extract first few messages for preview
    const lines = transcription.split('\n')
    const messages = lines.filter(line => line.match(/^\[.*\]\s(You|Boo):/))
    const preview = messages.slice(0, 2).map(msg => {
      const match = msg.match(/^\[.*\]\s(You|Boo):\s(.*)$/)
      if (match) {
        const [, speaker, content] = match
        return `${speaker}: ${content}`
      }
      return msg
    }).join(' → ')
    
    return preview.length > 120 ? preview.substring(0, 120) + '...' : preview
  }

  const exportConversation = (conversation: Conversation, e: React.MouseEvent) => {
    e.stopPropagation()
    const date = new Date(conversation.timestamp)
    const dateStr = format(date, 'yyyy-MM-dd')
    const filename = `conversation-${dateStr}.txt`
    
    const blob = new Blob([conversation.transcription], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  // Get paginated conversations
  const getPaginatedConversations = () => {
    const startIndex = (currentPage - 1) * pageSize
    const endIndex = startIndex + pageSize
    return conversations.slice(startIndex, endIndex)
  }

  return (
    <div className="max-w-7xl mx-auto p-8">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Card - Talk to Boo */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          <Card className="bg-card/50 backdrop-blur-sm border-border/50 h-[700px] flex flex-col">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center flex-shrink-0">
                    <MessageSquare className="h-4 w-4 text-white" />
                  </div>
                  <div className="min-w-0">
                    <CardTitle className="text-lg text-white">Talk to Boo</CardTitle>
                  </div>
                </div>
                
                {/* Voice Toggle in Header */}
                <motion.div 
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.3 }}
                  className="flex items-center gap-3 mt-1"
                >
                  <Label htmlFor="voice-toggle" className="text-sm font-medium text-gray-300">
                    Voice
                  </Label>
                  <Switch
                    id="voice-toggle"
                    checked={voiceEnabled}
                    onCheckedChange={setVoiceEnabled}
                  />
                  <Volume2 className={`h-4 w-4 ${voiceEnabled ? 'text-primary' : 'text-muted-foreground'}`} />
                </motion.div>
              </div>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col items-center justify-center relative overflow-hidden">
              {/* Background decorative elements */}
              <div className="absolute inset-4 opacity-20">
                <motion.div
                  animate={{ 
                    x: [0, 60, 0],
                    y: [0, -30, 0]
                  }}
                  transition={{ 
                    duration: 20, 
                    repeat: Infinity, 
                    ease: "linear" 
                  }}
                  className="absolute top-10 left-10 w-4 h-4 bg-primary/30 rounded-full blur-sm"
                />
                <motion.div
                  animate={{ 
                    x: [0, -40, 0],
                    y: [0, 30, 0]
                  }}
                  transition={{ 
                    duration: 15, 
                    repeat: Infinity, 
                    ease: "linear" 
                  }}
                  className="absolute top-32 right-16 w-2 h-2 bg-secondary/40 rounded-full blur-sm"
                />
                <motion.div
                  animate={{ 
                    x: [0, 30, 0],
                    y: [0, -20, 0]
                  }}
                  transition={{ 
                    duration: 25, 
                    repeat: Infinity, 
                    ease: "linear" 
                  }}
                  className="absolute bottom-20 left-20 w-3 h-3 bg-primary/20 rounded-full blur-sm"
                />
              </div>

              <div className="flex flex-col items-center gap-6 -translate-y-8">
                {/* Animated Boo Icon */}
                <motion.div
                  initial={{ scale: 0.8, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ duration: 0.5, delay: 0.2 }}
                  className="relative cursor-pointer"
                  onClick={handleStartChat}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                >
                  <motion.div
                    animate={{ 
                      scale: [1, 1.05, 1]
                    }}
                    transition={{ 
                      duration: 3, 
                      repeat: Infinity, 
                      ease: "easeInOut" 
                    }}
                    className="w-20 h-20 rounded-full bg-gradient-to-br from-primary/20 to-secondary/20 flex items-center justify-center border border-primary/30"
                  >
                    <Mic className="h-8 w-8 text-primary" />
                  </motion.div>
                  {/* Subtle breathing glow effect */}
                  <motion.div
                    animate={{ 
                      opacity: [0.1, 0.3, 0.1],
                      scale: [1, 1.1, 1]
                    }}
                    transition={{ 
                      duration: 4, 
                      repeat: Infinity,
                      ease: "easeInOut"
                    }}
                    className="absolute inset-0 rounded-full bg-primary/20 blur-lg"
                  />
                </motion.div>
                
                <TypewriterText 
                  text="A quiet space... for your loud thoughts"
                  delay={0.4}
                  className="text-gray-400 text-center max-w-sm"
                />
              </div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.8 }}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                <button
                  onClick={handleStartChat}
                  disabled={isPreparing}
                  className="relative overflow-hidden group px-8 py-3 rounded-lg font-medium shadow-lg hover:shadow-xl transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 gap-3 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-secondary/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                  <span className="relative z-10 flex items-center font-medium">
                    {isPreparing ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        Preparing Boo...
                      </>
                    ) : (
                      'Start Conversation'
                    )}
                  </span>
                </button>
              </motion.div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Right Card - Saved Conversations */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
        >
          <Card className="bg-card/50 backdrop-blur-sm border-border/50 h-[700px] flex flex-col">
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-green-500 to-teal-600 flex items-center justify-center flex-shrink-0">
                  <MessageSquare className="h-4 w-4 text-white" />
                </div>
                <div className="min-w-0">
                  <CardTitle className="text-lg text-white">Conversation History</CardTitle>
                  <p className="text-gray-400 text-sm">
                    Your saved chats with Boo
                  </p>
                </div>
              </div>
            </CardHeader>
            <CardContent className="flex-1 overflow-hidden p-4 flex flex-col">
              {loading ? (
                <div className="flex items-center justify-center h-full">
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                    className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full"
                  />
                </div>
              ) : conversations.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-center space-y-4">
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ type: "spring", delay: 0.2 }}
                    className="w-16 h-16 rounded-full bg-muted/20 flex items-center justify-center"
                  >
                    <MessageSquare className="h-8 w-8 text-muted-foreground" />
                  </motion.div>
                  <div>
                    <p className="text-gray-400 font-medium">No conversations yet</p>
                    <p className="text-gray-500 text-sm mt-1">
                      Start your first chat with Boo to see it here
                    </p>
                  </div>
                </div>
              ) : (
                <>
                  <div className="flex-1 overflow-y-auto pr-2 space-y-3 pl-1 pt-1">
                    <AnimatePresence mode="wait">
                      {getPaginatedConversations().map((conv, index) => (
                        <motion.div
                          key={conv.id}
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -10 }}
                          transition={{ delay: index * 0.05 }}
                        >
                          <Card 
                            className="cursor-pointer transition-all duration-200 hover:shadow-lg hover:bg-muted/30 group relative overflow-hidden"
                            onClick={() => {
                              openConversationDetail(conv)
                            }}
                          >
                            {/* Shimmer effect */}
                            <div className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/10 to-transparent group-hover:translate-x-full transition-transform duration-700" />
                            
                            <CardContent className="p-3 relative">
                              <div className="flex items-start justify-between mb-2">
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2 mb-1">
                                    <span className="text-sm font-semibold text-white">
                                      <span className="text-primary">{format(new Date(conv.timestamp), 'EEEE')}</span>
                                      <span className="text-white">, </span>
                                      <span className="text-muted-foreground">{format(new Date(conv.timestamp), 'MMMM d, yyyy')}</span>
                                    </span>
                                  </div>
                                  <div className="flex items-center gap-2 mb-1 text-muted-foreground">
                                    <Clock className="h-3 w-3" />
                                    <span className="text-xs">{format(new Date(conv.timestamp), 'h:mm a')}</span>
                                  </div>
                                  <p className="text-sm text-white leading-relaxed line-clamp-2">
                                    {getConversationPreview(conv.transcription)}
                                  </p>
                                </div>
                                <div className="flex items-center gap-1 ml-3 opacity-0 group-hover:opacity-100 transition-opacity">
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={(e) => exportConversation(conv, e)}
                                    className="h-8 w-8 p-0 text-blue-300 drop-shadow-[0_0_4px_rgba(147,197,253,0.6)] hover:bg-blue-500/20 hover:text-blue-400 hover:drop-shadow-[0_0_6px_rgba(96,165,250,0.8)]"
                                    title="Export conversation"
                                  >
                                    <Download className="h-3.5 w-3.5" />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={(e) => confirmDelete(conv, e)}
                                    className="h-8 w-8 p-0 text-blue-300 drop-shadow-[0_0_4px_rgba(147,197,253,0.6)] hover:bg-red-500/20 hover:text-red-400 hover:drop-shadow-[0_0_6px_rgba(248,113,113,0.8)]"
                                    title="Delete conversation"
                                  >
                                    <Trash2 className="h-3.5 w-3.5" />
                                  </Button>
                                </div>
                              </div>
                              
                              <div className="flex items-center justify-between mt-2">
                                <div className="flex items-center gap-2">
                                  <Badge className="bg-green-500/10 text-green-400 border-green-500/20 text-xs">
                                    {formatDuration(conv.duration)}
                                  </Badge>
                                  <Badge className="bg-blue-500/10 text-blue-400 border-blue-500/20 text-xs">
                                    {conv.message_count} messages
                                  </Badge>
                                  {conv.search_queries_used.length > 0 && (
                                    <Badge className="bg-purple-500/10 text-purple-400 border-purple-500/20 text-xs">
                                      {conv.search_queries_used.length} searches
                                    </Badge>
                                  )}
                                  {/* Indexing status badge - same style as ViewEntriesPage */}
                                  {(() => {
                                    // Check if embedding is a valid JSON array with content
                                    if (conv.embedding && conv.embedding !== null && conv.embedding.trim() !== '') {
                                      try {
                                        const embeddingArray = JSON.parse(conv.embedding)
                                        if (Array.isArray(embeddingArray) && embeddingArray.length > 0) {
                                          return (
                                            <Badge className="bg-cyan-500/10 text-cyan-400 border-cyan-500/20 text-xs">
                                              Indexed
                                            </Badge>
                                          )
                                        }
                                      } catch (error) {
                                        // Invalid JSON, treat as not indexed
                                      }
                                    }
                                    // No valid embedding found
                                    return (
                                      <Badge className="bg-orange-500/10 text-orange-400 border-orange-500/20 text-xs">
                                        No Embeddings
                                      </Badge>
                                    )
                                  })()}
                                </div>
                                <span className="text-muted-foreground text-xs">
                                  {Math.round(conv.transcription.length / 5)} words
                                </span>
                              </div>
                            </CardContent>
                          </Card>
                        </motion.div>
                      ))}
                    </AnimatePresence>
                  </div>

                  {/* Pagination */}
                  {totalPages > 1 && (
                    <div className="flex items-center justify-between pt-4 border-t border-border flex-shrink-0">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                        disabled={currentPage === 1}
                        className="flex items-center gap-2 bg-card border border-border text-yellow-400 hover:bg-card/80 hover:text-yellow-300 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <ChevronLeft className="h-4 w-4" />
                        Previous
                      </Button>
                      
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <span>Page {currentPage} of {totalPages}</span>
                        <span className="text-xs">({conversations.length} total)</span>
                      </div>
                      
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                        disabled={currentPage === totalPages}
                        className="flex items-center gap-2 bg-card border border-border text-yellow-400 hover:bg-card/80 hover:text-yellow-300 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        Next
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* Chat Modal */}
      <ChatModal
        isOpen={isChatModalOpen}
        onClose={handleChatClose}
        onEndChat={handleChatEnd}
      />

      {/* Save/Discard Modal */}
      <SaveDiscardModal
        isOpen={isSaveModalOpen}
        onClose={() => setIsSaveModalOpen(false)}
        onSave={handleSaveConversation}
        onDiscard={handleDiscardConversation}
        transcription={conversationToSave?.transcription || ''}
        duration={conversationToSave?.duration || 0}
        messageCount={conversationToSave?.messageCount || 0}
      />

      {/* Conversation Detail Modal */}
      <ConversationDetailModal
        isOpen={isDetailModalOpen}
        onClose={() => {
          setIsDetailModalOpen(false)
          setSelectedConversation(null)
        }}
        conversation={selectedConversation}
        onDelete={async (id) => {
          await handleDeleteConversation(id)
          setIsDetailModalOpen(false)
          setSelectedConversation(null)
        }}
      />

      {/* Delete Confirmation Modal */}
      <AnimatePresence>
        {showDeleteDialog && conversationToDelete && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[60] bg-black/80 backdrop-blur-md flex items-center justify-center p-4"
            onClick={() => setShowDeleteDialog(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              transition={{ type: "spring", stiffness: 300, damping: 30 }}
              className="w-full max-w-md bg-card border border-border rounded-lg shadow-2xl p-6"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center gap-3 mb-4">
                <div className="flex items-center justify-center w-12 h-12 bg-red-500/20 rounded-full">
                  <Trash2 className="h-6 w-6 text-red-400" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-white">Delete Conversation</h3>
                  <p className="text-sm text-muted-foreground">This action cannot be undone</p>
                </div>
              </div>
              
              <p className="text-white mb-6">
                Are you sure you want to delete this conversation from{' '}
                <span className="font-medium text-primary">
                  {format(new Date(conversationToDelete.timestamp), 'EEEE, MMMM d, yyyy')}
                </span>?
              </p>
              
              <div className="flex justify-end gap-3">
                <Button
                  variant="ghost"
                  onClick={() => setShowDeleteDialog(false)}
                  className="text-white hover:bg-muted/50"
                >
                  Cancel
                </Button>
                <Button
                  onClick={() => handleDeleteConversation(conversationToDelete.id)}
                  disabled={deleting}
                  className="bg-red-600 text-white hover:bg-red-700 border-red-600 hover:border-red-700"
                >
                  {deleting ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                      Deleting...
                    </>
                  ) : (
                    <>
                      <Trash2 className="h-4 w-4 mr-2" />
                      Delete Conversation
                    </>
                  )}
                </Button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Loading Overlay for Boo Preparation */}
      <AnimatePresence>
        {isPreparing && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="text-center"
            >
              <Loader2 className="h-12 w-12 animate-spin text-primary mx-auto mb-6" />
              <motion.h2
                key={preparingMessageIndex}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="text-2xl font-semibold text-white max-w-md mx-auto"
              >
                {preparingMessages[preparingMessageIndex]}
              </motion.h2>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default TalkToYourDiaryPage