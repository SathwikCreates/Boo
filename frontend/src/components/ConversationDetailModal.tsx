import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Download, X, Trash2, Clock, MessageSquare, Search, Loader2 } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { format } from 'date-fns'
import { Badge } from '@/components/ui/badge'

interface ConversationDetailModalProps {
  isOpen: boolean
  onClose: () => void
  conversation: {
    id: number
    timestamp: string
    duration: number
    transcription: string
    conversation_type: string
    message_count: number
    search_queries_used: string[]
    created_at: string
    updated_at?: string
  } | null
  onDelete: (id: number) => Promise<void>
}

function ConversationDetailModal({ isOpen, onClose, conversation, onDelete }: ConversationDetailModalProps) {
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [deleting, setDeleting] = useState(false)

  if (!isOpen || !conversation) return null

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp)
    return {
      date: format(date, 'MMMM d, yyyy'),
      time: format(date, 'h:mm a'),
      dayOfWeek: format(date, 'EEEE')
    }
  }

  const parseConversation = () => {
    // Parse conversation transcript into messages
    const lines = conversation.transcription.split('\n')
    const messages: { role: 'user' | 'assistant'; content: string; time: string }[] = []
    
    lines.forEach(line => {
      const match = line.match(/^\[(\d+:\d+\s[AP]M)\]\s(You|Boo):\s(.*)$/)
      if (match) {
        const [, time, speaker, content] = match
        messages.push({
          role: speaker === 'You' ? 'user' : 'assistant',
          content: content.trim(),
          time
        })
      }
    })
    
    return messages
  }

  const exportConversation = () => {
    const { dayOfWeek, date } = formatTimestamp(conversation.timestamp)
    const filename = `conversation-${dayOfWeek}-${date.replace(/[\s,]/g, '-')}.txt`
    
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

  const handleDelete = async () => {
    setDeleting(true)
    try {
      await onDelete(conversation.id)
      setShowDeleteDialog(false)
      onClose()
    } catch (error) {
      console.error('Failed to delete conversation:', error)
    } finally {
      setDeleting(false)
    }
  }

  const messages = parseConversation()
  const { date, time, dayOfWeek } = formatTimestamp(conversation.timestamp)

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.2 }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4"
        onClick={onClose}
      >
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.95, opacity: 0 }}
          transition={{ type: "spring", stiffness: 400, damping: 25, duration: 0.4 }}
          className="bg-card border border-border rounded-lg shadow-2xl overflow-hidden max-w-4xl w-full max-h-[85vh]"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="px-6 py-4 border-b border-border">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-white">
                  <span className="text-primary">{dayOfWeek}</span>
                  <span className="text-white">, </span>
                  <span className="text-muted-foreground">{date}</span>
                </h2>
                <p className="text-muted-foreground flex items-center gap-2 mt-1">
                  <Clock className="h-4 w-4" />
                  {time}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onClose}
                  className="h-8 w-8 p-0 text-blue-300 drop-shadow-[0_0_4px_rgba(147,197,253,0.6)] hover:bg-muted/50 hover:text-white hover:drop-shadow-[0_0_6px_rgba(255,255,255,0.6)]"
                  title="Close"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {/* Stats */}
            <div className="flex items-center gap-3 mt-4">
              <Badge className="bg-green-500/10 text-green-400 border-green-500/20 text-xs flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {formatDuration(conversation.duration)}
              </Badge>
              <Badge className="bg-blue-500/10 text-blue-400 border-blue-500/20 text-xs flex items-center gap-1">
                <MessageSquare className="h-3 w-3" />
                {conversation.message_count} messages
              </Badge>
              {conversation.search_queries_used.length > 0 && (
                <Badge className="bg-purple-500/10 text-purple-400 border-purple-500/20 text-xs flex items-center gap-1">
                  <Search className="h-3 w-3" />
                  {conversation.search_queries_used.length} searches
                </Badge>
              )}
              <span className="text-muted-foreground text-xs ml-auto">
                {Math.round(conversation.transcription.length / 5)} words
              </span>
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6" style={{ maxHeight: '60vh' }}>
            <div className="space-y-4">
              {messages.map((message, index) => (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.02 }}
                  className={`flex ${message.role === 'user' ? 'justify-start' : 'justify-end'}`}
                >
                  <div
                    className={`max-w-[70%] px-4 py-2 rounded-lg ${
                      message.role === 'user'
                        ? 'bg-gradient-to-br from-blue-500/20 to-cyan-500/20 border border-blue-500/30 text-white'
                        : 'bg-gradient-to-br from-purple-500/20 to-pink-500/20 border border-purple-500/30 text-white'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs font-medium ${
                        message.role === 'user' ? 'text-blue-300' : 'text-purple-300'
                      }`}>
                        {message.role === 'user' ? 'You' : 'Boo'}
                      </span>
                      <span className="text-xs text-gray-500">{message.time}</span>
                    </div>
                    <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                  </div>
                </motion.div>
              ))}
            </div>

            {/* Search queries used */}
            {conversation.search_queries_used.length > 0 && (
              <div className="mt-8 p-4 bg-muted/20 rounded-lg border border-border/50">
                <h4 className="text-sm font-medium text-gray-300 mb-2">Search queries used:</h4>
                <div className="flex flex-wrap gap-2">
                  {conversation.search_queries_used.map((query, index) => (
                    <Badge key={index} variant="outline" className="text-xs">
                      {query}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-border">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={exportConversation}
                  className="flex items-center gap-2 hover:bg-blue-500/20 hover:text-blue-400 hover:border-blue-500/50"
                >
                  <Download className="h-4 w-4" />
                  Export Conversation
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowDeleteDialog(true)}
                  disabled={deleting}
                  className="flex items-center gap-2 hover:bg-red-500/20 hover:text-red-400 hover:border-red-500/50"
                >
                  <Trash2 className="h-4 w-4" />
                  Delete Conversation
                </Button>
              </div>
              <div className="text-sm text-muted-foreground">
                <span>{Math.round(conversation.transcription.length / 5)} words</span>
                <span className="mx-2">•</span>
                <span>Created {date}</span>
              </div>
            </div>
          </div>
        </motion.div>

      </motion.div>

      {/* Delete Confirmation Modal */}
      <AnimatePresence>
        {showDeleteDialog && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[60] bg-black/80 backdrop-blur-md flex items-center justify-center p-4"
            onClick={() => setShowDeleteDialog(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              transition={{ type: "spring", stiffness: 400, damping: 25, duration: 0.3 }}
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
                <span className="font-medium text-primary">{dayOfWeek}, {date}</span>?
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
                  onClick={handleDelete}
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
    </AnimatePresence>
  )
}

export default ConversationDetailModal