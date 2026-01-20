import { Button } from '@/components/ui/button'
import { Save, Trash2, Clock, MessageSquare, X } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { Badge } from '@/components/ui/badge'

interface SaveDiscardModalProps {
  isOpen: boolean
  onClose: () => void
  onSave: () => void
  onDiscard: () => void
  transcription: string
  duration: number
  messageCount: number
}

function SaveDiscardModal({
  isOpen,
  onClose,
  onSave,
  onDiscard,
  transcription,
  duration,
  messageCount
}: SaveDiscardModalProps) {
  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const parseConversation = () => {
    // Parse conversation transcript into messages
    const lines = transcription.split('\n')
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

  const messages = parseConversation()

  if (!isOpen) return null

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.3, ease: "easeInOut" }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4"
        onClick={onClose}
      >
        <motion.div
          initial={{ scale: 0.9, opacity: 0, y: 20 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          exit={{ scale: 0.85, opacity: 0, y: -20 }}
          transition={{ 
            type: "spring", 
            stiffness: 300, 
            damping: 30,
            exit: { duration: 0.25, ease: "easeIn" }
          }}
          className="bg-card border border-border rounded-lg shadow-2xl overflow-hidden max-w-4xl w-full max-h-[85vh] flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="px-6 py-4 border-b border-border">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-green-500 to-teal-600 flex items-center justify-center">
                  <Save className="h-4 w-4 text-white" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-white">Save Conversation?</h2>
                  <p className="text-muted-foreground mt-1">
                    Review your chat with Boo and decide if you'd like to save it.
                  </p>
                </div>
              </div>
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

            {/* Stats */}
            <div className="flex items-center gap-3 mt-4">
              <Badge className="bg-green-500/10 text-green-400 border-green-500/20 text-xs flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {formatDuration(duration)}
              </Badge>
              <Badge className="bg-blue-500/10 text-blue-400 border-blue-500/20 text-xs flex items-center gap-1">
                <MessageSquare className="h-3 w-3" />
                {messageCount} messages
              </Badge>
              <span className="text-muted-foreground text-xs ml-auto">
                {Math.round(transcription.length / 5)} words
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
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-border">
            <div className="flex items-center justify-between gap-4">
              <button
                onClick={onDiscard}
                className="relative overflow-hidden group px-6 py-3 rounded-lg font-medium shadow-lg hover:shadow-xl transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 gap-2"
              >
                <div className="absolute inset-0 bg-gradient-to-r from-red-500/10 to-red-600/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                <span className="relative z-10 flex items-center font-medium">
                  <Trash2 className="h-4 w-4" />
                  Discard Conversation
                </span>
              </button>
              <button
                onClick={onSave}
                className="relative overflow-hidden group px-6 py-3 rounded-lg font-medium shadow-lg hover:shadow-xl transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-green-500/10 border border-green-500/20 text-green-400 hover:bg-green-500/20 gap-2"
              >
                <div className="absolute inset-0 bg-gradient-to-r from-green-500/10 to-emerald-500/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                <span className="relative z-10 flex items-center font-medium">
                  <Save className="h-4 w-4" />
                  Save Conversation
                </span>
              </button>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}

export default SaveDiscardModal