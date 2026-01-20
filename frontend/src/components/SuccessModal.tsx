import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Button } from '@/components/ui/button'

interface SuccessModalProps {
  isOpen: boolean
  title: string
  message: string
  autoCloseMs?: number
  onClose: () => void
}

function SuccessModal({ isOpen, title, message, autoCloseMs = 3000, onClose }: SuccessModalProps) {
  const [countdown, setCountdown] = useState(Math.floor(autoCloseMs / 1000))

  useEffect(() => {
    if (!isOpen) return

    // Reset countdown when modal opens
    const seconds = Math.floor(autoCloseMs / 1000)
    setCountdown(seconds)
    
    // Set up the countdown interval
    const interval = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          return 0
        }
        return prev - 1
      })
    }, 1000)

    // Set up the auto-close timeout
    const timeout = setTimeout(() => {
      onClose()
    }, autoCloseMs)

    // Cleanup
    return () => {
      clearInterval(interval)
      clearTimeout(timeout)
    }
  }, [isOpen, autoCloseMs, onClose])

  return (
    <AnimatePresence mode="wait">
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[60] bg-black/80 backdrop-blur-md flex items-center justify-center p-4"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="w-full max-w-md bg-card border border-border rounded-lg shadow-2xl p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-center mb-6">
              <div className="flex items-center justify-center w-16 h-16 rounded-full bg-green-500/20 mx-auto mb-4">
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: "spring", stiffness: 200, delay: 0.1 }}
                  className="text-green-400 text-2xl font-bold"
                >
                  ✓
                </motion.div>
              </div>
              <h3 className="text-xl font-semibold text-white mb-2">{title}</h3>
              <p className="text-sm text-muted-foreground">Redirecting you to Boo...</p>
            </div>
            
            <p className="text-white mb-6">{message}</p>
            
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-green-400 animate-pulse" />
                <span className="text-xs text-gray-300">
                  Redirecting in <span className="text-green-400 font-semibold">{countdown}s</span>
                </span>
              </div>
              <Button
                onClick={onClose}
                size="sm"
                className="bg-green-500/10 border border-green-500/20 text-green-400 hover:bg-green-500/20 hover:text-green-300"
              >
                Continue Now
              </Button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export default SuccessModal