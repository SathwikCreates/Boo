import { useState, useEffect, useMemo } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { format } from 'date-fns'
import SignupModal from '@/components/SignupModal'
import LoginModal from '@/components/LoginModal'
import SuccessModal from '@/components/SuccessModal'

function LandingPage() {
  const navigate = useNavigate()
  const [showSignupModal, setShowSignupModal] = useState(false)
  const [showSigninModal, setShowSigninModal] = useState(false)
  const [showSuccessModal, setShowSuccessModal] = useState(false)
  const [successData, setSuccessData] = useState({ title: '', message: '' })
  const [currentTime, setCurrentTime] = useState(new Date())
  const [timeOfDay, setTimeOfDay] = useState<'morning' | 'day' | 'evening' | 'night'>('day')
  const [currentSnark, setCurrentSnark] = useState('')
  const [displayedSnark, setDisplayedSnark] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  
  // Generate fixed star positions once
  const stars = useMemo(() => {
    const staticStars = Array.from({ length: 30 }, (_, i) => ({
      id: `static-${i}`,
      left: Math.random() * 100,
      top: Math.random() * 100,
      size: Math.random() * 2,
      opacity: Math.random() * 0.6 + 0.4,
    }))
    
    const shimmerStars = Array.from({ length: 20 }, (_, i) => ({
      id: `shimmer-${i}`,
      left: Math.random() * 100,
      top: Math.random() * 100,
      duration: Math.random() * 6 + 6,
      delay: Math.random() * 12,
    }))
    
    return { staticStars, shimmerStars }
  }, []) // Empty dependency array means these positions never change

  // Time-based snarky comments
  const snarkyComments = {
    0: ["Midnight. Still here. Still overthinking. Still fabulous.", "12 AM: I am both the problem and the insomniac solution.", "It's midnight and I've never felt more creative or useless.", "12 AM: fueled by delusion and glowing screens."],
    1: ["It's 1 AM. Perfect time to replay arguments in my head like a greatest hits album.", "1 AM: where \"just one more episode\" becomes five.", "1 AM and I've suddenly decided to rebrand my whole personality.", "1 AM: brain is loud, world is quiet, regrets are booing."],
    2: ["2 AM. Overthinking? Check. Hydrated? No.", "2 AM is just diet sadness with worse lighting.", "It's 2 AM. I've solved zero problems and invented three new ones.", "2 AM: the hour my inner monologue turns into a TED Talk no one asked for."],
    3: ["3 AM: Why sleep when I can spiral in style?", "3 AM. Body tired. Brain: what if dinosaurs had anxiety?", "It's 3 AM and my pillow just became a therapy session.", "3 AM: unlocked a new memory to cringe about forever."],
    4: ["4 AM: Birds are chirping. I'm still a disaster.", "It's 4 AM and the only thing up is my cortisol.", "4 AM: technically morning, emotionally a haunted house.", "4 AM: nature wakes up, and so does my self-doubt."],
    5: ["5 AM. Too early to function, too late to pretend I slept.", "5 AM: when you're not awake on purpose, just on accident.", "It's 5 AM and I'm watching the sun rise out of spite.", "5 AM: the sky's changing and so is my grip on sanity."],
    6: ["6 AM: my alarm clock hates me and honestly? Valid.", "6 AM and I'm already 3 years behind on life.", "It's 6 AM. Should I meditate or scream quietly?", "6 AM: the day starts, but I do not."],
    7: ["7 AM. I'm vertical but not thriving.", "7 AM: awake in body, missing in spirit.", "It's 7 AM and I'm already Googling how to fake enthusiasm.", "7 AM: coffee's hot, my ambition is lukewarm."],
    8: ["8 AM. Pretending I'm a productive citizen again.", "It's 8 AM and the email avalanche begins.", "8 AM: fully dressed in despair and denim.", "8 AM: caffeine loading, willpower buffering."],
    9: ["9 AM. I've opened five tabs and zero intentions.", "9 AM: work mode ON, motivation OFF.", "It's 9 AM and I'm already pretending to be in a meeting.", "9 AM: crushing emails like dreams."],
    10: ["10 AM: halfway to lunch, emotionally at the end.", "10 AM and I still haven't accepted that I'm awake.", "It's 10 AM. Time to pretend I understand my job.", "10 AM: thriving, if your definition of thriving is \"not crying yet.\""],
    11: ["11 AM: I'm not procrastinating. I'm time traveling inefficiently.", "It's 11 AM. I've done nothing but feel busy.", "11 AM: floating between coffee and crisis.", "11 AM: is it too early to call it a day?"],
    12: ["12 PM: Lunch? Already? I did so little to deserve this.", "Noon. Halfway to nowhere, fueled by snacks and sarcasm.", "12 PM: the sun is at its peak, unlike me.", "It's 12 PM and I've contributed one (1) sigh to society."],
    13: ["1 PM: productivity's ghost hour.", "1 PM and I'm just a meat puppet staring at a screen.", "It's 1 PM. Still pretending that spreadsheet makes sense.", "1 PM: brain left the chat."],
    14: ["2 PM. Daydreaming about escape plans and snacks.", "It's 2 PM: hunger, confusion, and fake smiling.", "2 PM: I've hit the wall. The wall hit back.", "2 PM: the hour of unproductive rebellion."],
    15: ["3 PM. Caffeine gone. Hope vanished. Just vibes.", "It's 3 PM and I've opened my 19th tab of denial.", "3 PM: The day's still happening and I deeply resent that.", "3 PM: brain melted. Only sarcasm remains."],
    16: ["4 PM. Energy low. Complaints high.", "It's 4 PM. I'm technically conscious but emotionally buffering.", "4 PM: Why is this meeting happening to me?", "4 PM: fading faster than my phone battery."],
    17: ["5 PM. Workday ends, existential crisis begins.", "5 PM: I survived. Somehow. Barely.", "It's 5 PM. I've earned the right to collapse.", "5 PM: logging off but still dead inside."],
    18: ["6 PM: cooking? Or just eating crackers over the sink?", "It's 6 PM. The food is hot, my standards are low.", "6 PM: Dinner plans? You mean depression with a side of pasta?", "6 PM: feasting like a raccoon in emotional recovery."],
    19: ["7 PM. I call this meal: chaos and calories.", "7 PM: too late to be productive, too early to sleep.", "It's 7 PM. Nothing makes sense, but the snacks are here.", "7 PM: vibes are weird, leftovers are divine."],
    20: ["8 PM: intentionally ignoring the dishes.", "8 PM: Peak delusion hour. I'm totally going to clean my life now.", "It's 8 PM. Netflix, take the wheel.", "8 PM: productivity now legally prohibited."],
    21: ["9 PM: where guilt meets popcorn.", "9 PM: I should be sleeping. Instead, I'm reorganizing my trauma.", "It's 9 PM. Let's start a hobby we'll never finish.", "9 PM: the hour of unrealistic intentions."],
    22: ["10 PM. One more episode = three less hours of sleep.", "10 PM: truly a time for poor decisions and blanket forts.", "It's 10 PM and I'm just getting weird now.", "10 PM: peak \"I swear I'll go to bed soon\" energy."],
    23: ["11 PM: I'm awake and dramatic for no reason.", "11 PM: bedtime is a concept, not a reality.", "It's 11 PM. I'm texting people I shouldn't and opening apps I hate.", "11 PM: just one last scroll... for science."]
  }

  const handleSignupSuccess = (user: any) => {
    console.log('Signup successful:', user)
    setSuccessData({
      title: 'Welcome to Boo!',
      message: `Your account has been created successfully, ${user.display_name}! Get ready to capture your thoughts.`
    })
    setShowSuccessModal(true)
    
    setTimeout(() => {
      navigate('/', { replace: true })
      window.location.reload()
    }, 3000)
  }

  const handleLoginSuccess = (user: any) => {
    console.log('Login successful:', user)
    setSuccessData({
      title: 'Welcome Back!',
      message: `Good to see you again, ${user.display_name}! Let's dive back into your thoughts.`
    })
    setShowSuccessModal(true)
    
    setTimeout(() => {
      navigate('/', { replace: true })
      window.location.reload()
    }, 3000)
  }

  const handleSuccessModalClose = () => {
    setShowSuccessModal(false)
    navigate('/', { replace: true })
    window.location.reload()
  }

  // Clock update effect and snarky comments
  useEffect(() => {
    const updateTimeAndSnark = () => {
      const now = new Date()
      setCurrentTime(now)
      const hour = now.getHours()
      const comments = snarkyComments[hour as keyof typeof snarkyComments] || ["Time to reflect with Boo"]
      setCurrentSnark(comments[Math.floor(Math.random() * comments.length)])
    }

    updateTimeAndSnark()
    const interval = setInterval(updateTimeAndSnark, 60000) // Update every minute
    return () => clearInterval(interval)
  }, [])

  // Determine time of day
  useEffect(() => {
    const hour = currentTime.getHours()
    if (hour >= 5 && hour < 12) {
      setTimeOfDay('morning')
    } else if (hour >= 12 && hour < 17) {
      setTimeOfDay('day')
    } else if (hour >= 17 && hour < 20) {
      setTimeOfDay('evening')
    } else {
      setTimeOfDay('night')
    }
  }, [currentTime])

  // Typewriter effect for snarky comments
  useEffect(() => {
    if (!currentSnark) return

    // Start typing after all other animations are done (delay matches other elements + buffer)
    const startDelay = setTimeout(() => {
      setIsTyping(true)
      setDisplayedSnark('')
      
      let index = 0
      const typeInterval = setInterval(() => {
        if (index < currentSnark.length) {
          setDisplayedSnark(currentSnark.slice(0, index + 1))
          index++
        } else {
          setIsTyping(false)
          clearInterval(typeInterval)
        }
      }, 50) // 50ms per character for smooth typing

      return () => clearInterval(typeInterval)
    }, 1500) // Wait for other animations to complete

    return () => clearTimeout(startDelay)
  }, [currentSnark])

  // Get gradient colors based on time
  const getSceneGradient = () => {
    switch (timeOfDay) {
      case 'morning':
        return 'from-orange-400 via-pink-400 to-purple-500'
      case 'day':
        return 'from-blue-400 via-cyan-400 to-purple-500'
      case 'evening':
        return 'from-orange-500 via-pink-500 to-purple-600'
      case 'night':
        return 'from-indigo-800 via-purple-800 to-pink-900'
      default:
        return 'from-purple-600 via-pink-500 to-orange-400'
    }
  }

  // Get sun/moon properties based on time
  const getCelestialBody = () => {
    switch (timeOfDay) {
      case 'morning':
        return { gradient: 'from-yellow-200 to-orange-300', size: 'w-16 h-16' }
      case 'day':
        return { gradient: 'from-yellow-100 to-yellow-300', size: 'w-14 h-14' }
      case 'evening':
        return { gradient: 'from-orange-300 to-red-400', size: 'w-16 h-16' }
      case 'night':
        return { gradient: 'from-gray-200 to-gray-400', size: 'w-12 h-12' }
      default:
        return { gradient: 'from-yellow-200 to-orange-300', size: 'w-16 h-16' }
    }
  }

  const celestialBody = getCelestialBody()

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 via-purple-900 to-slate-900 text-foreground relative overflow-hidden">
      {/* Static stars with subtle shimmer */}
      <div className="absolute inset-0 pointer-events-none">
        {/* Layer 1: Static bright stars */}
        {stars.staticStars.map((star) => (
          <div
            key={star.id}
            className="absolute bg-white rounded-full"
            style={{
              left: `${star.left}%`,
              top: `${star.top}%`,
              width: `${star.size}px`,
              height: `${star.size}px`,
              opacity: star.opacity,
            }}
          />
        ))}
        
        {/* Layer 2: Subtle shimmering stars */}
        {stars.shimmerStars.map((star) => (
          <motion.div
            key={star.id}
            className="absolute w-1 h-1 bg-white rounded-full"
            style={{
              left: `${star.left}%`,
              top: `${star.top}%`,
            }}
            animate={{
              opacity: [0.6, 0.9, 0.6],
              scale: [1, 1.2, 1],
            }}
            transition={{
              duration: star.duration,
              repeat: Infinity,
              delay: star.delay,
              ease: "easeInOut",
            }}
          />
        ))}
        
        {/* Shooting stars */}
        {[...Array(3)].map((_, i) => (
          <motion.div
            key={`shooting-${i}`}
            className="absolute w-1 h-[1px] bg-gradient-to-r from-transparent via-white to-transparent"
            style={{
              left: `${Math.random() * 100}%`,
              top: `${Math.random() * 50}%`,
            }}
            animate={{
              x: [0, 200],
              y: [0, 100],
              opacity: [0, 1, 0],
            }}
            transition={{
              duration: 1,
              repeat: Infinity,
              delay: i * 3 + Math.random() * 5,
              ease: "easeOut"
            }}
          />
        ))}
      </div>

      <div className="relative z-10 min-h-screen flex items-center justify-center p-4">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="w-full max-w-md"
        >
          <div className="bg-card/95 backdrop-blur-md rounded-2xl overflow-hidden shadow-2xl">
            {/* Scenic header illustration */}
            <div className={`relative h-64 bg-gradient-to-b ${getSceneGradient()} overflow-hidden transition-all duration-1000`}>
              {/* Sun/Moon */}
              <motion.div
                className={`absolute top-8 right-12 ${celestialBody.size} bg-gradient-to-br ${celestialBody.gradient} rounded-full transition-all duration-1000 ${
                  timeOfDay === 'night' ? 'shadow-lg shadow-gray-400/30' : 'shadow-xl shadow-yellow-400/40'
                }`}
                animate={{
                  y: [0, 10, 0],
                }}
                transition={{
                  duration: 4,
                  repeat: Infinity,
                  ease: "easeInOut"
                }}
              />
              
              {/* Moon craters (only at night) */}
              {timeOfDay === 'night' && (
                <>
                  <div className="absolute top-10 right-14 w-2 h-2 bg-gray-500/30 rounded-full" />
                  <div className="absolute top-12 right-16 w-3 h-3 bg-gray-500/20 rounded-full" />
                  <div className="absolute top-14 right-12 w-2 h-2 bg-gray-500/25 rounded-full" />
                </>
              )}
              
              {/* Mountains SVG */}
              <svg className="absolute bottom-0 w-full" viewBox="0 0 400 150" preserveAspectRatio="none">
                {/* Back mountain */}
                <motion.path
                  d="M0,150 L100,40 L200,80 L400,150 Z"
                  fill="rgba(99, 102, 241, 0.3)"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 1, delay: 0.2 }}
                />
                {/* Middle mountain */}
                <motion.path
                  d="M0,150 L150,50 L250,90 L400,150 Z"
                  fill="rgba(139, 92, 246, 0.5)"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 1, delay: 0.4 }}
                />
                {/* Front mountain */}
                <motion.path
                  d="M0,150 L80,70 L180,100 L300,60 L400,150 Z"
                  fill="rgba(168, 85, 247, 0.7)"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 1, delay: 0.6 }}
                />
              </svg>
            </div>

            {/* Form section */}
            <div className="p-8 space-y-6">
              <motion.h1 
                className="text-3xl font-bold text-center text-white"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.3 }}
              >
                Boo
              </motion.h1>

              <motion.div 
                className="space-y-4"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.5 }}
              >
                {/* Sign In Button */}
                <motion.button
                  onClick={() => setShowSigninModal(true)}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className="w-full py-3 px-4 bg-primary/20 hover:bg-primary/30 border border-primary/30 text-white rounded-lg font-medium transition-all duration-200"
                >
                  Sign In
                </motion.button>

                {/* Create Account Button */}
                <motion.button
                  onClick={() => setShowSignupModal(true)}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className="w-full py-3 px-4 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white rounded-lg font-medium transition-all duration-200 shadow-lg"
                >
                  Create Account
                </motion.button>
              </motion.div>

              <motion.p 
                className="text-center text-xs text-gray-400 mt-6"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.7 }}
              >
                100% Local, 100% Private, 100% Yours
              </motion.p>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Top Right Clock - Same as HomePage */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.8 }}
        className="absolute top-4 right-4 md:top-8 md:right-8 z-30 text-right"
      >
        {/* Time Display */}
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

        {/* Snarky Comment - Typewriter Effect */}
        <div className="w-[32rem] min-h-[1.5rem]">
          <p className="text-gray-300 text-sm italic text-right whitespace-nowrap">
            "{displayedSnark}
            {isTyping && (
              <motion.span
                animate={{ opacity: [1, 0] }}
                transition={{ duration: 0.8, repeat: Infinity }}
                className="text-pink-400"
              >
                |
              </motion.span>
            )}"
          </p>
        </div>
      </motion.div>

      {/* Modals */}
      <SignupModal
        isOpen={showSignupModal}
        onClose={() => setShowSignupModal(false)}
        onSuccess={handleSignupSuccess}
      />

      <LoginModal
        isOpen={showSigninModal}
        onClose={() => setShowSigninModal(false)}
        onSuccess={handleLoginSuccess}
      />

      <SuccessModal
        isOpen={showSuccessModal}
        title={successData.title}
        message={successData.message}
        onClose={handleSuccessModalClose}
        autoCloseMs={3000}
      />
    </div>
  )
}

export default LandingPage