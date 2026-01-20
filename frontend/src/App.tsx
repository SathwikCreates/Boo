import { Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from '@/components/ui/toaster'
import Layout from '@/components/layout/Layout'
import HomePage from '@/pages/HomePage'
import LandingPage from '@/pages/LandingPage'
import NewEntryPage from '@/pages/NewEntryPage'
import VoiceUploadPage from '@/pages/VoiceUploadPage'
import ViewEntriesPage from '@/pages/ViewEntriesPage'
import TalkToYourDiaryPage from '@/pages/TalkToYourDiaryPage'
import PatternInsightsPage from '@/pages/PatternInsightsPage'
import MemoriesPage from '@/pages/MemoriesPage'
import SettingsPage from '@/pages/SettingsPage'
import { useState, useEffect } from 'react'
import { api } from '@/lib/api'

// Authentication guard component
function AuthGuard({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null)
  const [loading, setLoading] = useState(true)

  const checkAuthStatus = async () => {
    try {
      setLoading(true)
      const response = await api.getSessionInfo()
      setIsAuthenticated(response.success && response.data?.is_authenticated === true)
    } catch (error) {
      console.error('Failed to check auth status:', error)
      setIsAuthenticated(false)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    checkAuthStatus()
  }, [])

  // Listen for authentication events
  useEffect(() => {
    const handleAuthChange = () => {
      checkAuthStatus()
    }

    const handleLogout = () => {
      setIsAuthenticated(false)
      setLoading(false)
    }

    window.addEventListener('auth-success', handleAuthChange)
    window.addEventListener('auth-logout', handleLogout)
    return () => {
      window.removeEventListener('auth-success', handleAuthChange)
      window.removeEventListener('auth-logout', handleLogout)
    }
  }, [])

  if (loading) {
    return <div className="flex items-center justify-center h-screen">Loading...</div>
  }

  if (!isAuthenticated) {
    return <LandingPage />
  }

  return <>{children}</>
}

// Protected route component for memory features
function MemoryProtectedRoute() {
  const [memoryEnabled, setMemoryEnabled] = useState<boolean | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadMemoryPreference = async () => {
      try {
        const response = await api.getPreferences()
        if (response.success && response.data) {
          const memoryPref = response.data.preferences.find((pref: any) => pref.key === 'memory_enabled')
          setMemoryEnabled(memoryPref ? memoryPref.typed_value !== false : true)
        } else {
          setMemoryEnabled(true) // Default to enabled if can't load
        }
      } catch (error) {
        console.error('Failed to load memory preference:', error)
        setMemoryEnabled(true) // Default to enabled on error
      } finally {
        setLoading(false)
      }
    }
    
    loadMemoryPreference()
  }, [])

  if (loading) {
    return <div className="flex items-center justify-center h-full">Loading...</div>
  }

  if (!memoryEnabled) {
    return <Navigate to="/" replace />
  }

  return <MemoriesPage />
}

function App() {
  return (
    <div className="min-h-screen bg-background font-sans antialiased">
      <AuthGuard>
        <Layout>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/new" element={<NewEntryPage />} />
            <Route path="/voice-upload" element={<VoiceUploadPage />} />
            <Route path="/entries" element={<ViewEntriesPage />} />
            <Route path="/talk" element={<TalkToYourDiaryPage />} />
            <Route path="/patterns" element={<PatternInsightsPage />} />
            <Route path="/memories" element={<MemoryProtectedRoute />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </Layout>
      </AuthGuard>
      <Toaster />
    </div>
  )
}

export default App