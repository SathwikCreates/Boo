import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Slider } from '@/components/ui/slider'
import { Button } from '@/components/ui/button'
import { useToast } from '@/components/ui/use-toast'
import { api } from '@/lib/api'
import { Keyboard, Globe, Mic, Settings2, Loader2, CheckCircle2, XCircle, FileText, MessageSquare, Brain, AlertTriangle, Palette, User, LogOut, Eye, EyeOff, Download, Shield, Lock } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'

function SettingsPage() {
  const { toast } = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  // Hotkey settings
  const [hotkey, setHotkey] = useState('F8')
  const [isRecordingHotkey, setIsRecordingHotkey] = useState(false)

  // Ollama settings
  const [ollamaHost, setOllamaHost] = useState('localhost')
  const [ollamaPort, setOllamaPort] = useState('11434')
  const [ollamaModels, setOllamaModels] = useState<string[]>([])
  const [ollamaConnected, setOllamaConnected] = useState<boolean | null>(null)
  const [testingOllama, setTestingOllama] = useState(false)

  // Journal Processing settings
  const [journalModel, setJournalModel] = useState('mistral:7b')
  const [journalTemperature, setJournalTemperature] = useState('0.1')
  const [journalContextWindow, setJournalContextWindow] = useState('4096')

  // Talk to Your Diary settings
  const [diaryModel, setDiaryModel] = useState('qwen3:8b')
  const [diaryTemperature, setDiaryTemperature] = useState('0.2')
  const [diaryContextWindow, setDiaryContextWindow] = useState('8192')

  // TTS settings
  const [ttsEngine, setTtsEngine] = useState('piper')
  const [ttsVoice, setTtsVoice] = useState('hfc_female')
  const [ttsSpeed, setTtsSpeed] = useState('1.0')
  const [ttsVolume, setTtsVolume] = useState('1.0')
  const [availableVoices, setAvailableVoices] = useState<Array<{ name: string, filename: string }>>([])
  const [loadingVoices, setLoadingVoices] = useState(false)

  // Voice settings (master toggle)
  const [voiceEnabled, setVoiceEnabled] = useState(false) // Default to OFF

  // Memory settings
  const [memoryEnabled, setMemoryEnabled] = useState(true) // Default to ON

  // General settings
  const [autoSave, setAutoSave] = useState(true)
  const [autoSaveInterval, setAutoSaveInterval] = useState('30')
  const [theme, setTheme] = useState('system')

  // User settings
  const [userName, setUserName] = useState('')
  const [changingPassword, setChangingPassword] = useState(false)
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [changingPhrase, setChangingPhrase] = useState(false)
  const [newRecoveryPhrase, setNewRecoveryPhrase] = useState('')

  // Get current tab from URL or default to 'general'
  const currentTab = searchParams.get('tab') || 'general'

  // Load preferences on mount
  useEffect(() => {
    loadPreferences()
    loadUserInfo()
  }, [])

  // Load available voices when TTS tab is active
  useEffect(() => {
    if (currentTab === 'tts') {
      loadAvailableVoices()
    }
  }, [currentTab])

  const loadPreferences = async () => {
    setLoading(true)
    try {
      const response = await api.getPreferences()
      if (response.success && response.data) {
        const prefs = response.data.preferences

        // Map preferences to state
        prefs.forEach(pref => {
          switch (pref.key) {
            case 'hotkey':
              setHotkey(pref.typed_value || 'F8')
              break
            case 'ollama_host':
              setOllamaHost(pref.typed_value || 'localhost')
              break
            case 'ollama_port':
              setOllamaPort(String(pref.typed_value || '11434'))
              break
            case 'ollama_model':
              setJournalModel(pref.typed_value || 'mistral:7b')
              break
            case 'ollama_temperature':
              setJournalTemperature(String(pref.typed_value || '0.1'))
              break
            case 'ollama_context_window':
              setJournalContextWindow(String(pref.typed_value || '4096'))
              break
            case 'talk_to_diary_model':
              setDiaryModel(pref.typed_value || 'qwen3:8b')
              break
            case 'talk_to_diary_temperature':
              setDiaryTemperature(String(pref.typed_value || '0.2'))
              break
            case 'talk_to_diary_context_window':
              setDiaryContextWindow(String(pref.typed_value || '8192'))
              break
            case 'tts_engine':
              setTtsEngine(pref.typed_value || 'piper')
              break
            case 'tts_voice':
              setTtsVoice(pref.typed_value || 'hfc_female')
              break
            case 'tts_speed':
              setTtsSpeed(String(pref.typed_value || '1.0'))
              break
            case 'tts_volume':
              setTtsVolume(String(pref.typed_value || '1.0'))
              break
            case 'voice_enabled':
              setVoiceEnabled(pref.typed_value === true || pref.typed_value === 'true')
              break
            case 'memory_enabled':
              setMemoryEnabled(pref.typed_value !== false)
              break
            case 'auto_save':
              setAutoSave(pref.typed_value !== false)
              break
            case 'auto_save_interval':
              setAutoSaveInterval(String(pref.typed_value || '30'))
              break
            case 'theme':
              setTheme(pref.typed_value || 'system')
              break
          }
        })
      }

      // Load Ollama models
      await loadOllamaModels()
    } catch (error) {
      console.error('Failed to load preferences:', error)
      toast({
        title: 'Error',
        description: 'Failed to load settings',
        variant: 'destructive'
      })
    } finally {
      setLoading(false)
    }
  }

  const loadOllamaModels = async () => {
    try {
      const response = await api.getOllamaModels()
      if (response.success && response.data) {
        const models = (response.data as any).data?.models || []
        setOllamaModels(models.map((m: any) => m.name))
        setOllamaConnected(true)
      } else {
        setOllamaConnected(false)
      }
    } catch (error) {
      console.error('Failed to load Ollama models:', error)
      setOllamaConnected(false)
    }
  }

  const loadAvailableVoices = async () => {
    setLoadingVoices(true)
    try {
      const response = await api.getAvailableVoices()
      if (response.success && response.data?.data?.voices) {
        setAvailableVoices(response.data.data.voices)
      }
    } catch (error) {
      console.error('Failed to load available voices:', error)
      toast({
        title: 'Error',
        description: 'Failed to load available voices',
        variant: 'destructive'
      })
    } finally {
      setLoadingVoices(false)
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

  const savePreferences = async (preferences: Array<{ key: string; value: any; value_type: string }>) => {
    setSaving(true)
    try {
      const response = await api.request('/preferences/bulk', {
        method: 'POST',
        body: JSON.stringify({ preferences })
      })

      if (response.success) {
        toast({
          title: 'Settings saved',
          description: 'Your preferences have been updated'
        })

        // Broadcast settings change to refresh other components
        window.dispatchEvent(new CustomEvent('settingsChanged', {
          detail: { voiceEnabled: preferences.find(p => p.key === 'voice_enabled')?.value }
        }))

        // Also update localStorage timestamp to force refresh
        localStorage.setItem('voiceSettingsLastUpdated', Date.now().toString())

        return true
      } else {
        throw new Error(response.error || 'Failed to save preferences')
      }
    } catch (error) {
      console.error('Failed to save preferences:', error)
      toast({
        title: 'Error',
        description: 'Failed to save settings',
        variant: 'destructive'
      })
      return false
    } finally {
      setSaving(false)
    }
  }

  const handleSaveHotkey = async () => {
    const preferences = [
      { key: 'hotkey', value: hotkey, value_type: 'string' }
    ]
    await savePreferences(preferences)
  }

  const handleSaveJournal = async () => {
    const preferences = [
      { key: 'ollama_host', value: ollamaHost, value_type: 'string' },
      { key: 'ollama_port', value: parseInt(ollamaPort), value_type: 'int' },
      { key: 'ollama_model', value: journalModel, value_type: 'string' },
      { key: 'ollama_temperature', value: parseFloat(journalTemperature), value_type: 'float' },
      { key: 'ollama_context_window', value: parseInt(journalContextWindow), value_type: 'int' }
    ]
    await savePreferences(preferences)
  }

  const handleSaveDiary = async () => {
    const preferences = [
      { key: 'talk_to_diary_model', value: diaryModel, value_type: 'string' },
      { key: 'talk_to_diary_temperature', value: parseFloat(diaryTemperature), value_type: 'float' },
      { key: 'talk_to_diary_context_window', value: parseInt(diaryContextWindow), value_type: 'int' }
    ]
    await savePreferences(preferences)
  }

  const handleSaveOllama = async () => {
    const preferences = [
      { key: 'ollama_host', value: ollamaHost, value_type: 'string' },
      { key: 'ollama_port', value: parseInt(ollamaPort), value_type: 'int' },
      { key: 'ollama_model', value: journalModel, value_type: 'string' },
      { key: 'ollama_temperature', value: parseFloat(journalTemperature), value_type: 'float' },
      { key: 'ollama_context_window', value: parseInt(journalContextWindow), value_type: 'int' },
      { key: 'talk_to_diary_model', value: diaryModel, value_type: 'string' },
      { key: 'talk_to_diary_temperature', value: parseFloat(diaryTemperature), value_type: 'float' },
      { key: 'talk_to_diary_context_window', value: parseInt(diaryContextWindow), value_type: 'int' }
    ]
    await savePreferences(preferences)
  }

  const handleSaveTTS = async () => {
    const preferences = [
      { key: 'voice_enabled', value: voiceEnabled, value_type: 'bool' },
      { key: 'tts_engine', value: ttsEngine, value_type: 'string' },
      { key: 'tts_voice', value: ttsVoice, value_type: 'string' },
      { key: 'tts_speed', value: parseFloat(ttsSpeed), value_type: 'float' },
      { key: 'tts_volume', value: parseFloat(ttsVolume), value_type: 'float' }
    ]
    await savePreferences(preferences)

    // Broadcast voice change to other components
    window.dispatchEvent(new CustomEvent('voiceSettingChanged', {
      detail: { voiceEnabled }
    }))
  }

  const handleSaveMemory = async () => {
    const preferences = [
      { key: 'memory_enabled', value: memoryEnabled, value_type: 'bool' }
    ]
    await savePreferences(preferences)

    // Dispatch event to notify other components that settings were updated
    window.dispatchEvent(new CustomEvent('settingsUpdated'))
  }

  const handleSaveGeneral = async () => {
    const preferences = [
      { key: 'auto_save', value: autoSave, value_type: 'bool' },
      { key: 'auto_save_interval', value: parseInt(autoSaveInterval), value_type: 'int' },
      { key: 'theme', value: theme, value_type: 'string' },
    ]
    await savePreferences(preferences)

    // Dispatch event to notify other components that settings were updated
    window.dispatchEvent(new CustomEvent('settingsUpdated'))
  }

  const testOllamaConnection = async () => {
    setTestingOllama(true)
    try {
      toast({
        title: 'Testing connection...',
        description: 'Connecting to Ollama service'
      })

      // Test connection using saved settings (not current form values)
      const response = await api.testOllamaConnection()

      if (response.success && response.data?.data?.service_ready) {
        setOllamaConnected(true)
        toast({
          title: 'Connection successful',
          description: response.data?.message || 'Ollama is connected and ready'
        })
        // Reload models
        await loadOllamaModels()
      } else {
        setOllamaConnected(false)
        toast({
          title: 'Connection failed',
          description: response.error || 'Unable to connect to Ollama',
          variant: 'destructive'
        })
      }
    } catch (error) {
      setOllamaConnected(false)
      toast({
        title: 'Connection failed',
        description: 'Unable to connect to Ollama',
        variant: 'destructive'
      })
    } finally {
      setTestingOllama(false)
    }
  }

  const recordHotkey = () => {
    setIsRecordingHotkey(true)

    const handleKeyDown = (e: KeyboardEvent) => {
      e.preventDefault()
      const key = e.key.toUpperCase()
      const modifiers = []

      if (e.ctrlKey) modifiers.push('Ctrl')
      if (e.altKey) modifiers.push('Alt')
      if (e.shiftKey) modifiers.push('Shift')

      let hotkeyString = ''
      if (modifiers.length > 0) {
        hotkeyString = modifiers.join('+') + '+' + key
      } else if (key.startsWith('F') && !isNaN(parseInt(key.substring(1)))) {
        hotkeyString = key
      } else {
        hotkeyString = modifiers.length > 0 ? modifiers.join('+') + '+' + key : key
      }

      setHotkey(hotkeyString)
      setIsRecordingHotkey(false)
      document.removeEventListener('keydown', handleKeyDown)
    }

    document.addEventListener('keydown', handleKeyDown)
  }

  const handleTabChange = (tabValue: string) => {
    setSearchParams({ tab: tabValue })
  }

  // Logout function
  const handleLogout = async () => {
    try {
      await api.logoutUser()
      localStorage.removeItem('session_token')

      // Dispatch logout event to trigger AuthGuard update
      window.dispatchEvent(new CustomEvent('auth-logout'))

      toast({
        title: 'Logged out',
        description: 'You have been logged out successfully'
      })
    } catch (error) {
      console.error('Logout failed:', error)
      // Even if API call fails, clear local session and redirect
      localStorage.removeItem('session_token')
      window.dispatchEvent(new CustomEvent('auth-logout'))
    }
  }

  // User settings state  
  const [currentPasswordForChange, setCurrentPasswordForChange] = useState('')
  const [currentPasswordForPhrase, setCurrentPasswordForPhrase] = useState('')
  const [currentPasswordForKey, setCurrentPasswordForKey] = useState('')
  const [showCurrentPassword, setShowCurrentPassword] = useState(false)
  const [showNewPassword, setShowNewPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [showPhrasePassword, setShowPhrasePassword] = useState(false)
  const [showKeyPassword, setShowKeyPassword] = useState(false)
  const [keyPasswordVerified, setKeyPasswordVerified] = useState(false)

  // Handle password change
  const handleChangePassword = async () => {
    if (newPassword !== confirmPassword) {
      toast({
        title: 'Error',
        description: 'Passwords do not match',
        variant: 'destructive'
      })
      return
    }

    if (newPassword.length < 8) {
      toast({
        title: 'Error',
        description: 'Password must be at least 8 characters long',
        variant: 'destructive'
      })
      return
    }

    if (!currentPasswordForChange) {
      toast({
        title: 'Error',
        description: 'Current password is required',
        variant: 'destructive'
      })
      return
    }

    setSaving(true)
    try {
      const response = await api.changePassword({
        current_password: currentPasswordForChange,
        new_password: newPassword
      })

      if (response.success) {
        toast({
          title: 'Password changed',
          description: 'Your password has been updated successfully'
        })
        setChangingPassword(false)
        setNewPassword('')
        setConfirmPassword('')
        setCurrentPasswordForChange('')
      } else {
        toast({
          title: 'Error',
          description: response.error || 'Failed to change password',
          variant: 'destructive'
        })
      }
    } catch (error) {
      console.error('Failed to change password:', error)
      toast({
        title: 'Error',
        description: 'Failed to change password',
        variant: 'destructive'
      })
    } finally {
      setSaving(false)
    }
  }

  // Handle recovery phrase change
  const handleChangeRecoveryPhrase = async () => {
    if (!newRecoveryPhrase.trim() || newRecoveryPhrase.length < 10) {
      toast({
        title: 'Error',
        description: 'Recovery phrase must be at least 10 characters long',
        variant: 'destructive'
      })
      return
    }

    if (!currentPasswordForPhrase) {
      toast({
        title: 'Error',
        description: 'Current password is required',
        variant: 'destructive'
      })
      return
    }

    setSaving(true)
    try {
      const response = await api.changeRecoveryPhrase({
        current_password: currentPasswordForPhrase,
        new_recovery_phrase: newRecoveryPhrase
      })

      if (response.success) {
        toast({
          title: 'Recovery phrase changed',
          description: 'Your recovery phrase has been updated successfully'
        })
        setChangingPhrase(false)
        setNewRecoveryPhrase('')
        setCurrentPasswordForPhrase('')
      } else {
        toast({
          title: 'Error',
          description: response.error || 'Failed to change recovery phrase',
          variant: 'destructive'
        })
      }
    } catch (error) {
      console.error('Failed to change recovery phrase:', error)
      toast({
        title: 'Error',
        description: 'Failed to change recovery phrase',
        variant: 'destructive'
      })
    } finally {
      setSaving(false)
    }
  }

  // Verify password for emergency key
  const verifyKeyPassword = async () => {
    if (!currentPasswordForKey) {
      return
    }

    try {
      // Verify password
      const credentialsResponse = await api.getUserCredentials(currentPasswordForKey)
      if (credentialsResponse.success) {
        setKeyPasswordVerified(true)
      } else {
        setKeyPasswordVerified(false)
      }
    } catch (error) {
      setKeyPasswordVerified(false)
    }
  }

  // Download current user's emergency recovery key
  const downloadEmergencyKey = async () => {
    try {
      // Get current user's session info
      const sessionResponse = await api.getSessionInfo()
      if (!sessionResponse.success || !sessionResponse.data?.user) {
        throw new Error('Failed to get user information')
      }

      const user = sessionResponse.data.user

      // Verify password and get the ACTUAL emergency key
      const credentialsResponse = await api.getUserCredentials(currentPasswordForKey)
      if (!credentialsResponse.success) {
        toast({
          title: 'Error',
          description: 'Invalid password',
          variant: 'destructive'
        })
        setKeyPasswordVerified(false)
        return
      }

      // Get the ACTUAL emergency key from signup (not a fake generated one)
      const actualEmergencyKey = (credentialsResponse.data as any).emergency_key
      if (!actualEmergencyKey) {
        toast({
          title: 'Error',
          description: 'Emergency key not found',
          variant: 'destructive'
        })
        return
      }

      // Create the emergency key file content with the ACTUAL key
      const keyData = {
        type: 'boo_emergency_key',
        key: actualEmergencyKey,
        created: new Date().toISOString(),
        username: user.username,
        name: user.display_name
      }

      const content = JSON.stringify(keyData, null, 2)
      const blob = new Blob([content], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${user.username}_recovery_${Date.now()}.boounlock`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)

      setCurrentPasswordForKey('')
      setKeyPasswordVerified(false)
      toast({
        title: 'Emergency key downloaded',
        description: 'Your emergency recovery key has been downloaded',
      })
    } catch (error) {
      console.error('Failed to download emergency key:', error)
      toast({
        title: 'Error',
        description: 'Failed to download emergency key',
        variant: 'destructive'
      })
    }
  }

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto p-8">
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col p-4 md:p-6">
      <div className="max-w-5xl mx-auto w-full flex flex-col flex-1">
        {/* Header */}
        <div className="mb-4">
          <h2 className="text-2xl font-bold text-white mb-1">Settings</h2>
          <p className="text-gray-400 text-sm">
            Configure your Boo journal preferences
          </p>
        </div>

        <Tabs value={currentTab} onValueChange={handleTabChange} className="flex-1 flex flex-col">
          <TabsList className="grid w-full max-w-3xl grid-cols-6 mb-4 bg-card/50 backdrop-blur-sm border border-border/50 flex-shrink-0">
            <TabsTrigger value="general" className="flex items-center gap-2 data-[state=active]:bg-primary/10 data-[state=active]:text-primary">
              <Settings2 className="h-4 w-4" />
              <span className="hidden sm:inline">General</span>
            </TabsTrigger>
            <TabsTrigger value="user" className="flex items-center gap-2 data-[state=active]:bg-primary/10 data-[state=active]:text-primary">
              <User className="h-4 w-4" />
              <span className="hidden sm:inline">User</span>
            </TabsTrigger>
            <TabsTrigger value="hotkey" className="flex items-center gap-2 data-[state=active]:bg-primary/10 data-[state=active]:text-primary">
              <Keyboard className="h-4 w-4" />
              <span className="hidden sm:inline">Hotkey</span>
            </TabsTrigger>
            <TabsTrigger value="ollama" className="flex items-center gap-2 data-[state=active]:bg-primary/10 data-[state=active]:text-primary">
              <Globe className="h-4 w-4" />
              <span className="hidden sm:inline">Ollama</span>
            </TabsTrigger>
            <TabsTrigger value="tts" className="flex items-center gap-2 data-[state=active]:bg-primary/10 data-[state=active]:text-primary">
              <Mic className="h-4 w-4" />
              <span className="hidden sm:inline">Voice</span>
            </TabsTrigger>
            <TabsTrigger value="memory" className="flex items-center gap-2 data-[state=active]:bg-primary/10 data-[state=active]:text-primary">
              <Brain className="h-4 w-4" />
              <span className="hidden sm:inline">Memory</span>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="general" className="flex-1 overflow-hidden">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
            >
              <Card className="bg-card/50 backdrop-blur-sm border-border/50 h-full flex flex-col overflow-hidden">
                <CardHeader className="pb-2 flex-shrink-0">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center flex-shrink-0">
                      <Settings2 className="h-4 w-4 text-white" />
                    </div>
                    <div className="min-w-0">
                      <CardTitle className="text-base text-white">General Settings</CardTitle>
                      <CardDescription className="text-gray-400 text-xs">
                        Configure general application preferences
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="flex-1 overflow-y-auto space-y-3 p-3">
                  {/* Auto-save Setting */}
                  <div className="bg-muted/10 rounded-lg p-3 border border-border/50">
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <Label htmlFor="auto-save" className="text-white font-medium">Auto-save entries</Label>
                        <p className="text-sm text-gray-400 mt-1">
                          Automatically save entries while typing
                        </p>
                      </div>
                      <Switch
                        id="auto-save"
                        checked={autoSave}
                        onCheckedChange={setAutoSave}
                        className="data-[state=checked]:bg-primary"
                      />
                    </div>

                    {autoSave && (
                      <div className="mt-4 space-y-2">
                        <Label htmlFor="auto-save-interval" className="text-white font-medium">Auto-save interval</Label>
                        <div className="flex items-center gap-3">
                          <Input
                            id="auto-save-interval"
                            type="number"
                            min="10"
                            max="300"
                            value={autoSaveInterval}
                            onChange={(e) => setAutoSaveInterval(e.target.value)}
                            className="w-24 bg-background/50 border-border text-white placeholder:text-gray-500"
                          />
                          <span className="text-sm text-gray-400">seconds</span>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Theme Setting */}
                  <div className="bg-muted/10 rounded-lg p-3 border border-border/50">
                    <Label htmlFor="theme" className="text-white font-medium mb-2 block">Theme</Label>
                    <div className="bg-gradient-to-br from-purple-500/10 to-pink-500/10 border border-purple-500/20 rounded-lg p-4">
                      <div className="flex items-start gap-3">
                        <Palette className="h-4 w-4 text-purple-400 mt-0.5 flex-shrink-0" />
                        <p className="text-sm text-purple-300">
                          Coming Soon - We're working on beautiful theme options for Boo
                        </p>
                      </div>
                    </div>
                  </div>


                  {/* Save Button */}
                  <div className="flex justify-end pt-2">
                    <button
                      onClick={handleSaveGeneral}
                      disabled={saving}
                      className="relative overflow-hidden group px-5 py-2 rounded-lg font-medium shadow-lg hover:shadow-xl hover:scale-[1.02] transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-secondary/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                      <span className="relative z-10 flex items-center font-medium">
                        {saving ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Saving...
                          </>
                        ) : (
                          'Save Settings'
                        )}
                      </span>
                    </button>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          </TabsContent>

          <TabsContent value="user" className="flex-1 overflow-hidden">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
            >
              <Card className="bg-card/50 backdrop-blur-sm border-border/50 h-full flex flex-col overflow-hidden">
                <CardHeader className="pb-2 flex-shrink-0">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center flex-shrink-0">
                      <User className="h-4 w-4 text-white" />
                    </div>
                    <div className="min-w-0">
                      <CardTitle className="text-base text-white">User Settings</CardTitle>
                      <CardDescription className="text-gray-400 text-xs">
                        Manage your account and security settings
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="flex-1 overflow-y-auto space-y-3 p-3">

                  {/* Account Information */}
                  <div className="bg-muted/10 rounded-lg p-3 border border-border/50">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="username" className="text-white font-medium">Username</Label>
                      <span className="text-gray-300 text-sm">{userName}</span>
                    </div>
                  </div>

                  {/* Password */}
                  <div className="bg-muted/10 rounded-lg p-3 border border-border/50">
                    {!changingPassword ? (
                      <div className="flex items-center justify-between">
                        <Label htmlFor="password" className="text-white font-medium">Password</Label>
                        <button
                          onClick={() => setChangingPassword(true)}
                          className="relative overflow-hidden group px-3 py-1.5 rounded-md font-medium shadow hover:shadow-lg hover:scale-[1.01] transition-all duration-200 cursor-pointer inline-flex items-center justify-center bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
                        >
                          <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-secondary/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                          <span className="relative z-10 font-medium">Change</span>
                        </button>
                      </div>
                    ) : (
                      <div>
                        <Label htmlFor="password" className="text-white font-medium mb-3 block">Password</Label>
                        <div className="space-y-2">
                          <div className="relative">
                            <Input
                              type={showCurrentPassword ? "text" : "password"}
                              value={currentPasswordForChange}
                              onChange={(e) => setCurrentPasswordForChange(e.target.value)}
                              placeholder="Current password"
                              className="bg-background/50 border-border text-white text-sm placeholder:text-gray-500 pr-10"
                            />
                            <button
                              type="button"
                              onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
                            >
                              {showCurrentPassword ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                            </button>
                          </div>
                          <div className="relative">
                            <Input
                              type={showNewPassword ? "text" : "password"}
                              value={newPassword}
                              onChange={(e) => setNewPassword(e.target.value)}
                              placeholder="New password"
                              className="bg-background/50 border-border text-white text-sm placeholder:text-gray-500 pr-10"
                            />
                            <button
                              type="button"
                              onClick={() => setShowNewPassword(!showNewPassword)}
                              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
                            >
                              {showNewPassword ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                            </button>
                          </div>
                          <div className="relative">
                            <Input
                              type={showConfirmPassword ? "text" : "password"}
                              value={confirmPassword}
                              onChange={(e) => setConfirmPassword(e.target.value)}
                              placeholder="Confirm new password"
                              className="bg-background/50 border-border text-white text-sm placeholder:text-gray-500 pr-10"
                            />
                            <button
                              type="button"
                              onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
                            >
                              {showConfirmPassword ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                            </button>
                          </div>
                          <div className="flex justify-end gap-2">
                            <button
                              onClick={() => {
                                setChangingPassword(false)
                                setNewPassword('')
                                setConfirmPassword('')
                                setCurrentPasswordForChange('')
                              }}
                              className="px-2 py-1.5 text-sm text-gray-400 hover:text-white bg-muted/20 hover:bg-muted/30 border border-border/50 rounded-md"
                            >
                              Cancel
                            </button>
                            <button
                              onClick={handleChangePassword}
                              disabled={saving || !currentPasswordForChange || !newPassword || !confirmPassword}
                              className="relative overflow-hidden group px-3 py-1.5 rounded-md font-medium shadow hover:shadow-lg hover:scale-[1.01] transition-all duration-200 cursor-pointer inline-flex items-center justify-center bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
                            >
                              <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-secondary/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                              <span className="relative z-10 flex items-center font-medium">
                                {saving ? (
                                  <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Saving...
                                  </>
                                ) : (
                                  'Save Settings'
                                )}
                              </span>
                            </button>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Recovery Phrase */}
                  <div className="bg-muted/10 rounded-lg p-3 border border-border/50">
                    {!changingPhrase ? (
                      <div className="flex items-center justify-between">
                        <Label htmlFor="passphrase" className="text-white font-medium">Recovery Phrase</Label>
                        <button
                          onClick={() => setChangingPhrase(true)}
                          className="relative overflow-hidden group px-3 py-1.5 rounded-md font-medium shadow hover:shadow-lg hover:scale-[1.01] transition-all duration-200 cursor-pointer inline-flex items-center justify-center bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
                        >
                          <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-secondary/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                          <span className="relative z-10 font-medium">Change</span>
                        </button>
                      </div>
                    ) : (
                      <div>
                        <Label htmlFor="passphrase" className="text-white font-medium mb-3 block">Recovery Phrase</Label>
                        <div className="space-y-2">
                          <div className="relative">
                            <Input
                              type={showPhrasePassword ? "text" : "password"}
                              value={currentPasswordForPhrase}
                              onChange={(e) => setCurrentPasswordForPhrase(e.target.value)}
                              placeholder="Current password"
                              className="bg-background/50 border-border text-white text-sm placeholder:text-gray-500 pr-10"
                            />
                            <button
                              type="button"
                              onClick={() => setShowPhrasePassword(!showPhrasePassword)}
                              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
                            >
                              {showPhrasePassword ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                            </button>
                          </div>
                          <textarea
                            rows={3}
                            value={newRecoveryPhrase}
                            onChange={(e) => setNewRecoveryPhrase(e.target.value)}
                            placeholder="New recovery phrase"
                            className="w-full bg-background/50 border border-border rounded-md text-white text-sm placeholder:text-gray-500 resize-none px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary/50"
                          />
                          <div className="flex justify-end gap-2">
                            <button
                              onClick={() => {
                                setChangingPhrase(false)
                                setNewRecoveryPhrase('')
                                setCurrentPasswordForPhrase('')
                              }}
                              className="px-2 py-1.5 text-sm text-gray-400 hover:text-white bg-muted/20 hover:bg-muted/30 border border-border/50 rounded-md"
                            >
                              Cancel
                            </button>
                            <button
                              onClick={handleChangeRecoveryPhrase}
                              disabled={saving || !currentPasswordForPhrase || !newRecoveryPhrase.trim()}
                              className="relative overflow-hidden group px-3 py-1.5 rounded-md font-medium shadow hover:shadow-lg hover:scale-[1.01] transition-all duration-200 cursor-pointer inline-flex items-center justify-center bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
                            >
                              <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-secondary/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                              <span className="relative z-10 flex items-center font-medium">
                                {saving ? (
                                  <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Saving...
                                  </>
                                ) : (
                                  'Save Settings'
                                )}
                              </span>
                            </button>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Emergency Recovery Key */}
                  <div className="bg-muted/10 rounded-lg p-3 border border-border/50">
                    <Label htmlFor="emergency-key" className="text-white font-medium mb-3 block">Emergency Recovery Key</Label>
                    <div className="space-y-2">
                      <div className="relative">
                        <Input
                          type={showKeyPassword ? "text" : "password"}
                          value={currentPasswordForKey}
                          onChange={(e) => {
                            setCurrentPasswordForKey(e.target.value)
                            setKeyPasswordVerified(false) // Reset verification when password changes
                          }}
                          onBlur={verifyKeyPassword} // Verify when user finishes typing
                          placeholder="Enter password to download"
                          className="bg-background/50 border-border text-white text-sm placeholder:text-gray-500 pr-10"
                        />
                        <button
                          type="button"
                          onClick={() => setShowKeyPassword(!showKeyPassword)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
                        >
                          {showKeyPassword ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                        </button>
                      </div>
                      {keyPasswordVerified && (
                        <div className="flex justify-end">
                          <button
                            onClick={downloadEmergencyKey}
                            className="relative overflow-hidden group px-3 py-1.5 rounded-md font-medium shadow hover:shadow-lg hover:scale-[1.01] transition-all duration-200 cursor-pointer inline-flex items-center justify-center bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 text-sm"
                          >
                            <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-secondary/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                            <span className="relative z-10 font-medium">Download Recovery Key</span>
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Session Management */}
                  <div className="bg-muted/10 rounded-lg p-3 border border-border/50">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="session" className="text-white font-medium">Session</Label>
                      <button
                        onClick={handleLogout}
                        className="relative overflow-hidden group px-3 py-1.5 rounded-md font-medium shadow hover:shadow-lg hover:scale-[1.01] transition-all duration-200 cursor-pointer inline-flex items-center justify-center bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
                      >
                        <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-secondary/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                        <span className="relative z-10 font-medium">Logout</span>
                      </button>
                    </div>
                  </div>

                  {/* Save Button */}
                  <div className="flex justify-end pt-2">
                    <button
                      onClick={handleSaveGeneral}
                      disabled={saving}
                      className="relative overflow-hidden group px-3 py-1.5 rounded-md font-medium shadow hover:shadow-lg hover:scale-[1.01] transition-all duration-200 cursor-pointer inline-flex items-center justify-center bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
                    >
                      <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-secondary/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                      <span className="relative z-10 flex items-center font-medium">
                        {saving ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Saving...
                          </>
                        ) : (
                          'Save Settings'
                        )}
                      </span>
                    </button>
                  </div>

                </CardContent>
              </Card>
            </motion.div>
          </TabsContent>

          <TabsContent value="hotkey" className="flex-1 overflow-hidden">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
            >
              <Card className="bg-card/50 backdrop-blur-sm border-border/50 h-full flex flex-col overflow-hidden">
                <CardHeader className="pb-2 flex-shrink-0">
                  <div className="flex items-center gap-2">
                    <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center flex-shrink-0">
                      <Keyboard className="h-4 w-4 text-white" />
                    </div>
                    <div className="min-w-0">
                      <CardTitle className="text-lg text-white">Hotkey Configuration</CardTitle>
                      <CardDescription className="text-gray-400 text-sm">
                        Configure the global hotkey for voice recording
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="flex-1 overflow-y-auto space-y-4 p-4">
                  {/* Hotkey Setting */}
                  <div className="bg-muted/10 rounded-lg p-4 border border-border/50">
                    <Label htmlFor="hotkey" className="text-white font-medium mb-3 block">Recording Hotkey</Label>
                    <div className="flex gap-3 mb-3">
                      <Input
                        id="hotkey"
                        value={hotkey}
                        readOnly
                        className="flex-1 font-mono bg-background/50 border-border text-white placeholder:text-gray-500"
                        placeholder="Press Change to set hotkey"
                      />
                      <button
                        onClick={recordHotkey}
                        disabled={isRecordingHotkey}
                        className={`relative overflow-hidden group px-4 py-2 rounded-lg font-medium shadow-lg hover:shadow-xl hover:scale-[1.02] transition-all duration-300 cursor-pointer inline-flex items-center justify-center w-32 ${isRecordingHotkey
                            ? 'bg-red-500/20 border border-red-500/30 text-red-500 animate-pulse'
                            : 'bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20'
                          }`}
                      >
                        <span className="relative z-10 text-center font-medium">
                          {isRecordingHotkey ? 'Press any key...' : 'Change'}
                        </span>
                      </button>
                    </div>
                    <p className="text-sm text-gray-400">
                      Press and hold this key to start recording your voice
                    </p>
                  </div>

                  {/* Save Button */}
                  <div className="flex justify-end pt-2">
                    <button
                      onClick={handleSaveHotkey}
                      disabled={saving}
                      className="relative overflow-hidden group px-5 py-2 rounded-lg font-medium shadow-lg hover:shadow-xl hover:scale-[1.02] transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-secondary/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                      <span className="relative z-10 flex items-center font-medium">
                        {saving ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Saving...
                          </>
                        ) : (
                          'Save Settings'
                        )}
                      </span>
                    </button>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          </TabsContent>

          <TabsContent value="ollama" className="flex-1">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
            >
              <Card className="bg-card/50 backdrop-blur-sm border-border/50">
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center flex-shrink-0">
                      <Globe className="h-4 w-4 text-white" />
                    </div>
                    <div className="min-w-0">
                      <CardTitle className="text-base text-white">Ollama Configuration</CardTitle>
                      <CardDescription className="text-gray-400 text-xs">
                        Configure Ollama server connection and AI models
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4 p-3">

                  {/* Connection Section */}
                  <div className="bg-muted/10 rounded-lg p-3 border border-border/50">
                    <h3 className="text-white font-medium mb-3 text-sm flex items-center gap-2">
                      <Globe className="h-4 w-4 text-blue-500" />
                      Connection
                    </h3>
                    <div className="grid grid-cols-2 gap-3 mb-3">
                      <div className="space-y-1">
                        <Label htmlFor="ollama-host" className="text-white font-medium text-sm">Host</Label>
                        <Input
                          id="ollama-host"
                          value={ollamaHost}
                          onChange={(e) => setOllamaHost(e.target.value)}
                          placeholder="localhost"
                          className="bg-background/50 border-border text-white placeholder:text-gray-500 h-9"
                        />
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor="ollama-port" className="text-white font-medium text-sm">Port</Label>
                        <Input
                          id="ollama-port"
                          type="number"
                          value={ollamaPort}
                          onChange={(e) => setOllamaPort(e.target.value)}
                          placeholder="11434"
                          className="bg-background/50 border-border text-white placeholder:text-gray-500 h-9"
                        />
                      </div>
                    </div>

                    {/* Test Connection */}
                    <div className="flex items-center gap-3">
                      <button
                        onClick={testOllamaConnection}
                        disabled={testingOllama}
                        className="relative overflow-hidden group px-3 py-1.5 rounded-md font-medium shadow hover:shadow-lg hover:scale-[1.02] transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
                      >
                        <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-secondary/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                        <span className="relative z-10 flex items-center font-medium">
                          {testingOllama ? (
                            <>
                              <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                              Testing...
                            </>
                          ) : (
                            'Test Connection'
                          )}
                        </span>
                      </button>
                      {ollamaConnected !== null && (
                        <div className="flex items-center gap-2">
                          {ollamaConnected ? (
                            <>
                              <CheckCircle2 className="h-4 w-4 text-green-500" />
                              <span className="text-sm text-green-500 font-medium">Connected</span>
                            </>
                          ) : (
                            <>
                              <XCircle className="h-4 w-4 text-red-500" />
                              <span className="text-sm text-red-500 font-medium">Not connected</span>
                            </>
                          )}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Processing Model Section */}
                  {ollamaConnected && ollamaModels.length > 0 && (
                    <div className="bg-muted/10 rounded-lg p-3 border border-border/50">
                      <h3 className="text-white font-medium mb-3 text-sm flex items-center gap-2">
                        <FileText className="h-4 w-4 text-emerald-500" />
                        Processing Model
                      </h3>

                      {/* Journal Model */}
                      <div className="space-y-1 mb-3">
                        <Select value={journalModel} onValueChange={setJournalModel}>
                          <SelectTrigger className="bg-background/50 border-border text-white hover:bg-muted/50 h-9">
                            <SelectValue placeholder="Select a model" />
                          </SelectTrigger>
                          <SelectContent className="bg-background border-border">
                            {ollamaModels.map((model) => (
                              <SelectItem key={model} value={model} className="text-white hover:bg-muted/50 focus:bg-muted/50">
                                {model}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <p className="text-xs text-gray-400">
                          Model for raw → enhanced → structured processing (fast model like mistral:7b recommended)
                        </p>
                      </div>

                      {/* Model Parameters */}
                      <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1">
                          <Label htmlFor="journal-temperature" className="text-white font-medium text-sm">Temperature</Label>
                          <div className="flex items-center gap-2">
                            <Slider
                              id="journal-temperature"
                              min={0}
                              max={1}
                              step={0.1}
                              value={[parseFloat(journalTemperature)]}
                              onValueChange={(value) => setJournalTemperature(value[0].toString())}
                              className="flex-1 [&>*:first-child]:bg-muted/30 [&>*:first-child]:border-border/50"
                            />
                            <span className="w-10 text-sm text-white font-mono bg-background/50 px-1.5 py-0.5 rounded">
                              {journalTemperature}
                            </span>
                          </div>
                          <p className="text-xs text-gray-400">
                            0 = focused, 1 = creative
                          </p>
                        </div>

                        <div className="space-y-1">
                          <Label htmlFor="journal-context" className="text-white font-medium text-sm">Context Window</Label>
                          <Select value={journalContextWindow} onValueChange={setJournalContextWindow}>
                            <SelectTrigger className="bg-background/50 border-border text-white hover:bg-muted/50 h-9">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="bg-background border-border">
                              <SelectItem value="2048" className="text-white hover:bg-muted/50 focus:bg-muted/50">2048 tokens</SelectItem>
                              <SelectItem value="4096" className="text-white hover:bg-muted/50 focus:bg-muted/50">4096 tokens</SelectItem>
                              <SelectItem value="8192" className="text-white hover:bg-muted/50 focus:bg-muted/50">8192 tokens</SelectItem>
                              <SelectItem value="16384" className="text-white hover:bg-muted/50 focus:bg-muted/50">16384 tokens</SelectItem>
                              <SelectItem value="32768" className="text-white hover:bg-muted/50 focus:bg-muted/50">32768 tokens</SelectItem>
                            </SelectContent>
                          </Select>
                          <p className="text-xs text-gray-400">
                            Max entry length
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Talk to Boo Model Section */}
                  {ollamaConnected && ollamaModels.length > 0 && (
                    <div className="bg-muted/10 rounded-lg p-3 border border-border/50">
                      <h3 className="text-white font-medium mb-3 text-sm flex items-center gap-2">
                        <MessageSquare className="h-4 w-4 text-purple-500" />
                        Talk to Boo Model
                      </h3>

                      {/* Diary Chat Model */}
                      <div className="space-y-1 mb-3">
                        <Select value={diaryModel} onValueChange={setDiaryModel}>
                          <SelectTrigger className="bg-background/50 border-border text-white hover:bg-muted/50 h-9">
                            <SelectValue placeholder="Select a model" />
                          </SelectTrigger>
                          <SelectContent className="bg-background border-border">
                            {ollamaModels.map((model) => (
                              <SelectItem key={model} value={model} className="text-white hover:bg-muted/50 focus:bg-muted/50">
                                {model}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <p className="text-xs text-gray-400">
                          Model for diary conversations (thinking models like qwen3:8b recommended)
                        </p>
                      </div>

                      {/* Model Parameters */}
                      <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1">
                          <Label htmlFor="diary-temperature" className="text-white font-medium text-sm">Temperature</Label>
                          <div className="flex items-center gap-2">
                            <Slider
                              id="diary-temperature"
                              min={0}
                              max={1}
                              step={0.1}
                              value={[parseFloat(diaryTemperature)]}
                              onValueChange={(value) => setDiaryTemperature(value[0].toString())}
                              className="flex-1 [&>*:first-child]:bg-muted/30 [&>*:first-child]:border-border/50"
                            />
                            <span className="w-10 text-sm text-white font-mono bg-background/50 px-1.5 py-0.5 rounded">
                              {diaryTemperature}
                            </span>
                          </div>
                          <p className="text-xs text-gray-400">
                            0 = focused, 1 = creative
                          </p>
                        </div>

                        <div className="space-y-1">
                          <Label htmlFor="diary-context" className="text-white font-medium text-sm">Context Window</Label>
                          <Select value={diaryContextWindow} onValueChange={setDiaryContextWindow}>
                            <SelectTrigger className="bg-background/50 border-border text-white hover:bg-muted/50 h-9">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="bg-background border-border">
                              <SelectItem value="2048" className="text-white hover:bg-muted/50 focus:bg-muted/50">2048 tokens</SelectItem>
                              <SelectItem value="4096" className="text-white hover:bg-muted/50 focus:bg-muted/50">4096 tokens</SelectItem>
                              <SelectItem value="8192" className="text-white hover:bg-muted/50 focus:bg-muted/50">8192 tokens</SelectItem>
                              <SelectItem value="16384" className="text-white hover:bg-muted/50 focus:bg-muted/50">16384 tokens</SelectItem>
                              <SelectItem value="32768" className="text-white hover:bg-muted/50 focus:bg-muted/50">32768 tokens</SelectItem>
                            </SelectContent>
                          </Select>
                          <p className="text-xs text-gray-400">
                            Max conversation length
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Save Button */}
                  <div className="flex justify-end pt-2">
                    <button
                      onClick={handleSaveOllama}
                      disabled={saving}
                      className="relative overflow-hidden group px-5 py-2 rounded-lg font-medium shadow-lg hover:shadow-xl hover:scale-[1.02] transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-secondary/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                      <span className="relative z-10 flex items-center font-medium">
                        {saving ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Saving...
                          </>
                        ) : (
                          'Save Settings'
                        )}
                      </span>
                    </button>
                  </div>

                </CardContent>
              </Card>
            </motion.div>
          </TabsContent>

          <TabsContent value="tts" className="flex-1">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
            >
              <Card className="bg-card/50 backdrop-blur-sm border-border/50">
                <CardHeader className="pb-4">
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center">
                      <Mic className="h-5 w-5 text-white" />
                    </div>
                    <div>
                      <CardTitle className="text-xl text-white">Text-to-Speech Configuration</CardTitle>
                      <CardDescription className="text-gray-400 text-sm">
                        Configure voice output settings for Talk to Boo feature
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Voice Toggle Settings */}
                  <div className="bg-muted/10 rounded-lg p-4 border border-border/50">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="text-white font-medium">Voice Output</h3>
                      </div>
                      <Switch
                        checked={voiceEnabled}
                        onCheckedChange={setVoiceEnabled}
                        className="ml-4"
                      />
                    </div>
                  </div>

                  {/* TTS Engine Settings */}
                  <div className="bg-muted/10 rounded-lg p-4 border border-border/50">
                    <h3 className="text-white font-medium mb-4">Engine Configuration</h3>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                      <div className="space-y-2">
                        <Label htmlFor="tts-engine" className="text-white font-medium">TTS Engine</Label>
                        <Select value={ttsEngine} onValueChange={setTtsEngine}>
                          <SelectTrigger className="bg-background/50 border-border text-white hover:bg-muted/50">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent className="bg-background border-border">
                            <SelectItem value="piper" className="text-white hover:bg-muted/50 focus:bg-muted/50">Piper</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="tts-voice" className="text-white font-medium">Voice</Label>
                        {loadingVoices ? (
                          <div className="flex items-center justify-center h-10 bg-background/50 rounded-md border border-border">
                            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                          </div>
                        ) : availableVoices.length > 0 ? (
                          <Select value={ttsVoice} onValueChange={setTtsVoice}>
                            <SelectTrigger className="bg-background/50 border-border text-white hover:bg-muted/50">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="bg-background border-border">
                              {availableVoices.map((voice) => (
                                <SelectItem
                                  key={voice.filename}
                                  value={voice.filename}
                                  className="text-white hover:bg-muted/50 focus:bg-muted/50"
                                >
                                  {voice.name}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        ) : (
                          <div className="bg-background/50 border border-border rounded-md p-3">
                            <p className="text-sm text-gray-400">No voices found. Please add voice files to the backend/TTS directory.</p>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Info message about downloading voices */}
                    <div className="bg-gradient-to-br from-purple-500/10 to-pink-500/10 border border-purple-500/20 rounded-lg p-3 mt-4">
                      <p className="text-sm text-purple-300">
                        <strong>Note:</strong> To add more voices, <a
                          href="https://huggingface.co/rhasspy/piper-voices/tree/main/en"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-pink-400 hover:text-pink-300 underline hover:no-underline transition-colors duration-200"
                        >
                          download Piper TTS voice models
                        </a> (.onnx and .onnx.json files)
                        and place them in the <code className="bg-background/50 px-1 py-0.5 rounded">backend/TTS</code> directory.
                      </p>
                    </div>

                    {/* Voice Parameters */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                      <div className="space-y-3">
                        <Label htmlFor="tts-speed" className="text-white font-medium">Speed</Label>
                        <div className="flex items-center gap-3">
                          <Slider
                            id="tts-speed"
                            min={0}
                            max={2}
                            step={0.5}
                            value={[parseFloat(ttsSpeed)]}
                            onValueChange={(value) => setTtsSpeed(value[0].toString())}
                            className="flex-1 [&>*:first-child]:bg-muted/30 [&>*:first-child]:border-border/50"
                          />
                          <span className="w-12 text-sm text-white font-mono bg-background/50 px-2 py-1 rounded text-center">
                            {ttsSpeed}x
                          </span>
                        </div>
                        <p className="text-xs text-gray-400">
                          0x = silent, 0.5x = slow, 1x = normal, 1.5x = fast, 2x = fastest
                        </p>
                      </div>

                      <div className="space-y-3">
                        <Label htmlFor="tts-volume" className="text-white font-medium">Volume</Label>
                        <div className="flex items-center gap-3">
                          <Slider
                            id="tts-volume"
                            min={0}
                            max={1}
                            step={0.1}
                            value={[parseFloat(ttsVolume)]}
                            onValueChange={(value) => setTtsVolume(value[0].toString())}
                            className="flex-1 [&>*:first-child]:bg-muted/30 [&>*:first-child]:border-border/50"
                          />
                          <span className="w-12 text-sm text-white font-mono bg-background/50 px-2 py-1 rounded text-center">
                            {Math.round(parseFloat(ttsVolume) * 100)}%
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Save Button */}
                  <div className="flex justify-end pt-2">
                    <button
                      onClick={handleSaveTTS}
                      disabled={saving}
                      className="relative overflow-hidden group px-5 py-2 rounded-lg font-medium shadow-lg hover:shadow-xl hover:scale-[1.02] transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-secondary/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                      <span className="relative z-10 flex items-center font-medium">
                        {saving ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Saving...
                          </>
                        ) : (
                          'Save Settings'
                        )}
                      </span>
                    </button>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          </TabsContent>

          <TabsContent value="memory" className="flex-1">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
            >
              <Card className="bg-card/50 backdrop-blur-sm border-border/50">
                <CardHeader className="pb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                      <Brain className="h-5 w-5 text-white" />
                    </div>
                    <div>
                      <CardTitle className="text-xl text-white">Memory System</CardTitle>
                      <CardDescription className="text-gray-400 text-sm">
                        Configure Boo's memory system settings
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Beta Disclaimer Banner */}
                  <div className="bg-gradient-to-br from-purple-500/10 to-pink-500/10 border border-purple-500/20 rounded-lg p-4">
                    <div className="flex items-start gap-3">
                      <AlertTriangle className="h-4 w-4 text-purple-400 mt-0.5 flex-shrink-0" />
                      <p className="text-sm text-purple-300">
                        Beta Feature - The memory system is currently in beta. We're actively working to improve
                        how Boo remembers and uses information from your journal entries and conversations.
                      </p>
                    </div>
                  </div>

                  {/* Memory Toggle */}
                  <div className="bg-muted/10 rounded-lg p-4 border border-border/50">
                    <div className="flex items-center justify-between">
                      <div>
                        <Label htmlFor="memory-enabled" className="text-white font-medium">
                          Enable Memory System
                        </Label>
                        <p className="text-sm text-gray-400 mt-1">
                          Allow Boo to remember and use information from your past entries and conversations
                        </p>
                      </div>
                      <Switch
                        id="memory-enabled"
                        checked={memoryEnabled}
                        onCheckedChange={setMemoryEnabled}
                        className="data-[state=checked]:bg-primary"
                      />
                    </div>
                  </div>

                  {/* Save Button */}
                  <div className="flex justify-end pt-2">
                    <button
                      onClick={handleSaveMemory}
                      disabled={saving}
                      className="relative overflow-hidden group px-5 py-2 rounded-lg font-medium shadow-lg hover:shadow-xl hover:scale-[1.02] transition-all duration-300 cursor-pointer inline-flex items-center justify-center bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-secondary/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                      <span className="relative z-10 flex items-center font-medium">
                        {saving ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Saving...
                          </>
                        ) : (
                          'Save Settings'
                        )}
                      </span>
                    </button>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}

export default SettingsPage