import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { X, Eye, EyeOff, LogIn, Shield, RefreshCw } from 'lucide-react'
import { api } from '@/lib/api'

interface LoginModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: (user: any) => void
}

export interface LoginData {
  name: string
  password?: string
  recoveryPhrase?: string
  emergencyKeyFile?: File
}

function LoginModal({ isOpen, onClose, onSuccess }: LoginModalProps) {
  const [formData, setFormData] = useState<LoginData>({
    name: '',
    password: '',
    recoveryPhrase: '',
    emergencyKeyFile: undefined
  })
  
  const [showPassword, setShowPassword] = useState(false)
  const [errors, setErrors] = useState<Partial<LoginData>>({})
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [loginMethod, setLoginMethod] = useState<'password' | 'phrase' | 'emergency'>('password')
  const [apiError, setApiError] = useState('')

  const handleInputChange = (field: keyof LoginData, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }))
    
    // Clear error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: undefined }))
    }
  }

  const handleFileChange = (file: File | null) => {
    setFormData(prev => ({ ...prev, emergencyKeyFile: file || undefined }))
    if (errors.emergencyKeyFile) {
      setErrors(prev => ({ ...prev, emergencyKeyFile: undefined }))
    }
  }

  const validateForm = () => {
    const newErrors: Partial<LoginData> = {}
    
    if (!formData.name.trim()) {
      newErrors.name = 'Name is required'
    }
    
    switch (loginMethod) {
      case 'password':
        if (!formData.password) {
          newErrors.password = 'Password is required'
        }
        break
      case 'phrase':
        if (!formData.recoveryPhrase?.trim()) {
          newErrors.recoveryPhrase = 'Recovery phrase is required'
        }
        break
      case 'emergency':
        if (!formData.emergencyKeyFile) {
          newErrors.emergencyKeyFile = 'Emergency key file is required' as any
        } else if (!formData.emergencyKeyFile.name.endsWith('.boounlock')) {
          newErrors.emergencyKeyFile = 'Invalid file type. Please select an .boounlock file' as any
        }
        break
    }
    
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!validateForm()) return
    
    setIsSubmitting(true)
    setApiError('')
    
    try {
      let response;
      
      if (loginMethod === 'emergency' && formData.emergencyKeyFile) {
        // Handle emergency key file upload
        response = await api.uploadEmergencyKey(formData.name, formData.emergencyKeyFile)
      } else {
        // Handle regular login (password or recovery phrase)
        const loginData: any = { name: formData.name }
        
        if (loginMethod === 'password') {
          loginData.password = formData.password
        } else if (loginMethod === 'phrase') {
          loginData.recovery_phrase = formData.recoveryPhrase
        }
        
        response = await api.loginUser(loginData)
      }

      if (response.success && response.data) {
        // Store session token if needed (for future requests)
        localStorage.setItem('session_token', response.data.session_token)
        
        // Call success handler
        onSuccess(response.data.user)
        onClose()
      } else {
        setApiError(response.error || 'Login failed')
      }
    } catch (error) {
      console.error('Login failed:', error)
      setApiError('Network error. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const switchLoginMethod = (method: 'password' | 'phrase' | 'emergency') => {
    setLoginMethod(method)
    setFormData(prev => ({ ...prev, password: '', recoveryPhrase: '', emergencyKeyFile: undefined }))
    setErrors({})
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
          className="bg-card border border-border rounded-lg shadow-2xl overflow-hidden max-w-md w-full"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="px-6 py-4 border-b border-border">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-600 flex items-center justify-center">
                  {loginMethod === 'emergency' ? <Shield className="h-4 w-4 text-white" /> : <LogIn className="h-4 w-4 text-white" />}
                </div>
                <div>
                  <h2 className="text-xl font-bold text-white">
                    {loginMethod === 'emergency' ? 'Emergency Recovery' : 'Welcome Back to Boo'}
                  </h2>
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
                placeholder="Enter your name"
                className="bg-muted/20 border-border/50 text-white placeholder:text-gray-500"
              />
              {errors.name && (
                <p className="text-sm text-red-400">{errors.name}</p>
              )}
            </div>

            {/* Login Method Tabs */}
            <div className="space-y-4">
              <div className="flex gap-1 bg-muted/20 rounded-lg p-1">
                <button
                  type="button"
                  onClick={() => switchLoginMethod('password')}
                  className={`flex-1 px-3 py-2 text-xs font-medium rounded-md transition-colors ${
                    loginMethod === 'password'
                      ? 'bg-primary/20 text-primary border border-primary/30'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  Password
                </button>
                <button
                  type="button"
                  onClick={() => switchLoginMethod('phrase')}
                  className={`flex-1 px-3 py-2 text-xs font-medium rounded-md transition-colors ${
                    loginMethod === 'phrase'
                      ? 'bg-primary/20 text-primary border border-primary/30'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  Recovery Phrase
                </button>
                <button
                  type="button"
                  onClick={() => switchLoginMethod('emergency')}
                  className={`flex-1 px-3 py-2 text-xs font-medium rounded-md transition-colors ${
                    loginMethod === 'emergency'
                      ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  Emergency Key
                </button>
              </div>

              {/* Password Login */}
              {loginMethod === 'password' && (
                <div className="space-y-2">
                  <Label htmlFor="password" className="text-sm font-medium text-white">
                    Password
                  </Label>
                  <div className="relative">
                    <Input
                      id="password"
                      type={showPassword ? "text" : "password"}
                      value={formData.password || ''}
                      onChange={(e) => handleInputChange('password', e.target.value)}
                      placeholder="Enter your password"
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
                  {errors.password && (
                    <p className="text-sm text-red-400">{errors.password}</p>
                  )}
                </div>
              )}

              {/* Recovery Phrase Login */}
              {loginMethod === 'phrase' && (
                <div className="space-y-2">
                  <Label htmlFor="recoveryPhrase" className="text-sm font-medium text-white">
                    Recovery Phrase
                  </Label>
                  <textarea
                    id="recoveryPhrase"
                    value={formData.recoveryPhrase || ''}
                    onChange={(e) => handleInputChange('recoveryPhrase', e.target.value)}
                    placeholder="Enter your memorable recovery phrase..."
                    rows={3}
                    className="w-full px-3 py-2 bg-muted/20 border border-border/50 rounded-md text-white text-sm placeholder:text-gray-500 resize-none focus:outline-none focus:ring-2 focus:ring-primary/50"
                  />
                  {errors.recoveryPhrase && (
                    <p className="text-sm text-red-400">{errors.recoveryPhrase}</p>
                  )}
                  <p className="text-xs text-gray-400">
                    Enter the memorable phrase you created during signup
                  </p>
                </div>
              )}

              {/* Emergency Key File Upload */}
              {loginMethod === 'emergency' && (
                <div className="space-y-2">
                  <Label className="text-sm font-medium text-white">
                    Emergency Recovery Key
                  </Label>
                  <div className="border-2 border-dashed border-border/50 rounded-lg p-6 text-center">
                    <Shield className="h-8 w-8 text-gray-400 mx-auto mb-2" />
                    <p className="text-sm text-gray-400 mb-3">
                      Upload your .boounlock recovery file
                    </p>
                    <input
                      type="file"
                      accept=".boounlock"
                      onChange={(e) => handleFileChange(e.target.files?.[0] || null)}
                      className="hidden"
                      id="emergency-file"
                    />
                    <Label
                      htmlFor="emergency-file"
                      className="inline-flex items-center px-4 py-2 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg cursor-pointer hover:bg-red-500/20"
                    >
                      Select .boounlock File
                    </Label>
                    {formData.emergencyKeyFile && (
                      <p className="text-sm text-green-400 mt-2">
                        ✓ {formData.emergencyKeyFile.name}
                      </p>
                    )}
                    {errors.emergencyKeyFile && (
                      <p className="text-sm text-red-400 mt-2">{errors.emergencyKeyFile as string}</p>
                    )}
                  </div>
                  <p className="text-xs text-gray-400">
                    This is the emergency recovery file you saved when creating your account
                  </p>
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
              disabled={isSubmitting}
              className="w-full flex items-center gap-2 relative overflow-hidden group transition-all duration-200 bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 hover:text-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <div className="flex items-center gap-2">
                {isSubmitting ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    {loginMethod === 'emergency' ? 'Recovering Account...' : 'Signing In...'}
                  </>
                ) : (
                  <>
                    <LogIn className="h-4 w-4" />
                    {loginMethod === 'emergency' ? 'Recover Account' : 'Sign In'}
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

export default LoginModal