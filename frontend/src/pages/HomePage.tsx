import { motion, AnimatePresence } from 'framer-motion'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { FileText, Sparkles, Zap, Pen, BookOpen, Clock, FileAudio2, LogOut } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { api } from '@/lib/api'
import { format } from 'date-fns'

function HomePage() {
  const navigate = useNavigate()
  const [insights, setInsights] = useState<string[]>([])
  const [currentInsightIndex, setCurrentInsightIndex] = useState(0)
  const [entries, setEntries] = useState<any[]>([])
  const [currentTime, setCurrentTime] = useState(new Date())
  const [showPlusMenu, setShowPlusMenu] = useState(false)
  const [heroMessage, setHeroMessage] = useState('')
  const [userName, setUserName] = useState('')

  // Hero messages array
  const heroMessages = [
    "Go ahead. Be messy. Boo gets it. And it's not even connected to the damn internet.",
    "Say it how you feel it. Boo will sort it out later.",
    "Boo listens. Not because it has to—because it was built to.",
    "This is where chaos turns into memory. Silently. Locally. Without judgment.",
    "Talk to yourself. Boo just makes it look productive.",
    "Offline, but emotionally online. Welcome back to Boo.",
    "Whatever's in your head? Boo's already creating tags for it.",
    "Don't overthink it. Boo already did.",
    "Speak. Type. Mumble. Boo will make sense of it—eventually.",
    "No cloud. No crowd. Just you and your gloriously weird brain.",
    "Boo stores your spirals like they're precious. Because they are.",
    "You think out loud. Boo writes your autobiography in the background.",
    "Boo doesn't need the internet to understand you. Lucky Boo.",
    "Go off. Boo's heard worse. From you. Yesterday.",
    "This isn't just journaling. This is emotional version control.",
    "No rules. Just prompts, patterns, and poetic breakdowns.",
    "Built for thinkers. And feelers. And very tired people.",
    "Boo: where talking to yourself is suddenly very efficient.",
    "Let your thoughts sprawl. Boo runs local garbage collection.",
    "Say something weird. Boo thrives on weird."
  ]

  // Initialize random hero message
  useEffect(() => {
    const randomIndex = Math.floor(Math.random() * heroMessages.length)
    setHeroMessage(heroMessages[randomIndex])
  }, [])

  // Load user data for insights and user info
  useEffect(() => {
    loadUserData()
    loadUserInfo()
  }, [])


  // Update time
  useEffect(() => {
    const updateTime = () => {
      setCurrentTime(new Date())
    }

    updateTime()
    const interval = setInterval(updateTime, 60000) // Update every minute
    return () => clearInterval(interval)
  }, [])


  const loadUserData = async () => {
    try {
      const entriesResponse = await api.getEntries(1, 100)
      if (entriesResponse.success && entriesResponse.data) {
        const entriesData = (entriesResponse.data as any).data || entriesResponse.data
        if (entriesData.entries) {
          setEntries(entriesData.entries)
          generateInsights(entriesData.entries)
        }
      }
    } catch (error) {
      console.error('Failed to load user data:', error)
    }
  }

  const loadUserInfo = async () => {
    try {
      const response = await api.getSessionInfo()
      if (response.success && response.data?.user) {
        setUserName(response.data.user.display_name || response.data.user.username)
      }
    } catch (error) {
      console.error('Failed to load user info:', error)
    }
  }

  const generateInsights = (entries: any[]) => {
    const insightsList: string[] = []

    if (entries.length > 0) {
      // Total words
      const totalWords = entries.reduce((sum, entry) => sum + (entry.word_count || 0), 0)
      insightsList.push(`<span class="text-pink-400">${totalWords.toLocaleString()}</span> words captured in your journey`)

      // Longest entry
      const longestEntry = entries.reduce((max, entry) =>
        (entry.word_count || 0) > (max.word_count || 0) ? entry : max
      )
      if (longestEntry.word_count > 0) {
        insightsList.push(`Your longest reflection was <span class="text-pink-400">${longestEntry.word_count}</span> words`)
      }

      // Favorite day
      const dayFrequency: { [key: string]: number } = {}
      entries.forEach(entry => {
        const day = format(new Date(entry.timestamp), 'EEEE')
        dayFrequency[day] = (dayFrequency[day] || 0) + 1
      })
      const favoriteDay = Object.entries(dayFrequency)
        .sort((a, b) => b[1] - a[1])[0]
      if (favoriteDay) {
        insightsList.push(`<span class="text-pink-400">${favoriteDay[0]}s</span> are your most reflective days`)
      }

      // Time preference
      const hourFrequency: { [key: number]: number } = {}
      entries.forEach(entry => {
        const hour = new Date(entry.timestamp).getHours()
        hourFrequency[hour] = (hourFrequency[hour] || 0) + 1
      })
      const favoriteHour = Object.entries(hourFrequency)
        .sort((a, b) => b[1] - a[1])[0]
      if (favoriteHour) {
        const hour = parseInt(favoriteHour[0])
        const timeOfDay = hour < 12 ? 'morning' : hour < 17 ? 'afternoon' : 'evening'
        insightsList.push(`You're most creative in the <span class="text-pink-400">${timeOfDay}</span>`)
      }

      // Average entry length
      const avgWords = Math.round(totalWords / entries.length)
      insightsList.push(`You average <span class="text-pink-400">${avgWords}</span> words per entry`)

      // Mood insights
      const moodCounts: { [key: string]: number } = {}
      entries.forEach(entry => {
        entry.mood_tags?.forEach((mood: string) => {
          moodCounts[mood] = (moodCounts[mood] || 0) + 1
        })
      })
      if (Object.keys(moodCounts).length > 0) {
        const topMood = Object.entries(moodCounts)
          .sort((a, b) => b[1] - a[1])[0]
        if (topMood) {
          insightsList.push(`Your dominant emotion: <span class="text-pink-400">${topMood[0]}</span>`)
        }
      }
    } else {
      insightsList.push('Your story begins with the first entry')
      insightsList.push('Every word you write becomes part of your journey')
      insightsList.push('Reflection is the key to understanding yourself')
    }

    setInsights(insightsList)
  }

  // Cycle through insights
  useEffect(() => {
    if (insights.length <= 1) return

    const interval = setInterval(() => {
      setCurrentInsightIndex(prev => (prev + 1) % insights.length)
    }, 4000)

    return () => clearInterval(interval)
  }, [insights])

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

  // Logout function
  const handleLogout = async () => {
    try {
      await api.logoutUser()
      localStorage.removeItem('session_token')

      // Dispatch logout event to trigger AuthGuard update
      window.dispatchEvent(new CustomEvent('auth-logout'))
    } catch (error) {
      console.error('Logout failed:', error)
      // Even if API call fails, clear local session and redirect
      localStorage.removeItem('session_token')

      // Dispatch logout event to trigger AuthGuard update
      window.dispatchEvent(new CustomEvent('auth-logout'))
    }
  }

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.2,
        delayChildren: 0.1
      }
    }
  }

  const itemVariants = {
    hidden: { y: 20, opacity: 0 },
    visible: {
      y: 0,
      opacity: 1,
      transition: {
        type: "spring",
        stiffness: 300,
        damping: 24
      }
    }
  }

  const cardVariants = {
    hidden: { y: 20, opacity: 0, scale: 0.9 },
    visible: {
      y: 0,
      opacity: 1,
      scale: 1,
      transition: {
        type: "spring",
        stiffness: 300,
        damping: 24
      }
    },
    hover: {
      y: -8,
      scale: 1.02,
      transition: {
        type: "spring",
        stiffness: 400,
        damping: 10
      }
    }
  }

  return (
    <div className="h-screen flex flex-col p-4 md:p-8 overflow-hidden relative">
      {/* Ambient Background with Floating Orbs */}
      <div className="absolute inset-0 pointer-events-none z-0 overflow-hidden">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1.5, ease: "easeOut" }}
          className="relative w-full h-full"
        >
          {/* Floating gradient orbs - avoiding top right clock area */}
          <motion.div
            animate={{
              scale: [1, 1.3, 1],
              opacity: [0.2, 0.4, 0.2],
              rotate: [0, 180, 360]
            }}
            transition={{
              duration: 8,
              repeat: Infinity,
              ease: "easeInOut"
            }}
            className="absolute top-16 left-16 w-20 h-20 bg-gradient-to-r from-primary/30 to-blue-400/30 rounded-full blur-xl"
          />
          <motion.div
            animate={{
              scale: [1, 1.2, 1],
              opacity: [0.25, 0.45, 0.25],
              rotate: [0, -180, -360]
            }}
            transition={{
              duration: 10,
              repeat: Infinity,
              ease: "easeInOut",
              delay: 4
            }}
            className="absolute bottom-24 left-24 w-24 h-24 bg-gradient-to-tl from-cyan-400/25 to-indigo-400/25 rounded-full blur-xl"
          />
          <motion.div
            animate={{
              scale: [1, 1.4, 1],
              opacity: [0.2, 0.4, 0.2],
              rotate: [180, 0, -180]
            }}
            transition={{
              duration: 14,
              repeat: Infinity,
              ease: "easeInOut",
              delay: 1
            }}
            className="absolute top-1/2 left-1/3 w-18 h-18 bg-gradient-to-bl from-secondary/35 to-purple-400/35 rounded-full blur-xl"
          />
          <motion.div
            animate={{
              scale: [1, 1.6, 1],
              opacity: [0.15, 0.3, 0.15],
              rotate: [90, 270, 450]
            }}
            transition={{
              duration: 16,
              repeat: Infinity,
              ease: "easeInOut",
              delay: 6
            }}
            className="absolute bottom-1/4 left-1/4 w-22 h-22 bg-gradient-to-tr from-pink-400/30 to-cyan-400/30 rounded-full blur-xl"
          />
          <motion.div
            animate={{
              scale: [1, 1.1, 1],
              opacity: [0.3, 0.5, 0.3],
              rotate: [-90, 90, 270]
            }}
            transition={{
              duration: 6,
              repeat: Infinity,
              ease: "easeInOut",
              delay: 3
            }}
            className="absolute top-3/4 left-1/2 w-14 h-14 bg-gradient-to-r from-blue-400/35 to-primary/35 rounded-full blur-xl"
          />
        </motion.div>
      </div>
      <div className="max-w-6xl mx-auto w-full flex flex-col flex-1 justify-center -mt-8">
        <motion.div
          className="flex flex-col"
          variants={containerVariants}
          initial="hidden"
          animate="visible"
        >
          {/* Hero Section */}
          <motion.div className="text-center mb-16" variants={itemVariants}>
            <motion.h1
              className="text-5xl md:text-6xl font-bold mb-8 pb-3 bg-gradient-to-r from-white via-purple-400 to-blue-400 bg-clip-text text-transparent"
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.5 }}
            >
              {userName ? `Welcome back, ${userName}` : 'Welcome to Boo'}
            </motion.h1>
            <motion.p
              className="text-gray-300 text-lg md:text-xl max-w-4xl mx-auto leading-relaxed"
              variants={itemVariants}
            >
              {heroMessage || "Getting Boo ready to make sense of your thoughts..."}
            </motion.p>
          </motion.div>

          {/* Mode Cards */}
          <motion.div
            className="grid md:grid-cols-3 gap-8 mb-16"
            variants={containerVariants}
          >
            {viewModes.map((mode) => (
              <motion.div
                key={mode.mode}
                variants={cardVariants}
                whileHover="hover"
                whileTap={{ scale: 0.95 }}
              >
                <Card
                  className="cursor-pointer h-full bg-card/50 backdrop-blur-sm border-border/50 hover:border-primary/30 transition-all duration-300 overflow-hidden group relative"
                  onClick={() => navigate('/entries', { state: { previewMode: mode.mode } })}
                >
                  {/* Gradient overlay */}
                  <div className={`absolute inset-0 bg-gradient-to-br ${mode.gradient} opacity-0 group-hover:opacity-5 transition-opacity duration-300`} />

                  {/* Shimmer effect */}
                  <div className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/10 to-transparent group-hover:translate-x-full transition-transform duration-700" />

                  <CardHeader className="pb-4 relative">
                    <motion.div
                      className={`w-16 h-16 rounded-2xl bg-gradient-to-br ${mode.gradient} flex items-center justify-center mb-6 shadow-lg shadow-primary/20 relative`}
                      whileHover={{
                        scale: 1.1,
                        rotate: 5
                      }}
                      transition={{ type: "spring", stiffness: 300, damping: 10 }}
                    >
                      <mode.icon className="h-8 w-8 text-white" />

                      {/* Static ring - no pulse */}
                      <div className={`absolute inset-0 rounded-2xl bg-gradient-to-br ${mode.gradient} opacity-10`} />
                    </motion.div>

                    <CardTitle className="text-xl font-bold text-white group-hover:text-primary transition-colors duration-300">
                      {mode.title}
                    </CardTitle>
                    <CardDescription className="text-gray-300 text-base leading-relaxed">
                      {mode.description}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="pt-0">
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </motion.div>

          {/* Top Left Logout Button */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.8 }}
            className="absolute top-4 left-4 md:top-8 md:left-8 z-30"
          >
            <Button
              onClick={handleLogout}
              variant="ghost"
              size="sm"
              className="text-gray-300 hover:text-white hover:bg-red-500/10 transition-colors duration-200 gap-2"
            >
              <LogOut className="h-4 w-4" />
              Logout
            </Button>
          </motion.div>

          {/* Top Right Clock - NO CARD */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.8 }}
            className="absolute top-4 right-4 md:top-8 md:right-8 z-30 text-right"
          >
            {/* Time Display - Time and AM/PM on same line */}
            <div className="flex items-baseline justify-end gap-2 mb-3">
              <div className="text-3xl md:text-4xl font-bold bg-gradient-to-r from-white via-purple-400 to-pink-400 bg-clip-text text-transparent font-mono w-28 text-right">
                {format(currentTime, 'hh:mm')}
              </div>
              <motion.div
                className="text-lg font-medium text-purple-300 w-8 text-left"
                animate={{
                  opacity: [0.6, 1, 0.6]
                }}
                transition={{
                  duration: 2,
                  repeat: Infinity,
                  ease: "easeInOut"
                }}
              >
                {format(currentTime, 'a')}
              </motion.div>
            </div>

          </motion.div>

          {/* Rolling Insights */}
          <div className="absolute bottom-12 md:bottom-16 left-0 right-0 z-40">
            <div className="max-w-6xl mx-auto px-4 md:px-8">
              <div className="text-center">
                <AnimatePresence mode="wait">
                  {insights.length > 0 && (
                    <motion.p
                      key={currentInsightIndex}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      transition={{ duration: 0.3 }}
                      className="text-gray-300 text-lg max-w-2xl mx-auto leading-relaxed cursor-pointer select-none"
                      onClick={() => setCurrentInsightIndex(prev => (prev + 1) % insights.length)}
                      onMouseDown={(e) => {
                        const startX = e.clientX
                        const handleMouseMove = (moveEvent: MouseEvent) => {
                          const deltaX = moveEvent.clientX - startX
                          if (Math.abs(deltaX) > 50) {
                            if (deltaX > 0) {
                              setCurrentInsightIndex(prev => (prev + 1) % insights.length)
                            } else {
                              setCurrentInsightIndex(prev => prev === 0 ? insights.length - 1 : prev - 1)
                            }
                            document.removeEventListener('mousemove', handleMouseMove)
                            document.removeEventListener('mouseup', handleMouseUp)
                          }
                        }
                        const handleMouseUp = () => {
                          document.removeEventListener('mousemove', handleMouseMove)
                          document.removeEventListener('mouseup', handleMouseUp)
                        }
                        document.addEventListener('mousemove', handleMouseMove)
                        document.addEventListener('mouseup', handleMouseUp)
                      }}
                      title="Click or drag to navigate insights"
                      dangerouslySetInnerHTML={{ __html: insights[currentInsightIndex] }}
                    />
                  )}
                </AnimatePresence>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}

export default HomePage