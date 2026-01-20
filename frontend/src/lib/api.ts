// API client for Boo Journal backend

const API_BASE_URL = 'http://localhost:8000/api/v1'

interface ApiResponse<T> {
  success: boolean
  data?: T
  error?: string
}

interface Entry {
  id: number
  raw_text: string
  enhanced_text?: string
  structured_summary?: string
  mode: string
  embeddings?: string
  timestamp: string
  mood_tags?: string[]
  word_count: number
  processing_metadata?: any
}

interface EntryCreate {
  raw_text: string
  mode: string
}

interface EntryListResponse {
  entries: Entry[]
  total: number
  page: number
  page_size: number
  has_next: boolean
  has_prev: boolean
}

interface Preference {
  id: number
  key: string
  value: string
  value_type: string
  description?: string
  typed_value: any
}

interface PreferencesListResponse {
  preferences: Preference[]
}

class ApiClient {
  private baseUrl: string

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl
  }

  async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const url = `${this.baseUrl}${endpoint}`
    
    // Don't set Content-Type for FormData - let browser handle it
    const isFormData = options.body instanceof FormData
    const defaultHeaders = isFormData ? {} : {
      'Content-Type': 'application/json',
    }

    // Add session token if available
    const sessionToken = localStorage.getItem('session_token')
    if (sessionToken) {
      defaultHeaders['Authorization'] = `Bearer ${sessionToken}`
    }

    const config: RequestInit = {
      ...options,
      headers: {
        ...defaultHeaders,
        ...options.headers,
      },
    }

    try {
      const response = await fetch(url, config)
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        return {
          success: false,
          error: errorData.detail || `HTTP ${response.status}: ${response.statusText}`
        }
      }

      const data = await response.json()
      return {
        success: true,
        data
      }
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error'
      }
    }
  }

  // Entry endpoints
  async createEntry(entryData: EntryCreate): Promise<ApiResponse<Entry>> {
    return this.request<Entry>('/entries/', {
      method: 'POST',
      body: JSON.stringify(entryData)
    })
  }

  async createEntryWithAllTexts(
    rawText: string,
    enhancedText?: string,
    structuredSummary?: string,
    mode: string = 'raw',
    processingMetadata?: any,
    customTimestamp?: string
  ): Promise<ApiResponse<Entry>> {
    return this.request<Entry>('/entries/', {
      method: 'POST',
      body: JSON.stringify({
        raw_text: rawText,
        enhanced_text: enhancedText,
        structured_summary: structuredSummary,
        mode,
        processing_metadata: processingMetadata,
        custom_timestamp: customTimestamp
      })
    })
  }

  async getEntries(
    page: number = 1,
    pageSize: number = 20,
    mode?: string
  ): Promise<ApiResponse<EntryListResponse>> {
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString()
    })
    
    if (mode) {
      params.append('mode', mode)
    }

    return this.request<EntryListResponse>(`/entries/?${params}`)
  }

  async getEntry(entryId: number): Promise<ApiResponse<Entry>> {
    return this.request<Entry>(`/entries/${entryId}`)
  }

  async updateEntry(entryId: number, entryData: Partial<EntryCreate>): Promise<ApiResponse<Entry>> {
    return this.request<Entry>(`/entries/${entryId}`, {
      method: 'PUT',
      body: JSON.stringify(entryData)
    })
  }

  async deleteEntry(entryId: number): Promise<ApiResponse<any>> {
    return this.request(`/entries/${entryId}`, {
      method: 'DELETE'
    })
  }

  // Entry processing endpoints
  async processEntry(entryId: number, mode: string): Promise<ApiResponse<any>> {
    return this.request(`/entries/process/${entryId}`, {
      method: 'POST',
      body: JSON.stringify({ mode })
    })
  }

  async processTextOnly(
    rawText: string,
    modes: string[]
  ): Promise<ApiResponse<any>> {
    return this.request('/entries/process-only', {
      method: 'POST',
      body: JSON.stringify({
        raw_text: rawText,
        modes
      })
    })
  }

  async createAndProcessEntry(
    rawText: string,
    modes: string[]
  ): Promise<ApiResponse<any>> {
    return this.request('/entries/create-and-process', {
      method: 'POST',
      body: JSON.stringify({
        raw_text: rawText,
        modes
      })
    })
  }

  async getJobStatus(jobId: string): Promise<ApiResponse<any>> {
    return this.request(`/entries/processing/job/${jobId}`)
  }

  async getQueueStatus(): Promise<ApiResponse<any>> {
    return this.request('/entries/processing/queue/status')
  }

  // Health and status endpoints
  async getHealth(): Promise<ApiResponse<any>> {
    return this.request('/health')
  }

  async getWebSocketStatus(): Promise<ApiResponse<any>> {
    return this.request('/ws/status')
  }

  // Ollama endpoints
  async getOllamaModels(): Promise<ApiResponse<string[]>> {
    return this.request('/ollama/models')
  }

  async testOllamaConnection(): Promise<ApiResponse<any>> {
    return this.request('/ollama/test', {
      method: 'POST'
    })
  }

  // STT endpoints
  async getSTTStatus(): Promise<ApiResponse<any>> {
    return this.request('/stt/status')
  }

  async updateSTTConfig(config: any): Promise<ApiResponse<any>> {
    return this.request('/stt/config', {
      method: 'POST',
      body: JSON.stringify(config)
    })
  }

  // Hotkey endpoints
  async getHotkeyStatus(): Promise<ApiResponse<any>> {
    return this.request('/hotkey/status')
  }

  async changeHotkey(newHotkey: string): Promise<ApiResponse<any>> {
    return this.request('/hotkey/change', {
      method: 'POST',
      body: JSON.stringify({ hotkey: newHotkey })
    })
  }

  async validateHotkey(hotkey: string): Promise<ApiResponse<any>> {
    return this.request('/hotkey/validate', {
      method: 'POST',
      body: JSON.stringify({ hotkey })
    })
  }

  // Preferences endpoints
  async getPreferences(): Promise<ApiResponse<PreferencesListResponse>> {
    return this.request<PreferencesListResponse>('/preferences/')
  }

  async updatePreference(key: string, value: any, valueType: string = 'string', description?: string): Promise<ApiResponse<any>> {
    return this.request(`/preferences/${key}`, {
      method: 'PUT',
      body: JSON.stringify({ 
        key, 
        value, 
        value_type: valueType, 
        description 
      })
    })
  }

  // Statistics
  async getEntryCount(): Promise<ApiResponse<{ total_entries: number }>> {
    return this.request('/entries/stats/count')
  }

  async getDailyStreak(): Promise<ApiResponse<{ 
    streak: number
    last_entry_date: string | null
    total_entries: number
    unique_days: number
  }>> {
    return this.request('/entries/stats/daily-streak')
  }

  // Semantic search
  async semanticSearch(query: string, limit: number = 10, similarityThreshold: number = 0.3): Promise<ApiResponse<any>> {
    return this.request('/embeddings/semantic-search', {
      method: 'POST',
      body: JSON.stringify({
        query,
        limit,
        similarity_threshold: similarityThreshold
      })
    })
  }


  // Regenerate all embeddings using raw text only
  async regenerateAllEmbeddings(): Promise<ApiResponse<any>> {
    return this.request('/embeddings/regenerate-all-raw-text', {
      method: 'POST'
    })
  }

  // Get regeneration status
  async getRegenerationStatus(): Promise<ApiResponse<any>> {
    return this.request('/embeddings/regeneration-status')
  }

  // Debug database state
  async debugDatabaseState(): Promise<ApiResponse<any>> {
    return this.request('/embeddings/debug-database')
  }

  // Test embeddings directly
  async testEmbeddings(): Promise<ApiResponse<any>> {
    return this.request('/embeddings/test-embeddings')
  }

  // Force clear all embeddings
  async forceClearEmbeddings(): Promise<ApiResponse<any>> {
    return this.request('/embeddings/force-clear-embeddings', {
      method: 'POST'
    })
  }

  // Synchronous regeneration (for testing)
  async regenerateSync(): Promise<ApiResponse<any>> {
    return this.request('/embeddings/regenerate-sync', {
      method: 'POST'
    })
  }

  // Debug search
  async debugSearch(query: string): Promise<ApiResponse<any>> {
    return this.request('/embeddings/debug-search', {
      method: 'POST',
      body: JSON.stringify({ query })
    })
  }

  // Fix hiking entries
  async fixHikingEntries(): Promise<ApiResponse<any>> {
    return this.request('/embeddings/fix-hiking-entries', {
      method: 'POST'
    })
  }

  // Regenerate all embeddings with raw text only (final fix)
  async regenerateAllRawText(): Promise<ApiResponse<any>> {
    return this.request('/embeddings/regenerate-all-raw-text', {
      method: 'POST'
    })
  }

  // Pattern API methods
  async checkPatternThreshold(): Promise<ApiResponse<{
    threshold_met: boolean
    threshold: number
    entry_count: number
    remaining: number
  }>> {
    return this.request('/patterns/check')
  }

  async analyzePatterns(): Promise<ApiResponse<{
    patterns_found: number
    pattern_types: Record<string, number>
  }>> {
    return this.request('/patterns/analyze', {
      method: 'POST'
    })
  }

  async getPatterns(): Promise<ApiResponse<{
    patterns: Array<{
      id: number
      pattern_type: string
      description: string
      frequency: number
      confidence: number
      first_seen: string
      last_seen: string
      related_entries: number[]
      keywords: string[]
    }>
    total: number
  }>> {
    return this.request('/patterns/')
  }

  async getPatternEntries(patternId: number): Promise<ApiResponse<{
    entries: Entry[]
    pattern_id: number
    total: number
  }>> {
    return this.request(`/patterns/entries/${patternId}`)
  }
  
  async getEntriesByKeyword(keyword: string): Promise<ApiResponse<{
    entries: Entry[]
    keyword: string
    total: number
  }>> {
    return this.request(`/patterns/keyword/${encodeURIComponent(keyword)}`)
  }

  // Mood analysis endpoints
  async analyzeMood(text: string): Promise<ApiResponse<{
    mood_tags: string[]
  }>> {
    return this.request('/entries/analyze-mood', {
      method: 'POST',
      body: JSON.stringify({ text })
    })
  }

  async analyzeEntryMood(entryId: number): Promise<ApiResponse<{
    entry_id: number
    status: string
  }>> {
    return this.request(`/entries/${entryId}/analyze-mood`, {
      method: 'POST'
    })
  }

  // Talk to Your Diary API endpoints
  async getDiaryGreeting(): Promise<ApiResponse<string>> {
    return this.request('/diary/greeting')
  }

  async getDiarySearchFeedback(): Promise<ApiResponse<string>> {
    return this.request('/diary/search-feedback')
  }

  async preheatDiaryChat(): Promise<ApiResponse<{
    preheated: boolean
    model_ready: boolean
    entry_count?: number
  }>> {
    return this.request('/diary/preheat', {
      method: 'POST'
    })
  }

  async sendDiaryChatMessage(message: string, conversationHistory?: Array<{ role: string; content: string }>, conversationId?: number, memoryEnabled: boolean = true, debugMode: boolean = false): Promise<ApiResponse<{
    response: string
    tool_calls_made: Array<{ tool: string; arguments: any; result: any }>
    search_queries_used: string[]
    search_feedback?: string
    tool_feedback?: string
    processing_phases: Array<{ phase: string; message: string; tools?: string[] }>
    conversation_id?: number
    debug_info?: any
  }>> {
    return this.request('/diary/chat', {
      method: 'POST',
      body: JSON.stringify({
        message,
        conversation_history: conversationHistory,
        conversation_id: conversationId,
        memory_enabled: memoryEnabled,
        debug_mode: debugMode
      })
    })
  }

  // Conversation management endpoints
  async createConversation(data: {
    transcription: string
    conversation_type: string
    duration: number
    message_count: number
    search_queries_used: string[]
  }): Promise<ApiResponse<any>> {
    return this.request('/conversations', {
      method: 'POST',
      body: JSON.stringify(data)
    })
  }

  async getConversations(): Promise<ApiResponse<{
    conversations: Array<{
      id: number
      timestamp: string
      duration: number
      transcription: string
      conversation_type: string
      message_count: number
      search_queries_used: string[]
      created_at: string
      updated_at?: string
    }>
    total: number
  }>> {
    return this.request('/conversations')
  }

  async deleteConversation(id: number): Promise<ApiResponse<any>> {
    return this.request(`/conversations/${id}`, {
      method: 'DELETE'
    })
  }

  async getConversationStats(): Promise<ApiResponse<{
    total_conversations: number
    total_duration_seconds: number
    average_duration_seconds: number
    average_message_count: number
    conversations_by_type: Record<string, number>
    most_searched_topics: Array<{ query: string; count: number }>
    conversations_over_time: Array<{ date: string; count: number }>
    last_conversation_date?: string
  }>> {
    return this.request('/conversations/stats')
  }

  // TTS endpoints
  async synthesizeSpeech(text: string, stream: boolean = true): Promise<Blob> {
    // Try streaming first, fallback to non-streaming if it fails
    for (const useStream of [stream, false]) {
      try {
        const response = await fetch(`${this.baseUrl}/tts/synthesize`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ text, stream: useStream })
        })

        if (!response.ok) {
          throw new Error(`TTS synthesis failed: ${response.statusText}`)
        }

        // For streaming responses, collect all chunks
        if (useStream && response.body) {
          const reader = response.body.getReader()
          const chunks: Uint8Array[] = []
          
          try {
            let done = false
            let totalBytes = 0
            
            while (!done) {
              const result = await reader.read()
              done = result.done
              
              if (result.value) {
                chunks.push(result.value)
                totalBytes += result.value.length
              }
            }
            
            // Ensure we got some data
            if (totalBytes === 0) {
              throw new Error('No audio data received from stream')
            }
            
            // Combine all chunks into a single blob
            return new Blob(chunks, { type: 'audio/wav' })
          } finally {
            reader.releaseLock()
          }
        } else {
          // For non-streaming responses
          return response.blob()
        }
      } catch (error) {
        // If streaming failed and we haven't tried non-streaming yet, continue to fallback
        if (useStream && stream) {
          console.warn('Streaming TTS failed, falling back to non-streaming:', error)
          continue
        }
        // If non-streaming also failed or we weren't trying streaming, throw the error
        throw error
      }
    }
    
    throw new Error('All TTS synthesis methods failed')
  }

  async getTTSStatus(): Promise<ApiResponse<any>> {
    return this.request('/tts/status')
  }

  async getAvailableVoices(): Promise<ApiResponse<any>> {
    return this.request('/tts/voices')
  }

  async initializeTTS(): Promise<ApiResponse<any>> {
    return this.request('/tts/initialize', {
      method: 'POST'
    })
  }

  // Audio upload and transcription
  async uploadAndTranscribeAudio(formData: FormData): Promise<ApiResponse<{
    transcription: string
    duration?: number
    confidence?: number
  }>> {
    return this.request('/audio/transcribe', {
      method: 'POST',
      body: formData,
      headers: {} // Let browser set Content-Type for FormData
    })
  }

  // Memory management endpoints
  async getPaginatedMemories(
    page: number = 1,
    limit: number = 6,
    filter: 'all' | 'rated' | 'unrated' = 'all'
  ): Promise<ApiResponse<{
    memories: Array<{
      id: number
      content: string
      memory_type: string
      base_importance_score: number
      llm_importance_score?: number
      user_score_adjustment: number
      final_importance_score: number
      user_rated: number
      score_source: string
      effective_score?: any
      created_at: string
      last_accessed_at?: string
      access_count: number
    }>
    total: number
    page: number
    totalPages: number
    hasNext: boolean
    hasPrev: boolean
    filter: string
  }>> {
    const params = new URLSearchParams({
      page: page.toString(),
      limit: limit.toString(),
      filter
    })
    return this.request(`/memories/?${params}`)
  }

  async getUnratedMemories(limit: number = 10): Promise<ApiResponse<Array<{
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
  }>>> {
    return this.request(`/memories/unrated?limit=${limit}`)
  }

  async rateMemory(memoryId: number, adjustment: number): Promise<ApiResponse<{
    success: boolean
    message: string
  }>> {
    return this.request('/memories/rate', {
      method: 'POST',
      body: JSON.stringify({
        memory_id: memoryId,
        adjustment: adjustment
      })
    })
  }

  async getMemoryStats(): Promise<ApiResponse<{
    total_memories: number
    rated_memories: number
    unrated_memories: number
    llm_processed: number
    pending_deletion: number
    archived: number
    average_score: number
  }>> {
    return this.request('/memories/stats')
  }

  async searchMemories(query: string, memoryType?: string, limit: number = 10): Promise<ApiResponse<Array<{
    id: number
    content: string
    memory_type: string
    final_importance_score: number
    effective_score: any
    created_at: string
    access_count: number
  }>>> {
    const params = new URLSearchParams({ query, limit: limit.toString() })
    if (memoryType) {
      params.set('memory_type', memoryType)
    }
    return this.request(`/memories/search?${params}`)
  }

  async triggerLLMProcessing(batchSize: number = 5): Promise<ApiResponse<{
    success: boolean
    processed_count: number
    message: string
  }>> {
    return this.request('/memories/process-llm-batch', {
      method: 'POST',
      body: JSON.stringify({ batch_size: batchSize })
    })
  }

  async rescueMemory(memoryId: number): Promise<ApiResponse<{
    success: boolean
    message: string
  }>> {
    return this.request(`/memories/rescue/${memoryId}`, {
      method: 'POST'
    })
  }

  async getPendingDeletionMemories(): Promise<ApiResponse<Array<{
    id: number
    content: string
    deletion_reason: string
    marked_for_deletion_at: string
    scheduled_deletion_date: string
  }>>> {
    return this.request('/memories/pending-deletion')
  }

  // Authentication endpoints
  async getAuthStatus(): Promise<ApiResponse<{
    initialized: boolean
    has_users: boolean
    user_count: number
    requires_setup: boolean
    error?: string
  }>> {
    return this.request('/auth/status')
  }

  async registerUser(data: {
    name: string
    password: string
    recovery_phrase: string
    emergency_key?: string
  }): Promise<ApiResponse<{
    user: {
      id: number
      username: string
      display_name: string
      created_at: string
      last_login?: string
      is_active: boolean
    }
    emergency_key_file: string
    filename: string
    message: string
  }>> {
    return this.request('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data)
    })
  }

  async loginUser(data: {
    name: string
    password?: string
    recovery_phrase?: string
    emergency_key_content?: string
  }): Promise<ApiResponse<{
    user: {
      id: number
      username: string
      display_name: string
      created_at: string
      last_login?: string
      is_active: boolean
    }
    session_token: string
    message: string
  }>> {
    return this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify(data)
    })
  }

  async logoutUser(): Promise<ApiResponse<{ message: string }>> {
    return this.request('/auth/logout', {
      method: 'POST'
    })
  }

  async getSessionInfo(): Promise<ApiResponse<{
    user: {
      id: number
      username: string
      display_name: string
      created_at: string
      last_login?: string
      is_active: boolean
    } | null
    is_authenticated: boolean
    session_active: boolean
  }>> {
    return this.request('/auth/session')
  }

  async changePassword(data: {
    current_password: string
    new_password: string
  }): Promise<ApiResponse<{
    success: boolean
    message: string
  }>> {
    return this.request('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify(data)
    })
  }

  async changeRecoveryPhrase(data: {
    current_password: string
    new_recovery_phrase: string
  }): Promise<ApiResponse<{
    success: boolean
    message: string
  }>> {
    return this.request('/auth/change-recovery-phrase', {
      method: 'POST',
      body: JSON.stringify(data)
    })
  }

  async uploadEmergencyKey(name: string, file: File): Promise<ApiResponse<{
    user: {
      id: number
      username: string
      display_name: string
      created_at: string
      last_login?: string
      is_active: boolean
    }
    session_token: string
    message: string
  }>> {
    const formData = new FormData()
    formData.append('file', file)
    
    return this.request(`/auth/emergency/upload?name=${encodeURIComponent(name)}`, {
      method: 'POST',
      body: formData
    })
  }

  async listUsers(): Promise<ApiResponse<Array<{
    id: number
    username: string
    display_name: string
    created_at: string
    last_login?: string
  }>>> {
    return this.request('/auth/users')
  }

  async getUserCredentials(currentPassword: string): Promise<ApiResponse<{
    password: string
    recovery_phrase: string | null
  }>> {
    return this.request(`/auth/user/credentials?current_password=${encodeURIComponent(currentPassword)}`, {
      method: 'GET'
    })
  }
}

// Export singleton instance
export const api = new ApiClient()
export type { Entry, EntryCreate, EntryListResponse, ApiResponse, Preference, PreferencesListResponse }