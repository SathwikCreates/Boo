import { useState, useEffect, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Calendar as CalendarComponent } from '@/components/ui/calendar'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { 
  ChevronDown, 
  ChevronUp, 
  FileText, 
  Pen, 
  BookOpen, 
  Search,
  Filter,
  Calendar,
  Clock,
  Trash2,
  Download,
  ChevronLeft,
  ChevronRight,
  Loader2,
  MoreVertical,
  X,
  Maximize2,
  Edit,
  Save,
  CheckCircle
} from 'lucide-react'
import { api } from '@/lib/api'
import { useLocation } from 'react-router-dom'

// Types for entry data
interface Entry {
  id: number
  raw_text: string
  enhanced_text?: string
  structured_summary?: string
  mode: string
  timestamp: string
  word_count: number
  processing_metadata?: any
  mood_tags?: string[]
}

// View modes for entry display
const viewModes = [
  {
    key: 'raw',
    icon: FileText,
    title: "Raw Transcription",
    description: "Your exact words, unfiltered and authentic",
    gradient: "from-blue-500 to-blue-600",
    bgColor: "bg-blue-500/10",
    borderColor: "border-blue-500/20"
  },
  {
    key: 'enhanced',
    icon: Pen,
    title: "Enhanced Style", 
    description: "Improved grammar and tone while preserving your intent",
    gradient: "from-purple-500 to-pink-500",
    bgColor: "bg-purple-500/10",
    borderColor: "border-purple-500/20"
  },
  {
    key: 'structured',
    icon: BookOpen,
    title: "Structured Summary",
    description: "Organized into coherent themes and key points", 
    gradient: "from-emerald-500 to-teal-500",
    bgColor: "bg-emerald-500/10",
    borderColor: "border-emerald-500/20"
  }
]

function ViewEntriesPage() {
  const location = useLocation()
  const [entries, setEntries] = useState<Entry[]>([])
  const [selectedEntry, setSelectedEntry] = useState<Entry | null>(null)

  // Get mood color based on sentiment (from Pattern Insights)
  const getMoodColor = (mood: string) => {
    const positiveModds = ['happy', 'excited', 'grateful', 'content', 'peaceful', 'confident', 'proud', 'hopeful', 'inspired', 'loved', 'optimistic']
    const negativeModds = ['sad', 'angry', 'frustrated', 'anxious', 'stressed', 'worried', 'disappointed', 'lonely', 'scared', 'overwhelmed']
    const neutralModds = ['tired', 'calm', 'surprised', 'confused', 'bored', 'curious', 'focused']
    
    if (positiveModds.includes(mood.toLowerCase())) {
      return 'from-green-400 to-emerald-500'
    } else if (negativeModds.includes(mood.toLowerCase())) {
      return 'from-red-400 to-pink-500'
    } else {
      return 'from-blue-400 to-purple-500'
    }
  }

  const getMoodEmoji = (mood: string) => {
    const emojiMap: { [key: string]: string } = {
      happy: '😊', sad: '😢', excited: '🤩', anxious: '😰', stressed: '😣',
      calm: '😌', angry: '😠', grateful: '🙏', tired: '😴', content: '😌',
      frustrated: '😤', peaceful: '🧘', overwhelmed: '😵', confident: '😎',
      worried: '😟', hopeful: '🌟', lonely: '😔', proud: '💪', scared: '😨',
      surprised: '😲', bored: '😑', confused: '🤔', inspired: '✨'
    }
    return emojiMap[mood.toLowerCase()] || '💭'
  }
  
  const [expandedDropdowns, setExpandedDropdowns] = useState<Set<number>>(new Set())
  const [selectedVersion, setSelectedVersion] = useState<'raw' | 'enhanced' | 'structured'>('enhanced')
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [semanticResults, setSemanticResults] = useState<Entry[]>([])
  const [isSemanticSearch, setIsSemanticSearch] = useState(false)
  // Removed: useSemanticSearch - now always uses hybrid search
  const [isRegenerating, setIsRegenerating] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [totalEntries, setTotalEntries] = useState(0)
  const [pageSize] = useState(20)
  const [deleting, setDeleting] = useState<number | null>(null)
  const [expandedView, setExpandedView] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editedContent, setEditedContent] = useState('')
  const [saving, setSaving] = useState(false)
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null)
  const [showDateFilter, setShowDateFilter] = useState(false)
  const [dateFilterType, setDateFilterType] = useState<'all' | 'before' | 'after' | 'between' | 'on' | 'last-days-months'>('all')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [showBeforeCalendar, setShowBeforeCalendar] = useState(false)
  const [showAfterCalendar, setShowAfterCalendar] = useState(false)
  const [showOnCalendar, setShowOnCalendar] = useState(false)
  const [showBetweenStartCalendar, setShowBetweenStartCalendar] = useState(false)
  const [showBetweenEndCalendar, setShowBetweenEndCalendar] = useState(false)
  const [lastPeriodValue, setLastPeriodValue] = useState(1)
  const [lastPeriodUnit, setLastPeriodUnit] = useState<'days' | 'months'>('months')
  const [deleteConfirmation, setDeleteConfirmation] = useState<{ entryId: number; entryTitle: string } | null>(null)

  // Load entries on component mount and when page changes
  useEffect(() => {
    loadEntries()
  }, [currentPage])

  // Handle auto-selection when navigating from other pages (like pattern modals)
  useEffect(() => {
    const selectedEntryId = location.state?.selectedEntryId
    
    if (selectedEntryId) {
      // Clear navigation state immediately to prevent duplicate runs
      window.history.replaceState({}, document.title)
      
      // Check if entry is in current loaded entries first
      if (entries.length > 0) {
        const entryToSelect = entries.find(entry => entry.id === selectedEntryId)
        if (entryToSelect) {
          setSelectedEntry(entryToSelect)
          return
        }
      }
      
      // Entry not in current page or no entries loaded yet, fetch directly
      const fetchSelectedEntry = async () => {
        try {
          const response = await api.getEntry(selectedEntryId)
          if (response.success && response.data) {
            setSelectedEntry(response.data)
          }
        } catch (error) {
          console.error('Failed to fetch selected entry:', error)
        }
      }
      fetchSelectedEntry()
    }
  }, [location.state?.selectedEntryId])

  // Handle preview mode from homepage cards
  useEffect(() => {
    const previewMode = location.state?.previewMode
    
    if (previewMode && entries.length > 0) {
      // Set the selected version to match the clicked mode
      setSelectedVersion(previewMode as 'raw' | 'enhanced' | 'structured')
      
      // Auto-select the latest entry for preview
      const latestEntry = entries[0] // entries are sorted by timestamp desc
      if (latestEntry) {
        setSelectedEntry(latestEntry)
      }
      
      // Clear navigation state
      window.history.replaceState({}, document.title)
    }
  }, [location.state?.previewMode, entries])

  // Reload entries when clearing search
  useEffect(() => {
    if (!searchQuery) {
      setIsSemanticSearch(false)
      setSemanticResults([])
      setCurrentPage(1)
      loadEntries()
    }
  }, [searchQuery])

  // Handle Enter key for search
  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      performSemanticSearch(searchQuery)
    }
  }
  
  // Handle search button click
  const handleSearchClick = () => {
    performSemanticSearch(searchQuery)
  }

  // Test embedding similarity function
  const testEmbeddingSimilarity = async (query: string) => {
    console.log(`🧪 TESTING EMBEDDING SIMILARITY for query: "${query}"`)
    
    try {
      // First, let's check if embeddings were really regenerated with BGE
      const dbStateResponse = await api.debugDatabaseState()
      if (dbStateResponse.success && dbStateResponse.data) {
        const dbData = dbStateResponse.data.data || dbStateResponse.data
        console.log(`📊 Database has ${dbData.entries_with_embeddings} entries with embeddings`)
      }
      
      // Perform semantic search
      const searchResponse = await api.semanticSearch(query, 10, 0.1) // Lower threshold to see more results
      
      if (searchResponse.success && searchResponse.data) {
        const searchData = searchResponse.data.data || searchResponse.data
        const results = searchData.results || []
        
        console.log(`\n🔍 SEARCH RESULTS for "${query}": Found ${results.length} matches`)
        console.log('Total searchable entries:', searchData.total_searchable_entries)
        
        results.forEach((result: any, index: number) => {
          console.log(`\n${index + 1}. Entry ${result.entry_id} - Similarity: ${(result.similarity * 100).toFixed(2)}%`)
          console.log(`   Title: ${result.title}`)
          console.log(`   Content: ${result.content.substring(0, 150)}...`)
        })
        
        // Also show what SHOULD match
        console.log(`\n📝 EXPECTED MATCHES for "${query}":`)
        console.log('- Look for entries mentioning hiking, mountains, trails, nature, walking, etc.')
        console.log('- The Raj/soccer entry should have LOW similarity for "hiking"')
        
      } else {
        console.error('Search failed:', searchResponse.error)
      }
      
    } catch (error) {
      console.error('Test failed:', error)
    }
  }

  // Debug function - temporary
  const debugEmbeddings = async () => {
    console.log('🔧 DEBUG: Enhanced BGE Embedding Analysis...')
    
    try {
      // Get all entries by fetching multiple pages
      let allEntries = []
      let currentPage = 1
      let hasMorePages = true
      
      while (hasMorePages && currentPage <= 10) { // Limit to 10 pages max
        console.log(`Fetching page ${currentPage}...`)
        const response = await api.getEntries(currentPage, 50)
        
        if (response.success && response.data) {
          allEntries.push(...response.data.entries)
          hasMorePages = response.data.has_next
          currentPage++
        } else {
          hasMorePages = false
        }
      }
      
      console.log(`Total entries fetched: ${allEntries.length}`)
      
      // Search for Raj in all entries
      const rajEntries = allEntries.filter(entry => 
        entry.raw_text.toLowerCase().includes('raj') ||
        entry.enhanced_text?.toLowerCase().includes('raj') ||
        entry.structured_summary?.toLowerCase().includes('raj')
      )
      
      console.log('📋 ENTRIES CONTAINING "RAJ":')
      rajEntries.forEach((entry, index) => {
        console.log(`\n--- Entry ${index + 1} (ID: ${entry.id}) ---`)
        console.log('Raw:', entry.raw_text)
        console.log('Enhanced:', entry.enhanced_text || 'N/A')
        console.log('Structured:', entry.structured_summary || 'N/A')
        console.log('Has embeddings:', entry.embeddings && entry.embeddings.length > 0 ? `Yes (${entry.embeddings.length}D)` : 'No')
        
        // Check which text would be used for embedding (priority order)
        let selectedText = 'None'
        if (entry.structured_summary && entry.structured_summary.trim()) {
          selectedText = `Structured: "${entry.structured_summary}"`
        } else if (entry.enhanced_text && entry.enhanced_text.trim()) {
          selectedText = `Enhanced: "${entry.enhanced_text}"`
        } else if (entry.raw_text && entry.raw_text.trim()) {
          selectedText = `Raw: "${entry.raw_text}"`
        }
        console.log('Text used for embedding:', selectedText)
      })
      
      // Test semantic search for "Raj" and show detailed results
      console.log('\n🔍 TESTING SEMANTIC SEARCH FOR "RAJ":')
      const searchResponse = await api.semanticSearch('Raj', 10, 0.1)
      
      if (searchResponse.success && searchResponse.data) {
        const results = searchResponse.data.results || []
        console.log(`Found ${results.length} semantic matches:`)
        
        results.forEach((result, index) => {
          console.log(`\nMatch ${index + 1}:`)
          console.log('- Entry ID:', result.entry_id)
          console.log('- Similarity:', `${(result.similarity * 100).toFixed(2)}%`)
          console.log('- Title:', result.title)
          console.log('- Content Preview:', result.content.substring(0, 100) + '...')
          
          // Find the full entry details
          const fullEntry = allEntries.find(e => e.id === result.entry_id)
          if (fullEntry) {
            const containsRaj = 
              fullEntry.raw_text.toLowerCase().includes('raj') ||
              fullEntry.enhanced_text?.toLowerCase().includes('raj') ||
              fullEntry.structured_summary?.toLowerCase().includes('raj')
            console.log('- Actually contains "Raj":', containsRaj ? '✅ YES' : '❌ NO')
          }
        })
        
        // Check if any Raj entries are missing from results
        const resultEntryIds = results.map(r => r.entry_id)
        const missingRajEntries = rajEntries.filter(entry => !resultEntryIds.includes(entry.id))
        
        if (missingRajEntries.length > 0) {
          console.log('\n⚠️ RAJ ENTRIES NOT IN SEARCH RESULTS:')
          missingRajEntries.forEach(entry => {
            console.log(`- Entry ${entry.id}: Has embeddings = ${entry.embeddings && entry.embeddings.length > 0}`)
          })
        }
      } else {
        console.error('Semantic search failed:', searchResponse.error)
      }
      
      if (rajEntries.length === 0) {
        console.log('❌ NO ENTRIES FOUND containing "Raj"')
        console.log('🔍 Double-check: Are you sure there is an entry with "Raj"?')
      } else {
        console.log(`✅ FOUND ${rajEntries.length} entries containing "Raj":`)
        
        rajEntries.forEach(entry => {
          const hasEmbeddings = entry.embeddings && entry.embeddings.length > 0
          const rawContainsRaj = entry.raw_text.toLowerCase().includes('raj')
          const enhancedContainsRaj = entry.enhanced_text?.toLowerCase().includes('raj')
          const structuredContainsRaj = entry.structured_summary?.toLowerCase().includes('raj')
          
          console.log(`\n📝 Entry ${entry.id}: ${hasEmbeddings ? '✅ INDEXED' : '❌ NO EMBEDDINGS'}`)
          console.log(`Raw contains "Raj": ${rawContainsRaj}`)
          console.log(`Enhanced contains "Raj": ${enhancedContainsRaj}`)
          console.log(`Structured contains "Raj": ${structuredContainsRaj}`)
          console.log(`Raw: "${entry.raw_text.substring(0, 100)}..."`)
          if (entry.enhanced_text) console.log(`Enhanced: "${entry.enhanced_text.substring(0, 100)}..."`)
          if (entry.structured_summary) console.log(`Structured: "${entry.structured_summary.substring(0, 100)}..."`)
          console.log('---')
        })
      }
      
    } catch (error) {
      console.error('Debug search failed:', error)
    }
  }

  // Regenerate all embeddings with BGE improvements
  const regenerateAllEmbeddings = async () => {
    console.log('🔄 Starting complete embedding regeneration with BGE improvements...')
    
    try {
      const response = await api.regenerateAllEmbeddings()
      
      if (response.success) {
        console.log('✅ Regeneration started successfully!')
        console.log('📝 Status:', response.data?.message)
        console.log('🗑️ Embeddings cleared:', response.data?.embeddings_cleared || 0)
        console.log('⏱️ Estimated time:', response.data?.estimated_time)
        console.log('🔄 This will regenerate ALL embeddings with:')
        console.log('  • Proper BGE document formatting')
        console.log('  • Text prioritization (structured > enhanced > raw)')
        console.log('  • Improved semantic search quality')
        console.log('\n📊 Monitoring progress...')
        
        // Set regenerating state to show processing badges
        setIsRegenerating(true)
        
        // Poll for status updates
        const pollStatus = async () => {
          try {
            const statusResponse = await api.getRegenerationStatus()
            if (statusResponse.success && statusResponse.data) {
              const status = statusResponse.data
              
              if (status.is_running) {
                console.log(`🔄 Progress: ${status.progress}/${status.total} (${status.percentage}%) - ${status.current_step}`)
                
                // Show recent logs
                if (status.logs && status.logs.length > 0) {
                  const recentLogs = status.logs.slice(-5) // Show last 5 logs
                  recentLogs.forEach((log: string) => console.log(`  ${log}`))
                }
                
                // Continue polling every 2 seconds
                setTimeout(pollStatus, 2000)
              } else {
                console.log('🎉 Regeneration completed!')
                console.log('📊 Final status:')
                console.log(`Progress: ${status.progress}/${status.total}`)
                
                if (status.logs && status.logs.length > 0) {
                  console.log('\n📜 REGENERATION LOGS:')
                  status.logs.forEach((log: string) => console.log(log))
                } else {
                  console.log('⚠️ No logs available from regeneration process')
                }
                
                // Clear regenerating state and refresh entries
                setIsRegenerating(false)
                console.log('🔄 Refreshing entries list...')
                loadEntries()
              }
            }
          } catch (error) {
            console.error('❌ Status polling failed:', error)
          }
        }
        
        // Start polling after a short delay
        setTimeout(pollStatus, 1000)
        
      } else {
        console.error('❌ Regeneration failed:', response.error)
      }
      
    } catch (error) {
      console.error('❌ Regeneration request failed:', error)
    }
  }

  // Database state debug function
  const debugDatabaseState = async () => {
    console.log('🗄️ DEBUG: Checking database state...')
    
    try {
      const response = await api.debugDatabaseState()
      
      if (response.success && response.data) {
        // The actual data is nested inside response.data.data due to SuccessResponse wrapper
        const data = response.data.data || response.data
        
        console.log('📊 DATABASE STATE:')
        console.log(`Total entries: ${data.total_entries}`)
        console.log(`Entries with embeddings: ${data.entries_with_embeddings}`)
        console.log(`Entries without embeddings: ${data.entries_without_embeddings}`)
        
        // Check regeneration status
        if (data.regeneration_status) {
          console.log('\n🔄 REGENERATION STATUS:')
          console.log(`Is running: ${data.regeneration_status.is_running}`)
          console.log(`Progress: ${data.regeneration_status.progress}/${data.regeneration_status.total}`)
          console.log(`Current step: ${data.regeneration_status.current_step}`)
        }
        
        // Show Raj entries if found
        if (data.raj_entries && data.raj_entries.length > 0) {
          console.log(`\n📌 ENTRIES CONTAINING "RAJ": ${data.raj_entries_found}`)
          data.raj_entries.forEach((entry: any, index: number) => {
            console.log(`\n--- Raj Entry ${index + 1} (ID: ${entry.id}) ---`)
            console.log(`Has embeddings: ${entry.has_embeddings} (${entry.embedding_dimension}D)`)
            if (entry.raw_text_snippet) {
              console.log(`Raw: "${entry.raw_text_snippet}"`)
            }
            if (entry.structured_snippet) {
              console.log(`Structured: "${entry.structured_snippet}"`)
            }
            if (entry.selected_text) {
              console.log(`Text for embedding: "${entry.selected_text}"`)
            }
          })
        } else {
          console.log('\n⚠️ No entries containing "Raj" found in database')
        }
        
        if (data.sample_entries && data.sample_entries.length > 0) {
          console.log('\n📝 SAMPLE ENTRIES:')
          data.sample_entries.forEach((entry: any, index: number) => {
            console.log(`\n--- Entry ${index + 1} (ID: ${entry.id}) ---`)
            console.log(`Has raw text: ${entry.has_raw}`)
            console.log(`Has enhanced: ${entry.has_enhanced}`)
            console.log(`Has structured: ${entry.has_structured}`)
            console.log(`Has embeddings: ${entry.has_embeddings} (${entry.embedding_dimension}D)`)
            
            if (entry.best_text_for_embedding) {
              console.log(`Best text for embedding: "${entry.best_text_for_embedding}"`)
            }
          })
        }
        
        // Summary message
        const embeddingPercentage = data.total_entries > 0 
          ? Math.round((data.entries_with_embeddings / data.total_entries) * 100) 
          : 0
        console.log(`\n📊 SUMMARY: ${embeddingPercentage}% of entries have embeddings (${data.entries_with_embeddings}/${data.total_entries})`)
        
      } else {
        console.error('❌ Failed to get database state:', response.error)
      }
      
    } catch (error) {
      console.error('❌ Database debug failed:', error)
    }
  }

  const loadEntries = async () => {
    try {
      setLoading(true)
      const response = await api.getEntries(currentPage, pageSize)
      
      if (response.success && response.data) {
        const loadedEntries = response.data.entries || []
        setEntries(loadedEntries)
        setTotalEntries(response.data.total || 0)
        setTotalPages(Math.ceil((response.data.total || 0) / pageSize))
      } else {
        console.error('Failed to load entries:', response.error)
        setEntries([])
      }
    } catch (error) {
      console.error('Failed to load entries:', error)
      setEntries([])
    } finally {
      setLoading(false)
    }
  }

  const performSemanticSearch = async (query: string) => {
    if (!query.trim()) {
      setIsSemanticSearch(false)
      setSemanticResults([])
      return
    }

    try {
      setSearching(true)
      console.log('🔍 Starting semantic search for:', query)
      
      const response = await api.semanticSearch(query, 20, 0.3)
      
      console.log('📡 Search response:', response)
      
      if (response.success && response.data) {
        // Handle nested data structure from SuccessResponse
        const searchData = response.data.data || response.data
        const results = searchData.results || []
        console.log('📊 Search results:', results)
        
        if (results.length === 0) {
          console.log('⚠️ No search results found')
          setSemanticResults([])
          setIsSemanticSearch(true)
          setCurrentPage(1)
          return
        }
        
        // Convert search results to Entry objects
        console.log('🔄 Fetching entry details for', results.length, 'results')
        
        const entryPromises = results.map(async (result: any) => {
          console.log('📝 Fetching entry:', result.entry_id, 'similarity:', result.similarity)
          const entryResponse = await api.getEntry(result.entry_id)
          if (entryResponse.success && entryResponse.data) {
            return {
              ...entryResponse.data,
              similarity: result.similarity // Add similarity score
            }
          }
          console.log('❌ Failed to fetch entry:', result.entry_id)
          return null
        })
        
        const entries = (await Promise.all(entryPromises)).filter(Boolean) as Entry[]
        console.log('✅ Successfully fetched', entries.length, 'entries')
        console.log('🎯 Similarities:', entries.map(e => `${(e as any).similarity * 100}%`).join(', '))
        
        setSemanticResults(entries)
        setIsSemanticSearch(true)
        setCurrentPage(1) // Reset to first page for search results
      } else {
        console.error('❌ Search failed:', response.error || response.data)
        setSemanticResults([])
        setIsSemanticSearch(false)
      }
    } catch (error) {
      console.error('💥 Search error:', error)
      setSemanticResults([])
      setIsSemanticSearch(false)
    } finally {
      setSearching(false)
    }
  }


  // Debug semantic search - shows detailed embedding information
  const performDebugSearch = async (query: string) => {
    if (!query.trim()) return

    try {
      console.log('🐛 DEBUG SEARCH for:', query)
      
      const response = await api.debugSearch(query)
      
      if (response.success && response.data) {
        const debugData = response.data.data || response.data
        
        console.log('🔍 DEBUG SEARCH RESULTS:')
        console.log('Query:', debugData.query)
        console.log('Query embedding dimension:', debugData.query_embedding_dim)
        console.log('Entries checked:', debugData.entries_checked)
        console.log('Total entries in DB:', debugData.total_entries)
        
        if (debugData.hiking_entries_found && debugData.hiking_entries_found.length > 0) {
          console.log(`\n📝 ENTRIES CONTAINING "${query}":`)
          debugData.hiking_entries_found.forEach((entry: any, index: number) => {
            console.log(`\n${index + 1}. Entry ID ${entry.entry_id}:`)
            console.log('  - Raw text has query:', entry.raw_has_hiking)
            console.log('  - Enhanced text has query:', entry.enhanced_has_hiking) 
            console.log('  - Structured text has query:', entry.structured_has_hiking)
            console.log('  - Has embeddings:', entry.has_embeddings)
            console.log('  - Text used for embedding:', entry.text_used_for_embedding)
            console.log('  - Raw preview:', entry.raw_text)
          })
        }
        
        if (debugData.results && debugData.results.length > 0) {
          console.log(`\n🔢 SIMILARITY RESULTS (Top ${debugData.results.length}):`)
          debugData.results.forEach((result: any, index: number) => {
            console.log(`${index + 1}. Entry ${result.entry_id}: ${(result.similarity * 100).toFixed(2)}% similarity`)
            console.log(`   Text: "${result.text_preview}"`)
            console.log(`   Contains query: ${result.has_hiking}`)
            console.log(`   Embedding length: ${result.embedding_length}`)
          })
        }
        
        // Check for potential issues
        const perfectMatches = debugData.results?.filter((r: any) => r.has_hiking) || []
        const nonMatches = debugData.results?.filter((r: any) => !r.has_hiking) || []
        
        if (perfectMatches.length === 0) {
          console.log('⚠️ WARNING: No results contain the search query text!')
        }
        
        if (debugData.results?.some((r: any) => Math.abs(r.similarity - 0.5) < 0.01)) {
          console.log('🚨 ALERT: Found results with ~50% similarity - this suggests BGE formatting mismatch!')
        }
        
        console.log('\n📊 Summary:')
        console.log(`- Entries with embeddings: ${debugData.entries_checked}`)
        console.log(`- Entries containing "${query}": ${debugData.hiking_entries_found?.length || 0}`)
        console.log(`- Perfect text matches in results: ${perfectMatches.length}`)
        console.log(`- Non-matching results: ${nonMatches.length}`)
        
      } else {
        console.error('Debug search failed:', response.error)
      }
    } catch (error) {
      console.error('Debug search error:', error)
    }
  }

  // Toggle dropdown for specific entry
  const toggleDropdown = (entryId: number) => {
    const newExpanded = new Set(expandedDropdowns)
    if (newExpanded.has(entryId)) {
      newExpanded.delete(entryId)
    } else {
      newExpanded.add(entryId)
    }
    setExpandedDropdowns(newExpanded)
  }

  // Show delete confirmation
  const showDeleteConfirmation = (entryId: number, entryTitle: string) => {
    setDeleteConfirmation({ entryId, entryTitle })
  }

  // Delete entry
  const deleteEntry = async (entryId: number) => {
    try {
      setDeleting(entryId)
      const response = await api.deleteEntry(entryId)
      
      if (response.success) {
        setEntries(entries.filter(entry => entry.id !== entryId))
        if (selectedEntry?.id === entryId) {
          setSelectedEntry(null)
        }
        setTotalEntries(prev => prev - 1)
        setDeleteConfirmation(null) // Close confirmation popup
      } else {
        console.error('Failed to delete entry:', response.error)
      }
    } catch (error) {
      console.error('Failed to delete entry:', error)
    } finally {
      setDeleting(null)
    }
  }

  // Cancel delete
  const cancelDelete = () => {
    setDeleteConfirmation(null)
  }

  // Export entry
  const exportEntry = (entry: Entry, version: 'raw' | 'enhanced' | 'structured') => {
    const content = getEntryContent(entry, version)
    const { dayOfWeek, formattedDate } = formatTimestamp(entry.timestamp)
    const filename = `entry-${dayOfWeek}-${formattedDate}-${version}.txt`
    
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  // Export all versions of an entry
  const exportAllVersions = (entry: Entry) => {
    const { dayOfWeek, formattedDate } = formatTimestamp(entry.timestamp)
    const content = `
ENTRY - ${dayOfWeek}, ${formattedDate}
${'='.repeat(50)}

RAW TRANSCRIPTION:
${entry.raw_text}

${entry.enhanced_text ? `
ENHANCED STYLE:
${entry.enhanced_text}
` : ''}

${entry.structured_summary ? `
STRUCTURED SUMMARY:
${entry.structured_summary}
` : ''}

Created: ${formattedDate}
Word Count: ${entry.word_count}
    `.trim()
    
    const filename = `entry-${dayOfWeek}-${formattedDate}-all-versions.txt`
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  // Format timestamp for display
  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp)
    const dayOfWeek = date.toLocaleDateString('en-US', { weekday: 'long' })
    const day = date.getDate()
    const month = date.toLocaleDateString('en-US', { month: 'long' })
    const year = date.getFullYear()
    
    // Add ordinal suffix (1st, 2nd, 3rd, 4th, etc.)
    const getOrdinalSuffix = (day: number) => {
      if (day > 3 && day < 21) return 'th'
      switch (day % 10) {
        case 1: return 'st'
        case 2: return 'nd'
        case 3: return 'rd'
        default: return 'th'
      }
    }
    
    const formattedDate = `${day}${getOrdinalSuffix(day)} ${month} ${year}`
    const time = date.toLocaleTimeString('en-US', { 
      hour: 'numeric', 
      minute: '2-digit',
      hour12: true 
    })
    
    return { dayOfWeek, formattedDate, time }
  }

  // Get content for specific version
  const getEntryContent = (entry: Entry, version: 'raw' | 'enhanced' | 'structured') => {
    switch (version) {
      case 'raw':
        return entry.raw_text
      case 'enhanced':
        return entry.enhanced_text || entry.raw_text
      case 'structured':
        return entry.structured_summary || entry.raw_text
      default:
        return entry.raw_text
    }
  }

  // Truncate text for preview
  const truncateText = (text: string, maxLength: number = 120) => {
    if (text.length <= maxLength) return text
    return text.slice(0, maxLength) + '...'
  }

  // Filter entries based on search query and date filter
  const filteredEntries = useMemo(() => {
    // Use semantic search results if available, otherwise use regular entries
    let filtered = isSemanticSearch ? semanticResults : entries

    // Apply date filter (but not text search since semantic search replaces it)
    if (dateFilterType !== 'all') {
      filtered = filtered.filter(entry => {
        const entryDate = new Date(entry.timestamp)
        const today = new Date()
        
        switch (dateFilterType) {
          case 'before':
            return startDate ? entryDate < new Date(startDate) : true
          case 'after':
            return startDate ? entryDate > new Date(startDate) : true
          case 'on':
            if (startDate) {
              const selectedDate = new Date(startDate)
              const entryDateOnly = new Date(entryDate.getFullYear(), entryDate.getMonth(), entryDate.getDate())
              const selectedDateOnly = new Date(selectedDate.getFullYear(), selectedDate.getMonth(), selectedDate.getDate())
              return entryDateOnly.getTime() === selectedDateOnly.getTime()
            }
            return true
          case 'between':
            if (startDate && endDate) {
              return entryDate >= new Date(startDate) && entryDate <= new Date(endDate)
            }
            return true
          case 'last-days-months':
            const periodAgo = new Date()
            if (lastPeriodUnit === 'days') {
              periodAgo.setDate(today.getDate() - lastPeriodValue)
            } else {
              periodAgo.setMonth(today.getMonth() - lastPeriodValue)
            }
            return entryDate >= periodAgo
          default:
            return true
        }
      })
    }

    return filtered
  }, [entries, semanticResults, isSemanticSearch, dateFilterType, startDate, endDate, lastPeriodValue, lastPeriodUnit])

  // Auto-close preview when no filtered entries (but not for directly fetched entries)
  useEffect(() => {
    if (selectedEntry && filteredEntries.length === 0) {
      // Only clear if we're in search mode or have filters active
      if (searchQuery || dateFilterType !== 'all') {
        setSelectedEntry(null)
        setEditing(false)
        setEditedContent('')
      }
    } else if (selectedEntry && !filteredEntries.find(entry => entry.id === selectedEntry.id)) {
      // Only close preview if we're in search/filter mode and entry is not in filtered results
      // Don't clear entries that were specifically navigated to from other pages
      if (searchQuery || dateFilterType !== 'all') {
        setSelectedEntry(null)
        setEditing(false)
        setEditedContent('')
      }
    }
  }, [filteredEntries, selectedEntry, searchQuery, dateFilterType])

  // Edit functionality
  const startEditing = () => {
    if (selectedEntry) {
      setEditing(true)
      setEditedContent(getEntryContent(selectedEntry, selectedVersion))
    }
  }

  const cancelEditing = () => {
    setEditing(false)
    setEditedContent('')
  }

  const saveEntry = async () => {
    if (!selectedEntry || !editedContent.trim()) return

    try {
      setSaving(true)
      
      // Determine which field to update based on selected version
      const updateData: any = {}
      switch (selectedVersion) {
        case 'raw':
          updateData.raw_text = editedContent
          break
        case 'enhanced':
          updateData.enhanced_text = editedContent
          break
        case 'structured':
          updateData.structured_summary = editedContent
          break
      }

      const response = await api.updateEntry(selectedEntry.id, updateData)
      
      if (response.success && response.data) {
        // Update the entry in the local state
        const updatedEntries = entries.map(entry => 
          entry.id === selectedEntry.id ? response.data! : entry
        )
        setEntries(updatedEntries)
        setSelectedEntry(response.data)
        
        // Show success notification
        setNotification({ message: 'Entry updated successfully!', type: 'success' })
        
        // Reset editing state
        setEditing(false)
        setEditedContent('')
      } else {
        throw new Error(response.error || 'Failed to update entry')
      }
    } catch (error) {
      console.error('Failed to save entry:', error)
      setNotification({ 
        message: error instanceof Error ? error.message : 'Failed to update entry', 
        type: 'error' 
      })
    } finally {
      setSaving(false)
    }
  }

  // Auto-hide notification after 3 seconds
  useEffect(() => {
    if (notification) {
      const timer = setTimeout(() => {
        setNotification(null)
      }, 3000)
      return () => clearTimeout(timer)
    }
  }, [notification])

  // Exit edit mode when switching between versions
  useEffect(() => {
    if (editing) {
      setEditing(false)
      setEditedContent('')
    }
  }, [selectedVersion])

  // Close date filter popup when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Element
      if (showDateFilter && !target.closest('.date-filter-popup')) {
        setShowDateFilter(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [showDateFilter])

  // Pagination controls
  const goToPage = (page: number) => {
    if (page >= 1 && page <= totalPages) {
      setCurrentPage(page)
    }
  }

  return (
    <div className="h-screen flex flex-col p-4 md:p-6 relative">
      {/* Notification */}
      {notification && (
        <motion.div
          initial={{ opacity: 0, y: -50 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -50 }}
          className={`fixed top-4 right-4 z-50 flex items-center gap-2 px-4 py-3 rounded-lg border shadow-lg ${
            notification.type === 'success' 
              ? 'bg-green-500/10 border-green-500/20 text-green-400' 
              : 'bg-red-500/10 border-red-500/20 text-red-400'
          }`}
        >
          {notification.type === 'success' ? (
            <CheckCircle className="h-4 w-4" />
          ) : (
            <X className="h-4 w-4" />
          )}
          <span className="text-sm font-medium">{notification.message}</span>
        </motion.div>
      )}
      
      <div className="max-w-7xl mx-auto w-full flex flex-col h-full">
        {/* Header */}
        <div className="flex items-center justify-between mb-6 flex-shrink-0">
          <h2 className="text-2xl font-bold text-white">Your Entries</h2>
          <div className="flex items-center gap-4">
            {/* Date Filter Button */}
            <div className="relative">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowDateFilter(!showDateFilter)}
                className="flex items-center gap-2 relative overflow-hidden group transition-all duration-200 bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 hover:text-primary"
              >
                {/* Animated background for consistent styling */}
                <motion.div
                  layoutId="activeDateFilterBg"
                  className="absolute inset-0 bg-primary/10"
                  initial={false}
                  transition={{ type: "spring", stiffness: 500, damping: 30 }}
                />
                
                <div className="relative flex items-center gap-2">
                  <Calendar className="h-4 w-4" />
                  {dateFilterType === 'all' ? 'All Time' : 
                   dateFilterType === 'last-days-months' ? `Last ${lastPeriodValue} ${lastPeriodUnit.charAt(0).toUpperCase() + lastPeriodUnit.slice(1)}` :
                   dateFilterType === 'before' ? 'Before Date' :
                   dateFilterType === 'after' ? 'After Date' :
                   dateFilterType === 'on' ? 'On Date' : 'Between Dates'}
                </div>
              </Button>

              {/* Date Filter Popup */}
              {showDateFilter && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="date-filter-popup absolute top-full right-0 mt-2 w-96 bg-card border border-border rounded-lg shadow-xl z-50 p-4"
                >
                  <div className="space-y-4">
                    <h3 className="font-semibold text-white text-sm">Filter by Date</h3>
                    
                    {/* Filter Type Selection */}
                    <div className="space-y-2">
                      <label className="flex items-center gap-2">
                        <input
                          type="radio"
                          name="dateFilter"
                          checked={dateFilterType === 'all'}
                          onChange={() => setDateFilterType('all')}
                          className="text-primary focus:ring-primary/20"
                        />
                        <span className="text-white text-sm">All time</span>
                      </label>
                      
                      <label className="flex items-center gap-2">
                        <input
                          type="radio"
                          name="dateFilter"
                          checked={dateFilterType === 'last-days-months'}
                          onChange={() => setDateFilterType('last-days-months')}
                          className="text-primary focus:ring-primary/20"
                        />
                        <span className="text-white text-sm">Last</span>
                        <input
                          type="number"
                          min="1"
                          max="31"
                          value={lastPeriodValue}
                          onChange={(e) => {
                            const value = Math.max(1, Math.min(31, parseInt(e.target.value) || 1))
                            setLastPeriodValue(value)
                          }}
                          disabled={dateFilterType !== 'last-days-months'}
                          className="bg-background border border-border rounded px-2 py-1 text-white text-sm w-16 focus:border-primary/50 focus:outline-none focus:ring-1 focus:ring-primary/20"
                        />
                        <div className="relative calendar-container">
                          <select
                            value={lastPeriodUnit}
                            onChange={(e) => setLastPeriodUnit(e.target.value as 'days' | 'months')}
                            disabled={dateFilterType !== 'last-days-months'}
                            className="bg-background border border-border rounded px-2 py-1 pr-6 text-white text-sm focus:border-primary/50 focus:outline-none focus:ring-1 focus:ring-primary/20 appearance-none"
                          >
                            <option value="days">Days</option>
                            <option value="months">Months</option>
                          </select>
                          <ChevronDown className="absolute right-1 top-1/2 transform -translate-y-1/2 h-3 w-3 text-muted-foreground pointer-events-none" />
                        </div>
                      </label>
                      
                      <label className="flex items-center gap-2">
                        <input
                          type="radio"
                          name="dateFilter"
                          checked={dateFilterType === 'before'}
                          onChange={() => setDateFilterType('before')}
                          className="text-primary focus:ring-primary/20"
                        />
                        <span className="text-white text-sm">Before</span>
                        <div className="relative calendar-container">
                          <button
                            type="button"
                            onClick={() => setShowBeforeCalendar(!showBeforeCalendar)}
                            disabled={dateFilterType !== 'before'}
                            className="bg-background border border-border rounded px-2 py-1 text-white text-sm w-32 text-left hover:bg-muted/50 disabled:opacity-50"
                          >
                            {startDate ? new Date(startDate).toLocaleDateString() : 'Select date'}
                          </button>
                          {showBeforeCalendar && dateFilterType === 'before' && (
                            <div className="absolute top-full left-0 mt-2 z-[100] min-w-[280px]">
                              <CalendarComponent
                                selected={startDate}
                                onSelect={(date) => {
                                  setStartDate(date)
                                  setShowBeforeCalendar(false)
                                }}
                                className="shadow-2xl border-2 border-border"
                              />
                            </div>
                          )}
                        </div>
                      </label>
                      
                      <label className="flex items-center gap-2">
                        <input
                          type="radio"
                          name="dateFilter"
                          checked={dateFilterType === 'after'}
                          onChange={() => setDateFilterType('after')}
                          className="text-primary focus:ring-primary/20"
                        />
                        <span className="text-white text-sm">After</span>
                        <div className="relative calendar-container">
                          <button
                            type="button"
                            onClick={() => setShowAfterCalendar(!showAfterCalendar)}
                            disabled={dateFilterType !== 'after'}
                            className="bg-background border border-border rounded px-2 py-1 text-white text-sm w-32 text-left hover:bg-muted/50 disabled:opacity-50"
                          >
                            {startDate ? new Date(startDate).toLocaleDateString() : 'Select date'}
                          </button>
                          {showAfterCalendar && dateFilterType === 'after' && (
                            <div className="absolute top-full left-0 mt-2 z-[100] min-w-[280px]">
                              <CalendarComponent
                                selected={startDate}
                                onSelect={(date) => {
                                  setStartDate(date)
                                  setShowAfterCalendar(false)
                                }}
                                className="shadow-2xl border-2 border-border"
                              />
                            </div>
                          )}
                        </div>
                      </label>
                      
                      <label className="flex items-center gap-2">
                        <input
                          type="radio"
                          name="dateFilter"
                          checked={dateFilterType === 'on'}
                          onChange={() => setDateFilterType('on')}
                          className="text-primary focus:ring-primary/20"
                        />
                        <span className="text-white text-sm">On</span>
                        <div className="relative calendar-container">
                          <button
                            type="button"
                            onClick={() => setShowOnCalendar(!showOnCalendar)}
                            disabled={dateFilterType !== 'on'}
                            className="bg-background border border-border rounded px-2 py-1 text-white text-sm w-32 text-left hover:bg-muted/50 disabled:opacity-50"
                          >
                            {startDate ? new Date(startDate).toLocaleDateString() : 'Select date'}
                          </button>
                          {showOnCalendar && dateFilterType === 'on' && (
                            <div className="absolute top-full left-0 mt-2 z-[100] min-w-[280px]">
                              <CalendarComponent
                                selected={startDate}
                                onSelect={(date) => {
                                  setStartDate(date)
                                  setShowOnCalendar(false)
                                }}
                                className="shadow-2xl border-2 border-border"
                              />
                            </div>
                          )}
                        </div>
                      </label>
                      
                      <label className="flex items-center gap-2">
                        <input
                          type="radio"
                          name="dateFilter"
                          checked={dateFilterType === 'between'}
                          onChange={() => setDateFilterType('between')}
                          className="text-primary focus:ring-primary/20"
                        />
                        <span className="text-white text-sm">Between</span>
                      </label>
                      
                      {dateFilterType === 'between' && (
                        <div className="ml-6 space-y-2">
                          <div className="flex items-center gap-2">
                            <span className="text-muted-foreground text-sm w-12">From:</span>
                            <div className="relative flex-1">
                              <button
                                type="button"
                                onClick={() => setShowBetweenStartCalendar(!showBetweenStartCalendar)}
                                className="bg-background border border-border rounded px-2 py-1 text-white text-sm w-full text-left hover:bg-muted/50"
                              >
                                {startDate ? new Date(startDate).toLocaleDateString() : 'Select date'}
                              </button>
                              {showBetweenStartCalendar && (
                                <div className="absolute top-full left-0 mt-2 z-[100] min-w-[280px]">
                                  <CalendarComponent
                                    selected={startDate}
                                    onSelect={(date) => {
                                      setStartDate(date)
                                      setShowBetweenStartCalendar(false)
                                    }}
                                    className="shadow-2xl border-2 border-border"
                                  />
                                </div>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-muted-foreground text-sm w-12">To:</span>
                            <div className="relative flex-1">
                              <button
                                type="button"
                                onClick={() => setShowBetweenEndCalendar(!showBetweenEndCalendar)}
                                className="bg-background border border-border rounded px-2 py-1 text-white text-sm w-full text-left hover:bg-muted/50"
                              >
                                {endDate ? new Date(endDate).toLocaleDateString() : 'Select date'}
                              </button>
                              {showBetweenEndCalendar && (
                                <div className="absolute top-full right-0 mt-2 z-[100] min-w-[280px]">
                                  <CalendarComponent
                                    selected={endDate}
                                    onSelect={(date) => {
                                      setEndDate(date)
                                      setShowBetweenEndCalendar(false)
                                    }}
                                    className="shadow-2xl border-2 border-border"
                                  />
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                    
                    {/* Action Buttons */}
                    <div className="flex justify-end gap-2 pt-2 border-t border-border">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setDateFilterType('all')
                          setStartDate('')
                          setEndDate('')
                          setLastPeriodValue(1)
                          setLastPeriodUnit('months')
                          // Close all calendar popups
                          setShowBeforeCalendar(false)
                          setShowAfterCalendar(false)
                          setShowOnCalendar(false)
                          setShowBetweenStartCalendar(false)
                          setShowBetweenEndCalendar(false)
                        }}
                        className="text-white hover:bg-muted/50"
                      >
                        Clear
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowDateFilter(false)}
                        className="bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 hover:text-primary"
                      >
                        Apply
                      </Button>
                    </div>
                  </div>
                </motion.div>
              )}
            </div>

            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <input
                    type="text"
                    placeholder="Search your entries..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={handleSearchKeyDown}
                    className="pl-10 pr-4 py-2 bg-background border border-border rounded-md text-white placeholder:text-muted-foreground focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all duration-200 w-80"
                  />
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleSearchClick}
                  disabled={searching || !searchQuery.trim()}
                  className="flex items-center gap-2 relative overflow-hidden group transition-all duration-200 bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 hover:text-primary disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <div className="relative flex items-center gap-2">
                    {searching ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Search className="h-4 w-4" />
                    )}
                    Search
                  </div>
                </Button>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Badge className="bg-primary/10 text-primary border-primary/20">
                {searchQuery ? filteredEntries.length : totalEntries} entries
              </Badge>
            </div>
          </div>
        </div>

        {/* Main Content - Split View */}
        <div className={`flex-1 flex gap-6 overflow-hidden ${showDateFilter ? 'blur-sm pointer-events-none' : ''} transition-all duration-200`}>
          {/* Entry List - Left Side */}
          <div className="w-96 flex flex-col overflow-hidden">
            <div className="flex-1 overflow-y-auto space-y-3 pr-2 pl-1 pt-1">
              {loading ? (
                <div className="flex items-center justify-center h-64">
                  <div className="text-center space-y-4">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
                    <p className="text-muted-foreground">Loading entries...</p>
                  </div>
                </div>
              ) : filteredEntries.length === 0 ? (
                <div className="flex items-center justify-center h-64">
                  <div className="text-center space-y-4">
                    <FileText className="h-12 w-12 text-muted-foreground mx-auto" />
                    <p className="text-white font-medium">
                      {searchQuery ? 'No entries match your search' : 'Start by creating your first entry'}
                    </p>
                  </div>
                </div>
              ) : (
                filteredEntries.map((entry) => {
                  const { dayOfWeek, formattedDate, time } = formatTimestamp(entry.timestamp)
                  const isExpanded = expandedDropdowns.has(entry.id)
                  const isSelected = selectedEntry?.id === entry.id
                  
                  return (
                    <motion.div
                      key={entry.id}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="space-y-2"
                    >
                      {/* Entry Header - Always visible */}
                      <Card className={`cursor-pointer transition-all duration-200 hover:shadow-lg relative overflow-hidden group ${
                        isSelected ? 'ring-2 ring-primary/50 bg-primary/5' : 'hover:bg-muted/30'
                      }`}>
                        {/* Shimmer effect */}
                        <div className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/10 to-transparent group-hover:translate-x-full transition-transform duration-700" />
                        
                        <CardHeader 
                          className="pb-2 pt-3 px-3 relative"
                          onClick={() => {
                            setSelectedEntry(entry)
                            setSelectedVersion('enhanced')
                          }}
                        >
                          <div className="flex items-center justify-between">
                            <div>
                              <div className="font-semibold text-white text-sm">
                                <span className="text-primary">{dayOfWeek}</span>
                                <span className="text-white">, </span>
                                <span className="text-muted-foreground">{formattedDate}</span>
                              </div>
                              <div className="flex items-center gap-2 mt-1 text-muted-foreground">
                                <Clock className="h-3 w-3" />
                                <span className="text-xs">{time}</span>
                              </div>
                            </div>
                            <div className="flex items-center gap-1">
                              {/* Delete and Export buttons - only visible on hover */}
                              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                {/* Delete button */}
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    const { dayOfWeek, formattedDate } = formatTimestamp(entry.timestamp)
                                    showDeleteConfirmation(entry.id, `${dayOfWeek}, ${formattedDate}`)
                                  }}
                                  disabled={deleting === entry.id}
                                  className="h-8 w-8 p-0 text-blue-300 drop-shadow-[0_0_4px_rgba(147,197,253,0.6)] hover:bg-red-500/20 hover:text-red-400 hover:drop-shadow-[0_0_6px_rgba(248,113,113,0.8)]"
                                >
                                  {deleting === entry.id ? (
                                    <Loader2 className="h-3 w-3 animate-spin" />
                                  ) : (
                                    <Trash2 className="h-3 w-3" />
                                  )}
                                </Button>
                                {/* Export button */}
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    exportAllVersions(entry)
                                  }}
                                  className="h-8 w-8 p-0 text-blue-300 drop-shadow-[0_0_4px_rgba(147,197,253,0.6)] hover:bg-blue-500/20 hover:text-blue-400 hover:drop-shadow-[0_0_6px_rgba(96,165,250,0.8)]"
                                >
                                  <Download className="h-3 w-3" />
                                </Button>
                              </div>
                              {/* Dropdown toggle - always visible */}
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  toggleDropdown(entry.id)
                                }}
                                className="h-8 w-8 p-0 hover:bg-muted/50"
                              >
                                {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                              </Button>
                            </div>
                          </div>
                          
                          {/* Default Enhanced Preview */}
                          <div className="mt-2">
                            <p className="text-white text-sm leading-relaxed">
                              {truncateText(getEntryContent(entry, 'enhanced'))}
                            </p>
                            <div className="flex items-center justify-between mt-2">
                              <div className="flex items-center gap-2">
                                <Badge className="bg-purple-500/10 text-purple-400 border-purple-500/20 text-xs">
                                  Enhanced
                                </Badge>
                                {/* Embedding indicator */}
                                {isRegenerating ? (
                                  <Badge className="bg-yellow-500/10 text-yellow-400 border-yellow-500/20 text-xs">
                                    Regenerating
                                  </Badge>
                                ) : entry.embeddings && Array.isArray(entry.embeddings) && entry.embeddings.length > 0 ? (
                                  <Badge className="bg-cyan-500/10 text-cyan-400 border-cyan-500/20 text-xs">
                                    Indexed
                                  </Badge>
                                ) : (
                                  <Badge className="bg-orange-500/10 text-orange-400 border-orange-500/20 text-xs">
                                    No Embeddings
                                  </Badge>
                                )}
                                {isSemanticSearch && (entry as any).similarity && (
                                  <Badge className="bg-emerald-500/10 text-emerald-400 border-emerald-500/20 text-xs">
                                    {Math.round((entry as any).similarity * 100)}% match
                                  </Badge>
                                )}
                              </div>
                              <span className="text-muted-foreground text-xs">
                                {entry.word_count} words
                              </span>
                            </div>
                          </div>
                        </CardHeader>
                      </Card>

                      {/* Dropdown - All Three Versions */}
                      <AnimatePresence>
                        {isExpanded && (
                          <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            transition={{ duration: 0.2 }}
                            className="space-y-2 ml-4"
                          >
                            {viewModes.map((mode) => {
                              const content = getEntryContent(entry, mode.key as any)
                              if (!content) return null
                              
                              return (
                                <motion.div
                                  key={mode.key}
                                  whileHover={{
                                    y: -8,
                                    scale: 1.02,
                                    transition: {
                                      type: "spring",
                                      stiffness: 400,
                                      damping: 10
                                    }
                                  }}
                                >
                                  <Card
                                    className={`cursor-pointer transition-all duration-200 hover:shadow-lg ${mode.bgColor} ${mode.borderColor} border relative group overflow-hidden`}
                                    onClick={() => {
                                      setSelectedEntry(entry)
                                      setSelectedVersion(mode.key as any)
                                    }}
                                  >
                                  
                                  <CardContent className="p-3 relative">
                                    <div className="flex items-center justify-between mb-2">
                                      <div className="flex items-center gap-2">
                                        <mode.icon className="h-4 w-4 text-white" />
                                        <span className="font-medium text-white text-sm">{mode.title}</span>
                                      </div>
                                      {/* Action buttons for dropdown entries */}
                                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100">
                                        <Button
                                          variant="ghost"
                                          size="sm"
                                          onClick={(e) => {
                                            e.stopPropagation()
                                            setSelectedEntry(entry)
                                            setSelectedVersion(mode.key as any)
                                            startEditing()
                                          }}
                                          className="h-6 w-6 p-0 text-blue-300 drop-shadow-[0_0_4px_rgba(147,197,253,0.6)] hover:bg-purple-500/20 hover:text-purple-400 hover:drop-shadow-[0_0_6px_rgba(196,181,253,0.8)]"
                                          title="Edit this version"
                                        >
                                          <Edit className="h-3 w-3" />
                                        </Button>
                                        <Button
                                          variant="ghost"
                                          size="sm"
                                          onClick={(e) => {
                                            e.stopPropagation()
                                            exportEntry(entry, mode.key as any)
                                          }}
                                          className="h-6 w-6 p-0 text-blue-300 drop-shadow-[0_0_4px_rgba(147,197,253,0.6)] hover:bg-blue-500/20 hover:text-blue-400 hover:drop-shadow-[0_0_6px_rgba(96,165,250,0.8)]"
                                          title="Export this version"
                                        >
                                          <Download className="h-3 w-3" />
                                        </Button>
                                        <Button
                                          variant="ghost"
                                          size="sm"
                                          onClick={(e) => {
                                            e.stopPropagation()
                                            const { dayOfWeek, formattedDate } = formatTimestamp(entry.timestamp)
                                            showDeleteConfirmation(entry.id, `${dayOfWeek}, ${formattedDate}`)
                                          }}
                                          disabled={deleting === entry.id}
                                          className="h-6 w-6 p-0 text-blue-300 drop-shadow-[0_0_4px_rgba(147,197,253,0.6)] hover:bg-red-500/20 hover:text-red-400 hover:drop-shadow-[0_0_6px_rgba(248,113,113,0.8)]"
                                          title="Delete entry"
                                        >
                                          {deleting === entry.id ? (
                                            <Loader2 className="h-3 w-3 animate-spin" />
                                          ) : (
                                            <Trash2 className="h-3 w-3" />
                                          )}
                                        </Button>
                                      </div>
                                    </div>
                                    <p className="text-white text-sm leading-relaxed">
                                      {truncateText(content, 100)}
                                    </p>
                                  </CardContent>
                                  </Card>
                                </motion.div>
                              )
                            })}
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </motion.div>
                  )
                })
              )}
            </div>
            
            {/* Pagination Controls - Fixed at bottom */}
            {!searchQuery && totalPages > 1 && (
              <div className="mt-4 flex items-center justify-between border-t border-border pt-4 flex-shrink-0">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => goToPage(currentPage - 1)}
                  disabled={currentPage === 1 || loading}
                  className="flex items-center gap-2 bg-card border border-border text-yellow-400 hover:bg-card/80 hover:text-yellow-300 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ChevronLeft className="h-4 w-4" />
                  Previous
                </Button>
                
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <span>Page {currentPage} of {totalPages}</span>
                  <span className="text-xs">({totalEntries} total)</span>
                </div>
                
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => goToPage(currentPage + 1)}
                  disabled={currentPage === totalPages || loading}
                  className="flex items-center gap-2 bg-card border border-border text-yellow-400 hover:bg-card/80 hover:text-yellow-300 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            )}
          </div>

          {/* Entry Detail - Right Side */}
          <div className="flex-1 overflow-hidden">
            {selectedEntry ? (
              <Card className="h-full flex flex-col">
                <CardHeader className="border-b flex-shrink-0">
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-white">
                        <span className="text-primary">{formatTimestamp(selectedEntry.timestamp).dayOfWeek}</span>
                        <span className="text-white">, </span>
                        <span className="text-muted-foreground">{formatTimestamp(selectedEntry.timestamp).formattedDate}</span>
                      </CardTitle>
                      <CardDescription className="flex items-center gap-2 mt-1">
                        <Clock className="h-4 w-4" />
                        {formatTimestamp(selectedEntry.timestamp).time}
                      </CardDescription>
                    </div>
                    <div className="flex items-center gap-1">
                      {/* Action buttons for detail view - icon only */}
                      {editing ? (
                        <>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={saveEntry}
                            disabled={saving || !editedContent.trim()}
                            className="h-8 w-8 p-0 text-blue-300 drop-shadow-[0_0_4px_rgba(147,197,253,0.6)] hover:bg-green-500/20 hover:text-green-400 hover:drop-shadow-[0_0_6px_rgba(74,222,128,0.8)]"
                            title="Save changes"
                          >
                            {saving ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Save className="h-4 w-4" />
                            )}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={cancelEditing}
                            className="h-8 w-8 p-0 text-blue-300 drop-shadow-[0_0_4px_rgba(147,197,253,0.6)] hover:bg-red-500/20 hover:text-red-400 hover:drop-shadow-[0_0_6px_rgba(248,113,113,0.8)]"
                            title="Cancel editing"
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </>
                      ) : (
                        <>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={startEditing}
                            className="h-8 w-8 p-0 text-blue-300 drop-shadow-[0_0_4px_rgba(147,197,253,0.6)] hover:bg-purple-500/20 hover:text-purple-400 hover:drop-shadow-[0_0_6px_rgba(196,181,253,0.8)]"
                            title="Edit entry"
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => exportEntry(selectedEntry, selectedVersion)}
                            className="h-8 w-8 p-0 text-blue-300 drop-shadow-[0_0_4px_rgba(147,197,253,0.6)] hover:bg-blue-500/20 hover:text-blue-400 hover:drop-shadow-[0_0_6px_rgba(96,165,250,0.8)]"
                            title={`Export ${viewModes.find(m => m.key === selectedVersion)?.title}`}
                          >
                            <Download className="h-4 w-4" />
                          </Button>
                        </>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setExpandedView(true)}
                        className="h-8 w-8 p-0 text-blue-300 drop-shadow-[0_0_4px_rgba(147,197,253,0.6)] hover:bg-green-500/20 hover:text-green-400 hover:drop-shadow-[0_0_6px_rgba(74,222,128,0.8)]"
                        title="Expand to full screen"
                      >
                        <Maximize2 className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          const { dayOfWeek, formattedDate } = formatTimestamp(selectedEntry.timestamp)
                          showDeleteConfirmation(selectedEntry.id, `${dayOfWeek}, ${formattedDate}`)
                        }}
                        disabled={deleting === selectedEntry.id}
                        className="h-8 w-8 p-0 text-blue-300 drop-shadow-[0_0_4px_rgba(147,197,253,0.6)] hover:bg-red-500/20 hover:text-red-400 hover:drop-shadow-[0_0_6px_rgba(248,113,113,0.8)]"
                        title="Delete entry"
                      >
                        {deleting === selectedEntry.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setSelectedEntry(null)}
                        className="h-8 w-8 p-0 text-blue-300 drop-shadow-[0_0_4px_rgba(147,197,253,0.6)] hover:bg-muted/50 hover:text-white hover:drop-shadow-[0_0_6px_rgba(255,255,255,0.6)]"
                        title="Close preview"
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 mt-4">
                    {viewModes.map((mode) => (
                      <Button
                        key={mode.key}
                        variant="ghost"
                        size="sm"
                        onClick={() => setSelectedVersion(mode.key as any)}
                        className={`relative overflow-hidden group transition-all duration-200 ${
                          selectedVersion === mode.key 
                            ? `${mode.bgColor} ${mode.borderColor} border text-white hover:${mode.bgColor} hover:text-white` 
                            : 'text-white border border-border hover:bg-muted/50 hover:text-white hover:border-muted'
                        }`}
                      >
                        {/* Animated background for active state */}
                        {selectedVersion === mode.key && (
                          <motion.div
                            layoutId="activeVersionBg"
                            className={`absolute inset-0 ${mode.gradient ? `bg-gradient-to-r ${mode.gradient}` : mode.bgColor}`}
                            initial={false}
                            transition={{ type: "spring", stiffness: 500, damping: 30 }}
                          />
                        )}
                        
                        <div className="relative flex items-center">
                          <mode.icon className="h-4 w-4 mr-2" />
                          {mode.title}
                        </div>
                      </Button>
                    ))}
                  </div>
                </CardHeader>
                <CardContent className="flex-1 overflow-y-auto p-6">
                  <div className="prose prose-invert max-w-none">
                    {editing ? (
                      <textarea
                        value={editedContent}
                        onChange={(e) => setEditedContent(e.target.value)}
                        className="w-full h-full min-h-[300px] bg-background border border-border rounded-md p-4 text-white text-sm leading-relaxed resize-none focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/50"
                        placeholder="Edit your entry..."
                      />
                    ) : (
                      <p className="text-white leading-relaxed whitespace-pre-wrap text-sm">
                        {getEntryContent(selectedEntry, selectedVersion)}
                      </p>
                    )}
                  </div>
                  
                  {/* Mood Tags Section */}
                  {selectedEntry.mood_tags && selectedEntry.mood_tags.length > 0 && (
                    <motion.div 
                      className="mt-4 pt-4 border-t border-border"
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.3, delay: 0.1 }}
                    >
                      <div className="flex flex-wrap gap-1">
                        {selectedEntry.mood_tags.map((tag, index) => (
                          <motion.div
                            key={`${selectedEntry.id}-${tag}-${index}`}
                            initial={{ opacity: 0, scale: 0.7, y: 5 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            transition={{ 
                              duration: 0.3, 
                              delay: 0.2 + (index * 0.08),
                              type: "spring",
                              stiffness: 300,
                              damping: 20
                            }}
                            whileHover={{ 
                              scale: 1.1,
                              y: -2,
                              transition: { duration: 0.2 }
                            }}
                            whileTap={{ scale: 0.95 }}
                          >
                            <Badge 
                              className={`bg-gradient-to-r ${getMoodColor(tag)} text-white text-xs cursor-pointer shadow-sm hover:shadow-md transition-shadow duration-200`}
                            >
                              {getMoodEmoji(tag)} {tag}
                            </Badge>
                          </motion.div>
                        ))}
                      </div>
                    </motion.div>
                  )}
                  
                  <div className="mt-6 pt-4 border-t border-border">
                    <div className="flex items-center text-sm text-muted-foreground">
                      <span>{selectedEntry.word_count} words</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <div className="h-full flex items-center justify-center">
                <div className="text-center space-y-4">
                  <FileText className="h-16 w-16 text-muted-foreground mx-auto" />
                  <div>
                    <p className="text-white font-medium text-lg">Select an entry to view</p>
                    <p className="text-muted-foreground">Choose an entry from the list to see its details</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Date Filter Overlay */}
      {showDateFilter && (
        <div className="fixed inset-0 bg-black/20 z-40" />
      )}

      {/* Expanded View Modal */}
      <AnimatePresence>
        {expandedView && selectedEntry && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md"
            onClick={() => setExpandedView(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              transition={{ type: "spring", stiffness: 300, damping: 30 }}
              className="w-[95vw] h-[85vh] max-w-6xl bg-card border border-border rounded-lg shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="h-full flex flex-col">
                {/* Modal Header */}
                <div className="flex items-center justify-between p-6 border-b border-border">
                  <div>
                    <h2 className="text-xl font-bold text-white">
                      <span className="text-primary">{formatTimestamp(selectedEntry.timestamp).dayOfWeek}</span>
                      <span className="text-white">, </span>
                      <span className="text-muted-foreground">{formatTimestamp(selectedEntry.timestamp).formattedDate}</span>
                    </h2>
                    <p className="text-muted-foreground flex items-center gap-2 mt-1">
                      <Clock className="h-4 w-4" />
                      {formatTimestamp(selectedEntry.timestamp).time}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {/* Version selection in modal */}
                    {viewModes.map((mode) => (
                      <Button
                        key={mode.key}
                        variant="ghost"
                        size="sm"
                        onClick={() => setSelectedVersion(mode.key as any)}
                        className={`relative overflow-hidden group transition-all duration-200 ${
                          selectedVersion === mode.key 
                            ? `${mode.bgColor} ${mode.borderColor} border text-white hover:${mode.bgColor} hover:text-white` 
                            : 'text-white border border-border hover:bg-muted/50 hover:text-white hover:border-muted'
                        }`}
                      >
                        {/* Animated background for active state */}
                        {selectedVersion === mode.key && (
                          <motion.div
                            layoutId="activeVersionBg"
                            className={`absolute inset-0 ${mode.gradient ? `bg-gradient-to-r ${mode.gradient}` : mode.bgColor}`}
                            initial={false}
                            transition={{ type: "spring", stiffness: 500, damping: 30 }}
                          />
                        )}
                        
                        <div className="relative flex items-center">
                          <mode.icon className="h-4 w-4 mr-2" />
                          {mode.title}
                        </div>
                      </Button>
                    ))}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setExpandedView(false)}
                      className="ml-4 h-8 w-8 p-0 text-blue-300 drop-shadow-[0_0_4px_rgba(147,197,253,0.6)] hover:bg-muted/50 hover:text-white hover:drop-shadow-[0_0_6px_rgba(255,255,255,0.6)]"
                      title="Close expanded view"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                </div>

                {/* Modal Content */}
                <div className="flex-1 overflow-y-auto p-6">
                  <div className="prose prose-invert max-w-none">
                    {editing ? (
                      <textarea
                        value={editedContent}
                        onChange={(e) => setEditedContent(e.target.value)}
                        className="w-full h-full min-h-[400px] bg-background border border-border rounded-md p-4 text-white text-sm leading-relaxed resize-none focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/50"
                        placeholder="Edit your entry..."
                      />
                    ) : (
                      <p className="text-white leading-relaxed whitespace-pre-wrap text-sm">
                        {getEntryContent(selectedEntry, selectedVersion)}
                      </p>
                    )}
                  </div>
                </div>

                {/* Modal Footer */}
                <div className="border-t border-border p-6">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      {editing ? (
                        <>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={saveEntry}
                            disabled={saving || !editedContent.trim()}
                            className="flex items-center gap-2 hover:bg-green-500/20 hover:text-green-400 hover:border-green-500/50"
                          >
                            {saving ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Save className="h-4 w-4" />
                            )}
                            Save Changes
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={cancelEditing}
                            className="flex items-center gap-2 hover:bg-red-500/20 hover:text-red-400 hover:border-red-500/50"
                          >
                            <X className="h-4 w-4" />
                            Cancel
                          </Button>
                        </>
                      ) : (
                        <>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={startEditing}
                            className="flex items-center gap-2 hover:bg-purple-500/20 hover:text-purple-400 hover:border-purple-500/50"
                          >
                            <Edit className="h-4 w-4" />
                            Edit Entry
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => exportEntry(selectedEntry, selectedVersion)}
                            className="flex items-center gap-2 hover:bg-blue-500/20 hover:text-blue-400 hover:border-blue-500/50"
                          >
                            <Download className="h-4 w-4" />
                            Export {viewModes.find(m => m.key === selectedVersion)?.title}
                          </Button>
                        </>
                      )}
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          const { dayOfWeek, formattedDate } = formatTimestamp(selectedEntry.timestamp)
                          showDeleteConfirmation(selectedEntry.id, `${dayOfWeek}, ${formattedDate}`)
                        }}
                        disabled={deleting === selectedEntry.id}
                        className="flex items-center gap-2 hover:bg-red-500/20 hover:text-red-400 hover:border-red-500/50"
                      >
                        {deleting === selectedEntry.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                        Delete Entry
                      </Button>
                    </div>
                    <div className="text-sm text-muted-foreground">
                      <span>{selectedEntry.word_count} words</span>
                      <span className="mx-2">•</span>
                      <span>Created {formatTimestamp(selectedEntry.timestamp).formattedDate}</span>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Delete Confirmation Modal */}
      <AnimatePresence>
        {deleteConfirmation && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md"
            onClick={cancelDelete}
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
                <div className="flex items-center justify-center w-12 h-12 bg-red-500/20 rounded-full">
                  <Trash2 className="h-6 w-6 text-red-400" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-white">Delete Entry</h3>
                  <p className="text-sm text-muted-foreground">This action cannot be undone</p>
                </div>
              </div>
              
              <p className="text-white mb-6">
                Are you sure you want to delete the entry from{' '}
                <span className="font-medium text-primary">{deleteConfirmation.entryTitle}</span>?
              </p>
              
              <div className="flex justify-end gap-3">
                <Button
                  variant="ghost"
                  onClick={cancelDelete}
                  className="text-white hover:bg-muted/50"
                >
                  Cancel
                </Button>
                <Button
                  onClick={() => deleteEntry(deleteConfirmation.entryId)}
                  disabled={deleting === deleteConfirmation.entryId}
                  className="bg-red-600 text-white hover:bg-red-700 border-red-600 hover:border-red-700"
                >
                  {deleting === deleteConfirmation.entryId ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  ) : (
                    <Trash2 className="h-4 w-4 mr-2" />
                  )}
                  Delete Entry
                </Button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default ViewEntriesPage