import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence, useMotionValue, useTransform, PanInfo } from 'framer-motion'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Brain, Heart, ThumbsUp, ThumbsDown, RotateCcw, Loader2, Sparkles, Users, Target, AlertCircle, ChevronLeft, ChevronRight } from 'lucide-react'
import { api } from '@/lib/api'
import { useToast } from '@/components/ui/use-toast'

interface Memory {
  id: number
  content: string
  memory_type: string
  base_importance_score: number
  llm_importance_score?: number
  user_score_adjustment: number
  final_importance_score: number
  user_rated: number
  score_source: string
  effective_score_data?: any
  created_at: string
  last_accessed_at?: string
  access_count: number
}

function MemoriesPage() {
  // Separate state for swipe functionality (left card)
  const [unratedMemories, setUnratedMemories] = useState<Memory[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  
  // Separate state for collection browsing (right card)
  const [allMemories, setAllMemories] = useState<Memory[]>([])
  const [memoryPage, setMemoryPage] = useState(1)
  const [memoryTotalPages, setMemoryTotalPages] = useState(1)
  const [memoryTotal, setMemoryTotal] = useState(0)
  const [memoryFilter, setMemoryFilter] = useState<'all' | 'rated' | 'unrated'>('all')
  const memoryPageSize = 6 // Show 6 memories per page in collection
  
  // Currently selected memory (can be from either source)
  const [currentMemory, setCurrentMemory] = useState<Memory | null>(null)
  const [currentMemorySource, setCurrentMemorySource] = useState<'swipe' | 'collection'>('swipe')
  
  // UI state
  const [loading, setLoading] = useState(true)
  const [isRating, setIsRating] = useState(false)
  const [showConfirmation, setShowConfirmation] = useState(false)
  const [showSwipeConfirmation, setShowSwipeConfirmation] = useState(false)
  const [pendingSwipeAction, setPendingSwipeAction] = useState<{ memoryId: number, isRelevant: boolean } | null>(null)
  const [lastAction, setLastAction] = useState<{ type: 'relevant' | 'irrelevant', memoryId: number } | null>(null)
  const [stats, setStats] = useState<any>(null)
  
  const { toast } = useToast()

  // Helper function to ensure toast content is valid (same as other pages)
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

  // Track first swipes for each direction separately
  const [hasSwipedLeft, setHasSwipedLeft] = useState(false)
  const [hasSwipedRight, setHasSwipedRight] = useState(false)

  // Reset swipe confirmation state when component unmounts (user navigates away)
  useEffect(() => {
    return () => {
      // Reset both directions when navigating away
      setHasSwipedLeft(false)
      setHasSwipedRight(false)
    }
  }, [])

  // Motion values for drag with increased threshold
  const x = useMotionValue(0)
  const y = useMotionValue(0)
  const rotate = useTransform(x, [-300, 300], [-25, 25])
  
  // Swipe threshold - increased for less reactivity
  const SWIPE_THRESHOLD = 120

  useEffect(() => {
    // Load based on initial filter (default is 'all')
    if (memoryFilter === 'all' || memoryFilter === 'unrated') {
      loadUnratedMemories()
    } else {
      loadRatedMemories()
    }
    loadPaginatedMemories(1, memoryFilter)
    loadStats()
  }, [])

  const loadUnratedMemories = async () => {
    try {
      setLoading(true)
      const response = await api.getUnratedMemories(20) // For swipe functionality
      if (response.success && response.data) {
        setUnratedMemories(response.data)
        setCurrentIndex(0)
        // Set initial current memory from swipe queue
        if (response.data.length > 0 && !currentMemory) {
          setCurrentMemory(response.data[0])
          setCurrentMemorySource('swipe')
        }
      } else {
        safeToast({
          title: "Failed to load memories",
          description: "Please try again"
        })
      }
    } catch (error) {
      console.error('Failed to load memories:', error)
      safeToast({
        title: "Failed to load memories",
        description: "Please check your connection and try again"
      })
    } finally {
      setLoading(false)
    }
  }

  const loadPaginatedMemories = async (page: number = 1, filter: 'all' | 'rated' | 'unrated' = 'all') => {
    try {
      const response = await api.getPaginatedMemories(page, memoryPageSize, filter)
      if (response.success && response.data) {
        setAllMemories(response.data.memories)
        setMemoryTotalPages(response.data.totalPages)
        setMemoryTotal(response.data.total)
        setMemoryPage(response.data.page)
        setMemoryFilter(filter)
      }
    } catch (error) {
      console.error('Failed to load paginated memories:', error)
      safeToast({
        title: "Failed to load memory collection",
        description: "Please try again"
      })
    }
  }

  const loadRatedMemories = async () => {
    try {
      // Load rated memories for display in the swipe card (read-only)
      const response = await api.getPaginatedMemories(1, 20, 'rated')
      if (response.success && response.data) {
        setUnratedMemories(response.data.memories) // Use same state but these are rated
        setCurrentIndex(0)
        // Set initial current memory from rated memories
        if (response.data.memories.length > 0) {
          setCurrentMemory(response.data.memories[0])
          setCurrentMemorySource('swipe')
        }
      }
    } catch (error) {
      console.error('Failed to load rated memories:', error)
      safeToast({
        title: "Failed to load rated memories",
        description: "Please try again"
      })
    }
  }

  const loadStats = async () => {
    try {
      const response = await api.getMemoryStats()
      if (response.success && response.data) {
        setStats(response.data)
      }
    } catch (error) {
      console.error('Failed to load stats:', error)
    }
  }

  // Helper functions to get current display memory
  const getDisplayMemory = () => {
    if (currentMemorySource === 'collection' && currentMemory) {
      return currentMemory
    }
    return unratedMemories[currentIndex]
  }

  const canRate = () => {
    const memory = getDisplayMemory()
    return memory && memory.user_rated === 0
  }

  const getPreviousRating = () => {
    const memory = getDisplayMemory()
    if (memory && memory.user_rated === 1) {
      return memory.user_score_adjustment > 0 ? 'relevant' : 'irrelevant'
    }
    return null
  }

  // Handle memory selection from collection
  const handleMemorySelection = (memory: Memory) => {
    setCurrentMemory(memory)
    setCurrentMemorySource('collection')
  }

  const rateMemory = async (memoryId: number, isRelevant: boolean) => {
    if (isRating) return

    setIsRating(true)
    try {
      const adjustment = isRelevant ? 2 : -3 // Relevant: +2, Irrelevant: -3
      const response = await api.rateMemory(memoryId, adjustment)
      
      if (response.success) {
        setLastAction({
          type: isRelevant ? 'relevant' : 'irrelevant',
          memoryId
        })
        setShowConfirmation(true)
        
        if (currentMemorySource === 'swipe') {
          // Move to next memory in swipe queue after short delay
          setTimeout(() => {
            setCurrentIndex(prev => prev + 1)
            setShowConfirmation(false)
            // Update current memory to next in queue
            if (currentIndex + 1 < unratedMemories.length) {
              setCurrentMemory(unratedMemories[currentIndex + 1])
            }
          }, 1500)
        } else {
          // For collection selection, update the memory's status
          setTimeout(() => {
            setShowConfirmation(false)
            // Reload the current page to show updated status
            loadPaginatedMemories(memoryPage, memoryFilter)
          }, 1500)
        }

        // Reload stats
        loadStats()
      } else {
        safeToast({
          title: "Failed to rate memory",
          description: response.error || "Please try again"
        })
      }
    } catch (error) {
      console.error('Failed to rate memory:', error)
      safeToast({
        title: "Failed to rate memory",
        description: "Please check your connection and try again"
      })
    } finally {
      setIsRating(false)
    }
  }

  const handleDragEnd = (event: any, info: PanInfo) => {
    const { offset, velocity } = info
    
    // Determine swipe direction and threshold
    const swipeVelocityThreshold = 500

    if (Math.abs(offset.x) > SWIPE_THRESHOLD || Math.abs(velocity.x) > swipeVelocityThreshold) {
      const currentMemory = getDisplayMemory()
      if (currentMemory && canRate()) {
        const isRelevant = offset.x > 0
        
        // Show confirmation dialog on first swipe of each direction
        const needsConfirmation = isRelevant ? !hasSwipedRight : !hasSwipedLeft
        
        if (needsConfirmation) {
          setPendingSwipeAction({ memoryId: currentMemory.id, isRelevant })
          setShowSwipeConfirmation(true)
          x.set(0) // Reset position
          y.set(0)
          return
        }
        
        // Direct action for subsequent swipes
        rateMemory(currentMemory.id, isRelevant)
      }
    } else {
      // Snap back to center
      x.set(0)
      y.set(0)
    }
  }

  const handleConfirmSwipe = () => {
    if (pendingSwipeAction) {
      // Mark the appropriate direction as confirmed
      if (pendingSwipeAction.isRelevant) {
        setHasSwipedRight(true)
      } else {
        setHasSwipedLeft(true)
      }
      
      // Reset motion values before rating to ensure clean transition
      x.set(0)
      y.set(0)
      
      // Small delay to ensure position reset completes before rating animation
      setTimeout(() => {
        rateMemory(pendingSwipeAction.memoryId, pendingSwipeAction.isRelevant)
      }, 50)
      
      setPendingSwipeAction(null)
      setShowSwipeConfirmation(false)
    }
  }

  const handleCancelSwipe = () => {
    // Reset motion values when canceling
    x.set(0)
    y.set(0)
    
    setPendingSwipeAction(null)
    setShowSwipeConfirmation(false)
  }

  const handleButtonRate = (isRelevant: boolean) => {
    const currentMemory = getDisplayMemory()
    if (currentMemory && canRate()) {
      // Buttons don't require confirmation - direct action
      rateMemory(currentMemory.id, isRelevant)
    }
  }

  const getMemoryTypeIcon = (type: string) => {
    switch (type) {
      case 'factual':
        return <Brain className="w-4 h-4" />
      case 'preference':
        return <Heart className="w-4 h-4" />
      case 'relational':
        return <Users className="w-4 h-4" />
      case 'behavioral':
        return <Target className="w-4 h-4" />
      default:
        return <Sparkles className="w-4 h-4" />
    }
  }

  const getMemoryTypeColor = (type: string) => {
    switch (type) {
      case 'factual':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
      case 'preference':
        return 'bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-200'
      case 'relational':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      case 'behavioral':
        return 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200'
    }
  }

  const formatMemoryType = (type: string) => {
    return type.charAt(0).toUpperCase() + type.slice(1)
  }

  // Handle pagination navigation
  const handlePageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= memoryTotalPages) {
      loadPaginatedMemories(newPage, memoryFilter)
    }
  }

  // Handle filter change
  const handleFilterChange = (filter: 'all' | 'rated' | 'unrated') => {
    setMemoryFilter(filter)
    setMemoryPage(1) // Reset to first page
    loadPaginatedMemories(1, filter)
    
    // Also update the swipe cards based on filter
    if (filter === 'unrated') {
      // Load only unrated for swipe
      loadUnratedMemories()
    } else if (filter === 'rated') {
      // Load rated memories for review (read-only)
      loadRatedMemories()
    } else {
      // Load all unrated for swipe when 'all' is selected
      loadUnratedMemories()
    }
  }

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
          <p className="text-muted-foreground">Loading your memories...</p>
        </div>
      </div>
    )
  }

  if (unratedMemories.length === 0 && allMemories.length === 0) {
    return (
      <div className="h-screen flex flex-col p-4 md:p-6 overflow-hidden">
        <div className="max-w-6xl mx-auto w-full flex flex-col flex-1 items-center justify-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="text-center"
          >
            <Brain className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
            <h2 className="text-2xl font-bold text-white mb-2">
              {memoryFilter === 'rated' ? 'No Rated Memories' : 
               memoryFilter === 'unrated' ? 'No Unrated Memories' : 
               'No Memories Yet'}
            </h2>
            <p className="text-gray-400 mb-6">
              {memoryFilter === 'rated' ? 
                "You haven't rated any memories yet. Switch to 'Pending' to see available memories." :
               memoryFilter === 'unrated' ? 
                "All memories have been rated! Great job helping Boo understand what's important." :
                "Keep journaling and chatting with Boo to build your memory collection."}
            </p>
            <div className="flex gap-3 justify-center">
              <Button 
                onClick={() => handleFilterChange('all')} 
                variant="ghost"
                size="sm"
                className="relative overflow-hidden group transition-all duration-200 bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 hover:text-primary"
              >
                <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-secondary/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                <span className="relative z-10 flex items-center font-medium">
                  <Sparkles className="mr-2 h-4 w-4" />
                  Show All Memories
                </span>
              </Button>
              <Button 
                onClick={() => {
                  if (memoryFilter === 'all' || memoryFilter === 'unrated') {
                    loadUnratedMemories()
                  } else {
                    loadRatedMemories()
                  }
                  loadPaginatedMemories(1, memoryFilter)
                }} 
                variant="ghost"
                size="sm"
                className="relative overflow-hidden group transition-all duration-200 bg-green-500/10 border border-green-500/20 text-green-400 hover:bg-green-500/20 hover:text-green-300"
              >
                <div className="absolute inset-0 bg-gradient-to-r from-green-500/10 to-green-500/20 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                <span className="relative z-10 flex items-center font-medium">
                  <RotateCcw className="mr-2 h-4 w-4" />
                  Check Again
                </span>
              </Button>
            </div>
          </motion.div>
        </div>
      </div>
    )
  }

  const displayMemory = getDisplayMemory()
  const isComplete = currentMemorySource === 'swipe' && currentIndex >= unratedMemories.length

  return (
    <div className="max-w-7xl mx-auto p-8">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Card - Memory Review */}
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
                    <Brain className="h-4 w-4 text-white" />
                  </div>
                  <div className="min-w-0">
                    <CardTitle className="text-lg text-white">Memory Review</CardTitle>
                    <p className="text-gray-400 text-sm">
                      Rate memories to help Boo learn
                    </p>
                  </div>
                </div>
                
                {/* Progress indicator */}
                {stats && (
                  <div className="text-right">
                    <div className="text-sm text-gray-400">
                      {stats.unrated_memories} remaining
                    </div>
                    <div className="text-xs text-green-400">
                      {stats.rated_memories} reviewed
                    </div>
                  </div>
                )}
              </div>
            </CardHeader>
            
            <CardContent className="flex-1 flex flex-col items-center justify-center relative p-6">
              {/* Show completion message when all memories are reviewed */}
              {isComplete ? (
                <motion.div
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="text-center w-full"
                >
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ duration: 0.3, delay: 0.2 }}
                    className="bg-gradient-to-br from-green-500/10 to-emerald-500/10 rounded-full w-16 h-16 flex items-center justify-center mx-auto mb-4"
                  >
                    <ThumbsUp className="h-8 w-8 text-green-400" />
                  </motion.div>
                  <h2 className="text-xl font-bold text-white mb-2">All Done!</h2>
                  <p className="text-gray-400 mb-6 text-sm">
                    All memories reviewed. Great job helping Boo!
                  </p>
                  <Button 
                    onClick={loadUnratedMemories} 
                    variant="ghost"
                    size="sm"
                    className="relative overflow-hidden group transition-all duration-200 bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 hover:text-primary"
                  >
                    <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-secondary/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                    <span className="relative z-10 flex items-center font-medium">
                      <RotateCcw className="mr-2 h-4 w-4" />
                      Check for New Memories
                    </span>
                  </Button>
                </motion.div>
              ) : (
                <>
                  {/* Confirmation feedback */}
                  <AnimatePresence>
                    {showConfirmation && lastAction && (
                      <motion.div
                        initial={{ opacity: 0, y: -50, scale: 0.8 }}
                        animate={{ opacity: 1, y: -100, scale: 1 }}
                        exit={{ opacity: 0, y: -150, scale: 0.8 }}
                        className="absolute top-4 z-20 bg-card border border-border rounded-lg px-4 py-2 shadow-lg"
                      >
                        <div className="flex items-center gap-2">
                          {lastAction.type === 'relevant' ? (
                            <>
                              <ThumbsUp className="w-4 h-4 text-green-500" />
                              <span className="text-green-500 font-medium">Marked as Relevant</span>
                            </>
                          ) : (
                            <>
                              <ThumbsDown className="w-4 h-4 text-red-500" />
                              <span className="text-red-500 font-medium">Marked as Irrelevant</span>
                            </>
                          )}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>

                  {/* Single Card Display */}
                  {displayMemory && (
                <motion.div
                  className="relative w-full max-w-md h-80 mb-6"
                  initial={{ y: 20, opacity: 0, scale: 0.9 }}
                  animate={{ y: 0, opacity: 1, scale: 1 }}
                  whileHover={{ y: -8, scale: 1.02 }}
                  transition={{
                    type: "spring",
                    stiffness: 300,
                    damping: 24
                  }}
                >
                  <motion.div
                    key={displayMemory.id}
                    className="absolute inset-0"
                    style={{
                      x,
                      y,
                      rotate,
                      opacity: 1
                    }}
                    drag={canRate() ? "x" : undefined}
                    dragConstraints={{ left: 0, right: 0 }}
                    onDragEnd={canRate() ? handleDragEnd : undefined}
                    transition={{ duration: 0.2 }}
                  >
                    <Card className="w-full h-full cursor-pointer bg-card/50 backdrop-blur-sm border-border/50 hover:border-primary/30 shadow-xl hover:shadow-2xl transition-all duration-300 overflow-hidden group relative flex flex-col">
                      {/* Gradient overlay */}
                      <div className="absolute inset-0 bg-gradient-to-br from-primary/10 to-secondary/10 opacity-0 group-hover:opacity-5 transition-opacity duration-300" />
                      
                      {/* Shimmer effect */}
                      <div className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/10 to-transparent group-hover:translate-x-full transition-transform duration-700" />
                      <CardHeader className="pb-3 relative flex-shrink-0">
                        <div className="flex items-start justify-between">
                          <Badge 
                            variant="secondary" 
                            className={`flex items-center gap-1 ${getMemoryTypeColor(displayMemory.memory_type)}`}
                          >
                            {getMemoryTypeIcon(displayMemory.memory_type)}
                            {formatMemoryType(displayMemory.memory_type)}
                          </Badge>
                          <Badge 
                            variant="outline"
                            className="bg-primary/10 text-primary border-primary/20"
                          >
                            {displayMemory.final_importance_score.toFixed(1)}/10
                          </Badge>
                        </div>
                      </CardHeader>
                      
                      <CardContent className="flex-1 flex flex-col p-6">
                        {/* Centered Memory Text */}
                        <div className="flex-1 flex items-center justify-center px-2">
                          <div className="text-base leading-relaxed text-white text-center max-w-full">
                            {displayMemory.content.length > 150 
                              ? displayMemory.content.substring(0, 150) + "..."
                              : displayMemory.content
                            }
                          </div>
                        </div>
                        
                        {/* Instructions at bottom */}
                        <div className="text-center text-xs text-gray-400 border-t border-border/30 pt-3 mt-auto">
                          {canRate() ? (
                            <>
                              <p className="mb-2">Swipe or click to rate</p>
                              <div className="flex justify-center gap-6">
                                <span className="text-red-400">← Irrelevant</span>
                                <span className="text-green-400">Relevant →</span>
                              </div>
                            </>
                          ) : (
                            <p>This memory has already been rated</p>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  </motion.div>
                </motion.div>
              )}

                  {/* Action Buttons or Rating Status */}
                  <div className="relative w-full max-w-md">
                    {canRate() ? (
                  <div className="flex justify-between gap-4">
                    <Button
                      onClick={() => handleButtonRate(false)}
                      disabled={isRating}
                      className="flex-1 relative overflow-hidden group px-6 py-4 rounded-xl font-semibold shadow-lg hover:shadow-xl transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 hover:text-red-300"
                    >
                      <div className="absolute inset-0 bg-gradient-to-r from-red-500/10 to-red-500/20 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                      <span className="relative z-10 flex items-center">
                        {isRating ? (
                          <Loader2 className="w-5 h-5 animate-spin mr-2" />
                        ) : (
                          <ThumbsDown className="w-5 h-5 mr-2" />
                        )}
                        Irrelevant
                      </span>
                    </Button>
                    
                    <Button
                      onClick={() => handleButtonRate(true)}
                      disabled={isRating}
                      className="flex-1 relative overflow-hidden group px-6 py-4 rounded-xl font-semibold shadow-lg hover:shadow-xl transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-green-500/10 border border-green-500/20 text-green-400 hover:bg-green-500/20 hover:text-green-300"
                    >
                      <div className="absolute inset-0 bg-gradient-to-r from-green-500/10 to-green-500/20 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                      <span className="relative z-10 flex items-center">
                        {isRating ? (
                          <Loader2 className="w-5 h-5 animate-spin mr-2" />
                        ) : (
                          <ThumbsUp className="w-5 h-5 mr-2" />
                        )}
                        Relevant
                      </span>
                    </Button>
                  </div>
                ) : (
                  <div className="flex justify-center">
                    <Badge
                      variant="outline"
                      className={`px-6 py-3 text-base ${
                        getPreviousRating() === 'relevant'
                          ? 'bg-green-500/10 text-green-400 border-green-500/20'
                          : 'bg-red-500/10 text-red-400 border-red-500/20'
                      }`}
                    >
                      {getPreviousRating() === 'relevant' ? (
                        <><ThumbsUp className="w-5 h-5 mr-2" /> Previously marked as Relevant</>
                      ) : (
                        <><ThumbsDown className="w-5 h-5 mr-2" /> Previously marked as Irrelevant</>
                      )}
                    </Badge>
                    </div>
                  )}
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Right Card - Memory List */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
        >
          <Card className="bg-card/50 backdrop-blur-sm border-border/50 h-[700px] flex flex-col">
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-green-500 to-teal-600 flex items-center justify-center flex-shrink-0">
                  <Target className="h-4 w-4 text-white" />
                </div>
                <div className="min-w-0">
                  <CardTitle className="text-lg text-white">Memory Collection</CardTitle>
                  <p className="text-gray-400 text-sm">
                    Your stored memories & ratings
                  </p>
                </div>
              </div>
            </CardHeader>
            <CardContent className="flex-1 overflow-hidden p-4 flex flex-col">
              {/* Stats - Clickable Filters */}
              {stats && (
                <div className="flex gap-2 mb-4 flex-wrap">
                  <Badge 
                    variant="secondary" 
                    className={`cursor-pointer transition-all text-xs ${
                      memoryFilter === 'all' 
                        ? 'bg-blue-500/20 text-blue-300 border-blue-500/40 ring-1 ring-blue-500/50' 
                        : 'bg-blue-500/10 text-blue-400 border-blue-500/20 hover:bg-blue-500/15'
                    }`}
                    onClick={() => handleFilterChange('all')}
                  >
                    {stats.total_memories} Total
                  </Badge>
                  <Badge 
                    variant="secondary" 
                    className={`cursor-pointer transition-all text-xs ${
                      memoryFilter === 'unrated' 
                        ? 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40 ring-1 ring-yellow-500/50' 
                        : 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20 hover:bg-yellow-500/15'
                    }`}
                    onClick={() => handleFilterChange('unrated')}
                  >
                    {stats.unrated_memories} Pending
                  </Badge>
                  <Badge 
                    variant="secondary" 
                    className={`cursor-pointer transition-all text-xs ${
                      memoryFilter === 'rated' 
                        ? 'bg-green-500/20 text-green-300 border-green-500/40 ring-1 ring-green-500/50' 
                        : 'bg-green-500/10 text-green-400 border-green-500/20 hover:bg-green-500/15'
                    }`}
                    onClick={() => handleFilterChange('rated')}
                  >
                    {stats.rated_memories} Rated
                  </Badge>
                </div>
              )}

              {/* Memory List */}
              <div className="flex-1 overflow-y-auto pr-2 space-y-3 pl-1 pt-1">
                <AnimatePresence mode="wait">
                  {allMemories.map((memory, index) => {
                    const isSelected = currentMemory?.id === memory.id && currentMemorySource === 'collection'
                    return (
                      <motion.div
                        key={memory.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                        transition={{ delay: index * 0.05 }}
                      >
                        <Card
                          className={`cursor-pointer transition-all duration-200 hover:shadow-lg hover:bg-muted/30 group relative overflow-hidden ${
                            isSelected ? 'border-primary/50 bg-primary/5' : ''
                          }`}
                          onClick={() => handleMemorySelection(memory)}
                        >
                          {/* Shimmer effect */}
                          <div className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/10 to-transparent group-hover:translate-x-full transition-transform duration-700" />
                          
                          <CardContent className="p-3 relative">
                          <div className="flex items-start justify-between mb-2">
                            <Badge 
                              variant="secondary" 
                              className={`text-xs ${getMemoryTypeColor(memory.memory_type)}`}
                            >
                              {getMemoryTypeIcon(memory.memory_type)}
                              <span className="ml-1">{formatMemoryType(memory.memory_type)}</span>
                            </Badge>
                            <div className="flex items-center gap-2">
                              {memory.user_rated === 1 && (
                                <Badge className="bg-green-500/10 text-green-400 border-green-500/20 text-xs px-1 py-0">
                                  ✓
                                </Badge>
                              )}
                              <Badge 
                                variant="outline"
                                className="bg-primary/10 text-primary border-primary/20 text-xs"
                              >
                                {memory.final_importance_score.toFixed(1)}
                              </Badge>
                            </div>
                          </div>
                          <p className="text-sm text-gray-300 line-clamp-2 leading-relaxed">
                            {memory.content}
                          </p>
                          <div className="flex justify-between items-center mt-2 text-xs text-gray-400">
                            <span className="capitalize">{memory.score_source}</span>
                            <span>{memory.access_count} access{memory.access_count !== 1 ? 'es' : ''}</span>
                          </div>
                          </CardContent>
                        </Card>
                      </motion.div>
                    )
                  })}
                </AnimatePresence>
              </div>

              {/* Pagination */}
              {memoryTotalPages > 1 && (
                <div className="flex items-center justify-between pt-4 border-t border-border flex-shrink-0">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handlePageChange(memoryPage - 1)}
                    disabled={memoryPage === 1}
                    className="flex items-center gap-2 bg-card border border-border text-yellow-400 hover:bg-card/80 hover:text-yellow-300 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <ChevronLeft className="h-4 w-4" />
                    Previous
                  </Button>
                  
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <span>Page {memoryPage} of {memoryTotalPages}</span>
                    <span className="text-xs">({memoryTotal.toLocaleString()} total)</span>
                  </div>
                  
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handlePageChange(memoryPage + 1)}
                    disabled={memoryPage === memoryTotalPages}
                    className="flex items-center gap-2 bg-card border border-border text-yellow-400 hover:bg-card/80 hover:text-yellow-300 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Next
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* First swipe confirmation modal */}
      <AnimatePresence>
        {showSwipeConfirmation && pendingSwipeAction && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[60] bg-black/80 backdrop-blur-md flex items-center justify-center p-4"
            onClick={() => setShowSwipeConfirmation(false)}
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
                <div className={`flex items-center justify-center w-12 h-12 rounded-full ${
                  pendingSwipeAction.isRelevant 
                    ? "bg-green-500/20" 
                    : "bg-red-500/20"
                }`}>
                  <AlertCircle className={`h-6 w-6 ${
                    pendingSwipeAction.isRelevant 
                      ? "text-green-400" 
                      : "text-red-400"
                  }`} />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-white">Confirm Your Rating</h3>
                  <p className="text-sm text-muted-foreground">This helps Boo learn your preferences</p>
                </div>
              </div>
              
              <p className="text-white mb-6">
                Are you sure you want to mark this memory as{" "}
                <span className={`font-medium ${
                  pendingSwipeAction.isRelevant ? "text-green-400" : "text-red-400"
                }`}>
                  {pendingSwipeAction.isRelevant ? "Relevant" : "Irrelevant"}
                </span>?
              </p>
              
              <div className="flex gap-3">
                <Button
                  onClick={handleCancelSwipe}
                  className="flex-1 relative overflow-hidden group px-6 py-3 rounded-xl font-semibold shadow-lg hover:shadow-xl transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-gray-500/10 border border-gray-500/20 text-gray-400 hover:bg-gray-500/20 hover:text-gray-300"
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-gray-500/10 to-gray-500/20 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                  <span className="relative z-10">Cancel</span>
                </Button>
                <Button
                  onClick={handleConfirmSwipe}
                  className={`flex-1 relative overflow-hidden group px-6 py-3 rounded-xl font-semibold shadow-lg hover:shadow-xl transition-all duration-300 cursor-pointer inline-flex items-center justify-center ${
                    pendingSwipeAction.isRelevant 
                      ? "bg-green-500/10 border border-green-500/20 text-green-400 hover:bg-green-500/20 hover:text-green-300"
                      : "bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 hover:text-red-300"
                  }`}
                >
                  <div className={`absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 ${
                    pendingSwipeAction.isRelevant 
                      ? "bg-gradient-to-r from-green-500/10 to-green-500/20"
                      : "bg-gradient-to-r from-red-500/10 to-red-500/20"
                  }`} />
                  <span className="relative z-10">
                    {pendingSwipeAction.isRelevant ? "Mark Relevant" : "Mark Irrelevant"}
                  </span>
                </Button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default MemoriesPage