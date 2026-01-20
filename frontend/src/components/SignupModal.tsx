import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { X, Eye, EyeOff, User, Shield, RefreshCw } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { api } from '@/lib/api'

interface SignupModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: (user: any) => void
}

export interface SignupData {
  name: string
  password: string
  recoveryPhrase: string
  emergencyKey: string
}

// Password strength calculation
const calculatePasswordStrength = (password: string) => {
  let score = 0
  let feedback = []

  if (password.length >= 8) score += 1
  else feedback.push('At least 8 characters')
  
  if (/[a-z]/.test(password)) score += 1
  else feedback.push('Lowercase letter')
  
  if (/[A-Z]/.test(password)) score += 1
  else feedback.push('Uppercase letter')
  
  if (/[0-9]/.test(password)) score += 1
  else feedback.push('Number')
  
  if (/[^A-Za-z0-9]/.test(password)) score += 1
  else feedback.push('Special character')

  const strength = score === 5 ? 'strong' : score >= 3 ? 'medium' : 'weak'
  return { score, strength, feedback }
}

// Recovery phrase examples for user guidance
const recoveryPhraseExamples = [
  "I miss her banana pancakes on sunday mornings",
  "The old oak tree behind grandma's house",
  "Dancing in the rain was our favorite thing",
  "Coffee tastes better when shared with friends"
]

function SignupModal({ isOpen, onClose, onSuccess }: SignupModalProps) {
  const [formData, setFormData] = useState<SignupData>({
    name: '',
    password: '',
    recoveryPhrase: '',
    emergencyKey: ''
  })
  
  const [showPassword, setShowPassword] = useState(false)
  const [passwordStrength, setPasswordStrength] = useState(calculatePasswordStrength(''))
  const [errors, setErrors] = useState<Partial<SignupData>>({})
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [currentExample, setCurrentExample] = useState(0)
  const [emergencyKey, setEmergencyKey] = useState('')
  const [keyGenerated, setKeyGenerated] = useState(false)
  const [apiError, setApiError] = useState('')

  const handleInputChange = (field: keyof SignupData, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }))
    
    // Clear error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: undefined }))
    }
    
    // Update password strength
    if (field === 'password') {
      setPasswordStrength(calculatePasswordStrength(value))
    }
  }

  const validateForm = () => {
    const newErrors: Partial<SignupData> = {}
    
    if (!formData.name.trim()) {
      newErrors.name = 'Name is required'
    } else if (formData.name.length < 2) {
      newErrors.name = 'Name must be at least 2 characters'
    }
    
    if (!formData.password) {
      newErrors.password = 'Password is required'
    } else if (passwordStrength.strength === 'weak') {
      newErrors.password = 'Password is too weak'
    }

    if (!formData.recoveryPhrase.trim()) {
      newErrors.recoveryPhrase = 'Recovery phrase is required'
    } else if (formData.recoveryPhrase.length < 10) {
      newErrors.recoveryPhrase = 'Recovery phrase should be at least 10 characters'
    }

    if (!emergencyKey) {
      newErrors.emergencyKey = 'Please generate your emergency recovery key'
    }
    
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  // Check if all fields are filled for submit button state
  const isFormComplete = () => {
    return (
      formData.name.trim().length >= 2 &&
      formData.password.length >= 8 &&
      passwordStrength.strength !== 'weak' &&
      formData.recoveryPhrase.trim().length >= 10 &&
      emergencyKey.length > 0
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!validateForm()) return
    
    setIsSubmitting(true)
    setApiError('')
    
    try {
      const response = await api.registerUser({
        name: formData.name,
        password: formData.password,
        recovery_phrase: formData.recoveryPhrase,
        emergency_key: emergencyKey
      })

      if (response.success && response.data) {
        // Download the emergency key file
        const content = response.data.emergency_key_file
        const blob = new Blob([content], { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = response.data.filename
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(url)

        // Call success handler
        onSuccess(response.data.user)
        onClose()
      } else {
        setApiError(response.error || 'Registration failed')
      }
    } catch (error) {
      console.error('Signup failed:', error)
      setApiError('Network error. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const cycleExample = () => {
    setCurrentExample(prev => (prev + 1) % recoveryPhraseExamples.length)
  }

  // Generate emergency recovery key (UUID-like)
  const generateEmergencyKey = () => {
    const key = 'boo_' + crypto.randomUUID().replace(/-/g, '')
    setEmergencyKey(key)
    setFormData(prev => ({ ...prev, emergencyKey: key }))
    setKeyGenerated(true)
  }

  // Download emergency key file
  const downloadEmergencyKey = () => {
    const content = JSON.stringify({
      type: 'boo_emergency_key',
      key: emergencyKey,
      created: new Date().toISOString(),
      name: formData.name
    }, null, 2)
    
    const blob = new Blob([content], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${formData.name.toLowerCase().replace(/\s+/g, '_')}_recovery.boounlock`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  return (
    <AnimatePresence mode="wait">
      {isOpen && (
        <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.3, ease: "easeInOut" }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4"
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
          className="bg-card border border-border rounded-lg shadow-2xl overflow-hidden max-w-md w-full max-h-[85vh] overflow-y-auto"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="px-6 py-4 border-b border-border">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center">
                  <User className="h-4 w-4 text-white" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-white">Create Your Boo Account</h2>
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
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="p-6 space-y-6">
            {/* Name */}
            <div className="space-y-2">
              <Label htmlFor="name" className="text-sm font-medium text-white">
                Your Name
              </Label>
              <Input
                id="name"
                type="text"
                value={formData.name}
                onChange={(e) => handleInputChange('name', e.target.value)}
                placeholder="How should Boo address you?"
                className="bg-muted/20 border-border/50 text-white placeholder:text-gray-500"
              />
              {errors.name && (
                <p className="text-sm text-red-400">{errors.name}</p>
              )}
            </div>

            {/* Password */}
            <div className="space-y-2">
              <Label htmlFor="password" className="text-sm font-medium text-white">
                Password
              </Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={formData.password}
                  onChange={(e) => handleInputChange('password', e.target.value)}
                  placeholder="Create a strong password"
                  className="bg-muted/20 border-border/50 text-white placeholder:text-gray-500 pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              
              {/* Password Strength */}
              {formData.password && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
                      <div 
                        className={`h-full transition-all duration-300 ${
                          passwordStrength.strength === 'strong' 
                            ? 'bg-green-500 w-full' 
                            : passwordStrength.strength === 'medium'
                            ? 'bg-yellow-500 w-3/5'
                            : 'bg-red-500 w-1/5'
                        }`}
                      />
                    </div>
                    <Badge 
                      variant="secondary" 
                      className={`text-xs ${
                        passwordStrength.strength === 'strong' 
                          ? 'bg-green-500/10 text-green-400 border-green-500/20' 
                          : passwordStrength.strength === 'medium'
                          ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20'
                          : 'bg-red-500/10 text-red-400 border-red-500/20'
                      }`}
                    >
                      {passwordStrength.strength}
                    </Badge>
                  </div>
                  {passwordStrength.feedback.length > 0 && (
                    <p className="text-xs text-gray-500">
                      Missing: {passwordStrength.feedback.join(', ')}
                    </p>
                  )}
                </div>
              )}
              
              {errors.password && (
                <p className="text-sm text-red-400">{errors.password}</p>
              )}
            </div>

            {/* Recovery Phrase */}
            <div className="space-y-2">
              <Label htmlFor="recoveryPhrase" className="text-sm font-medium text-white">
                Recovery Phrase
              </Label>
              <textarea
                id="recoveryPhrase"
                value={formData.recoveryPhrase}
                onChange={(e) => handleInputChange('recoveryPhrase', e.target.value)}
                placeholder="Enter a memorable phrase only you would know..."
                rows={3}
                className="w-full px-3 py-2 bg-muted/20 border border-border/50 rounded-md text-white text-sm placeholder:text-gray-500 resize-none focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
              {errors.recoveryPhrase && (
                <p className="text-sm text-red-400">{errors.recoveryPhrase}</p>
              )}
              
              {/* Examples */}
              <div className="bg-muted/10 border border-border/30 rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-gray-400">Example:</span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={cycleExample}
                    className="h-6 px-2 text-xs text-blue-400 hover:text-blue-300"
                  >
                    <RefreshCw className="h-3 w-3 mr-1" />
                    More
                  </Button>
                </div>
                <p className="text-sm text-blue-300 italic">
                  "{recoveryPhraseExamples[currentExample]}"
                </p>
              </div>
            </div>

            {/* Emergency Recovery Key */}
            <div className="space-y-2">
              <Label className="text-sm font-medium text-white">
                Emergency Recovery Key
              </Label>
              
              {!keyGenerated ? (
                <div className="bg-muted/10 border border-border/30 rounded-lg p-4 text-center">
                  <Shield className="h-8 w-8 text-gray-400 mx-auto mb-2" />
                  <p className="text-sm text-gray-400 mb-3">
                    Create your emergency recovery key
                  </p>
                  <Button
                    type="button"
                    onClick={generateEmergencyKey}
                    disabled={!formData.name.trim()}
                    className="relative overflow-hidden group px-4 py-2 rounded-lg font-medium shadow-lg hover:shadow-xl transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20"
                  >
                    <div className="absolute inset-0 bg-gradient-to-r from-red-500/10 to-red-600/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                    <span className="relative z-10 font-medium">
                      Generate Emergency Key
                    </span>
                  </Button>
                  {!formData.name.trim() && (
                    <p className="text-xs text-gray-500 mt-2">Enter your name first</p>
                  )}
                </div>
              ) : (
                <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                    <span className="text-sm font-medium text-green-400">Emergency Key Generated</span>
                  </div>
                  
                  <div className="bg-black/20 rounded border p-2 mb-3">
                    <p className="text-xs text-gray-300 font-mono break-all">
                      {emergencyKey}
                    </p>
                  </div>
                  
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      onClick={downloadEmergencyKey}
                      className="flex-1 relative overflow-hidden group px-3 py-2 rounded-lg font-medium shadow-lg hover:shadow-xl transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-green-500/10 border border-green-500/20 text-green-400 hover:bg-green-500/20 text-sm"
                    >
                      <div className="absolute inset-0 bg-gradient-to-r from-green-500/10 to-emerald-500/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                      <span className="relative z-10 font-medium">
                        Download .boounlock
                      </span>
                    </Button>
                    <Button
                      type="button"
                      onClick={generateEmergencyKey}
                      className="px-3 py-2 text-sm text-gray-400 hover:text-white bg-muted/20 hover:bg-muted/30 border border-border/50 rounded-lg"
                    >
                      <RefreshCw className="h-3 w-3" />
                    </Button>
                  </div>
                  
                  <div className="mt-3 p-2 bg-yellow-500/10 border border-yellow-500/20 rounded">
                    <p className="text-xs text-yellow-400">
                      ⚠️ Save this file in a secure location. You'll need it if you lose both your password and recovery phrase.
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* API Error Display */}
            {apiError && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
                <p className="text-sm text-red-400">{apiError}</p>
              </div>
            )}

            {/* Submit Button */}
            <Button
              type="submit"
              disabled={isSubmitting || !isFormComplete()}
              className="w-full flex items-center gap-2 relative overflow-hidden group transition-all duration-200 bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 hover:text-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <div className="flex items-center gap-2">
                {isSubmitting ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    Creating Account...
                  </>
                ) : (
                  <>
                    <User className="h-4 w-4" />
                    Create Account
                  </>
                )}
              </div>
            </Button>
          </form>
        </motion.div>
      </motion.div>
      )}
    </AnimatePresence>
  )
}

export default SignupModal