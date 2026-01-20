import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { X, Eye, EyeOff, Lock, Shield, RefreshCw } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { api } from '@/lib/api'

interface AccountSettingsModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: (message: string) => void
}

export interface ChangePasswordData {
  currentPassword: string
  newPassword: string
}

export interface ChangeRecoveryPhraseData {
  currentPassword: string
  newRecoveryPhrase: string
}

// Password strength calculation (same as SignupModal)
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

function AccountSettingsModal({ isOpen, onClose, onSuccess }: AccountSettingsModalProps) {
  const [activeTab, setActiveTab] = useState<'password' | 'recovery'>('password')
  
  // Password change state
  const [passwordData, setPasswordData] = useState<ChangePasswordData>({
    currentPassword: '',
    newPassword: ''
  })
  const [showCurrentPassword, setShowCurrentPassword] = useState(false)
  const [showNewPassword, setShowNewPassword] = useState(false)
  const [passwordStrength, setPasswordStrength] = useState(calculatePasswordStrength(''))
  const [passwordErrors, setPasswordErrors] = useState<Partial<ChangePasswordData>>({})
  const [isSubmittingPassword, setIsSubmittingPassword] = useState(false)
  
  // Recovery phrase change state
  const [recoveryData, setRecoveryData] = useState<ChangeRecoveryPhraseData>({
    currentPassword: '',
    newRecoveryPhrase: ''
  })
  const [showRecoveryPassword, setShowRecoveryPassword] = useState(false)
  const [recoveryErrors, setRecoveryErrors] = useState<Partial<ChangeRecoveryPhraseData>>({})
  const [isSubmittingRecovery, setIsSubmittingRecovery] = useState(false)
  const [apiError, setApiError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  const handlePasswordInputChange = (field: keyof ChangePasswordData, value: string) => {
    setPasswordData(prev => ({ ...prev, [field]: value }))
    
    // Clear error when user starts typing
    if (passwordErrors[field]) {
      setPasswordErrors(prev => ({ ...prev, [field]: undefined }))
    }
    
    // Update password strength for new password
    if (field === 'newPassword') {
      setPasswordStrength(calculatePasswordStrength(value))
    }
  }

  const handleRecoveryInputChange = (field: keyof ChangeRecoveryPhraseData, value: string) => {
    setRecoveryData(prev => ({ ...prev, [field]: value }))
    
    // Clear error when user starts typing
    if (recoveryErrors[field]) {
      setRecoveryErrors(prev => ({ ...prev, [field]: undefined }))
    }
  }

  const validatePasswordForm = () => {
    const newErrors: Partial<ChangePasswordData> = {}
    
    if (!passwordData.currentPassword) {
      newErrors.currentPassword = 'Current password is required'
    }
    
    if (!passwordData.newPassword) {
      newErrors.newPassword = 'New password is required'
    } else if (passwordStrength.strength === 'weak') {
      newErrors.newPassword = 'New password is too weak'
    } else if (passwordData.newPassword === passwordData.currentPassword) {
      newErrors.newPassword = 'New password must be different from current password'
    }
    
    setPasswordErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const validateRecoveryForm = () => {
    const newErrors: Partial<ChangeRecoveryPhraseData> = {}
    
    if (!recoveryData.currentPassword) {
      newErrors.currentPassword = 'Current password is required'
    }
    
    if (!recoveryData.newRecoveryPhrase.trim()) {
      newErrors.newRecoveryPhrase = 'Recovery phrase is required'
    } else if (recoveryData.newRecoveryPhrase.length < 10) {
      newErrors.newRecoveryPhrase = 'Recovery phrase should be at least 10 characters'
    }
    
    setRecoveryErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!validatePasswordForm()) return
    
    setIsSubmittingPassword(true)
    setApiError('')
    setSuccessMessage('')
    
    try {
      const response = await api.changePassword({
        current_password: passwordData.currentPassword,
        new_password: passwordData.newPassword
      })

      if (response.success && response.data) {
        setSuccessMessage(response.data.message)
        setPasswordData({ currentPassword: '', newPassword: '' })
        setPasswordStrength(calculatePasswordStrength(''))
        
        if (onSuccess) {
          onSuccess(response.data.message)
        }
      } else {
        setApiError(response.error || 'Failed to change password')
      }
    } catch (error) {
      console.error('Password change failed:', error)
      setApiError('Network error. Please try again.')
    } finally {
      setIsSubmittingPassword(false)
    }
  }

  const handleRecoverySubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!validateRecoveryForm()) return
    
    setIsSubmittingRecovery(true)
    setApiError('')
    setSuccessMessage('')
    
    try {
      const response = await api.changeRecoveryPhrase({
        current_password: recoveryData.currentPassword,
        new_recovery_phrase: recoveryData.newRecoveryPhrase
      })

      if (response.success && response.data) {
        setSuccessMessage(response.data.message)
        setRecoveryData({ currentPassword: '', newRecoveryPhrase: '' })
        
        if (onSuccess) {
          onSuccess(response.data.message)
        }
      } else {
        setApiError(response.error || 'Failed to change recovery phrase')
      }
    } catch (error) {
      console.error('Recovery phrase change failed:', error)
      setApiError('Network error. Please try again.')
    } finally {
      setIsSubmittingRecovery(false)
    }
  }

  const resetForms = () => {
    setPasswordData({ currentPassword: '', newPassword: '' })
    setRecoveryData({ currentPassword: '', newRecoveryPhrase: '' })
    setPasswordStrength(calculatePasswordStrength(''))
    setPasswordErrors({})
    setRecoveryErrors({})
    setActiveTab('password')
    setApiError('')
    setSuccessMessage('')
  }

  const handleClose = () => {
    resetForms()
    onClose()
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
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                    <Lock className="h-4 w-4 text-white" />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-white">Account Settings</h2>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleClose}
                  className="h-8 w-8 p-0 text-blue-300 drop-shadow-[0_0_4px_rgba(147,197,253,0.6)] hover:bg-muted/50 hover:text-white hover:drop-shadow-[0_0_6px_rgba(255,255,255,0.6)]"
                  title="Close"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {/* Tab Navigation */}
            <div className="px-6 pt-4">
              <div className="flex gap-1 bg-muted/20 rounded-lg p-1">
                <button
                  type="button"
                  onClick={() => setActiveTab('password')}
                  className={`flex-1 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                    activeTab === 'password'
                      ? 'bg-primary/20 text-primary border border-primary/30'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  <Lock className="h-4 w-4 inline mr-2" />
                  Change Password
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('recovery')}
                  className={`flex-1 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                    activeTab === 'recovery'
                      ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  <Shield className="h-4 w-4 inline mr-2" />
                  Recovery Phrase
                </button>
              </div>
            </div>

            {/* API Error/Success Display */}
            {(apiError || successMessage) && (
              <div className="px-6 pb-0">
                {apiError && (
                  <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg mb-4">
                    <p className="text-sm text-red-400">{apiError}</p>
                  </div>
                )}
                {successMessage && (
                  <div className="p-3 bg-green-500/10 border border-green-500/20 rounded-lg mb-4">
                    <p className="text-sm text-green-400">{successMessage}</p>
                  </div>
                )}
              </div>
            )}

            {/* Form Content */}
            <div className="p-6">
              {activeTab === 'password' && (
                <form onSubmit={handlePasswordSubmit} className="space-y-4">
                  {/* Current Password */}
                  <div className="space-y-2">
                    <Label htmlFor="currentPassword" className="text-sm font-medium text-white">
                      Current Password
                    </Label>
                    <div className="relative">
                      <Input
                        id="currentPassword"
                        type={showCurrentPassword ? "text" : "password"}
                        value={passwordData.currentPassword}
                        onChange={(e) => handlePasswordInputChange('currentPassword', e.target.value)}
                        placeholder="Enter your current password"
                        className="bg-muted/20 border-border/50 text-white text-sm placeholder:text-gray-500 pr-10"
                      />
                      <button
                        type="button"
                        onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
                      >
                        {showCurrentPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                    {passwordErrors.currentPassword && (
                      <p className="text-sm text-red-400">{passwordErrors.currentPassword}</p>
                    )}
                  </div>

                  {/* New Password */}
                  <div className="space-y-2">
                    <Label htmlFor="newPassword" className="text-sm font-medium text-white">
                      New Password
                    </Label>
                    <div className="relative">
                      <Input
                        id="newPassword"
                        type={showNewPassword ? "text" : "password"}
                        value={passwordData.newPassword}
                        onChange={(e) => handlePasswordInputChange('newPassword', e.target.value)}
                        placeholder="Enter your new password"
                        className="bg-muted/20 border-border/50 text-white text-sm placeholder:text-gray-500 pr-10"
                      />
                      <button
                        type="button"
                        onClick={() => setShowNewPassword(!showNewPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
                      >
                        {showNewPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>

                    {/* Password Strength */}
                    {passwordData.newPassword && (
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

                    {passwordErrors.newPassword && (
                      <p className="text-sm text-red-400">{passwordErrors.newPassword}</p>
                    )}
                  </div>

                  {/* Submit Button */}
                  <Button
                    type="submit"
                    disabled={isSubmittingPassword}
                    className="w-full flex items-center gap-2 relative overflow-hidden group transition-all duration-200 bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 hover:text-primary disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <div className="flex items-center gap-2">
                      {isSubmittingPassword ? (
                        <>
                          <RefreshCw className="h-4 w-4 animate-spin" />
                          Changing Password...
                        </>
                      ) : (
                        <>
                          <Lock className="h-4 w-4" />
                          Change Password
                        </>
                      )}
                    </div>
                  </Button>
                </form>
              )}

              {activeTab === 'recovery' && (
                <form onSubmit={handleRecoverySubmit} className="space-y-4">
                  {/* Current Password */}
                  <div className="space-y-2">
                    <Label htmlFor="recoveryCurrentPassword" className="text-sm font-medium text-white">
                      Current Password
                    </Label>
                    <div className="relative">
                      <Input
                        id="recoveryCurrentPassword"
                        type={showRecoveryPassword ? "text" : "password"}
                        value={recoveryData.currentPassword}
                        onChange={(e) => handleRecoveryInputChange('currentPassword', e.target.value)}
                        placeholder="Enter your current password"
                        className="bg-muted/20 border-border/50 text-white text-sm placeholder:text-gray-500 pr-10"
                      />
                      <button
                        type="button"
                        onClick={() => setShowRecoveryPassword(!showRecoveryPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
                      >
                        {showRecoveryPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                    {recoveryErrors.currentPassword && (
                      <p className="text-sm text-red-400">{recoveryErrors.currentPassword}</p>
                    )}
                  </div>

                  {/* New Recovery Phrase */}
                  <div className="space-y-2">
                    <Label htmlFor="newRecoveryPhrase" className="text-sm font-medium text-white">
                      New Recovery Phrase
                    </Label>
                    <textarea
                      id="newRecoveryPhrase"
                      value={recoveryData.newRecoveryPhrase}
                      onChange={(e) => handleRecoveryInputChange('newRecoveryPhrase', e.target.value)}
                      placeholder="Enter a memorable phrase only you would know..."
                      rows={3}
                      className="w-full px-3 py-2 bg-muted/20 border border-border/50 rounded-md text-white text-sm placeholder:text-gray-500 resize-none focus:outline-none focus:ring-2 focus:ring-primary/50"
                    />
                    {recoveryErrors.newRecoveryPhrase && (
                      <p className="text-sm text-red-400">{recoveryErrors.newRecoveryPhrase}</p>
                    )}
                  </div>

                  {/* Submit Button */}
                  <Button
                    type="submit"
                    disabled={isSubmittingRecovery}
                    className="w-full flex items-center gap-2 relative overflow-hidden group transition-all duration-200 bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 hover:bg-yellow-500/20 hover:text-yellow-300 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <div className="flex items-center gap-2">
                      {isSubmittingRecovery ? (
                        <>
                          <RefreshCw className="h-4 w-4 animate-spin" />
                          Updating Recovery Phrase...
                        </>
                      ) : (
                        <>
                          <Shield className="h-4 w-4" />
                          Update Recovery Phrase
                        </>
                      )}
                    </div>
                  </Button>
                </form>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export default AccountSettingsModal