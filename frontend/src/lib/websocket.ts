// WebSocket client for real-time STT communication

interface WebSocketMessage {
  type: string
  data: any
  session_id?: string
  timestamp?: string
}

export interface STTState {
  state: string
  message?: string
  is_active?: boolean
  session_id?: string
}

export interface TranscriptionResult {
  text: string
  language?: string
  confidence?: number
  segments?: any[]
  processing_time?: number
}

type MessageHandler = (message: WebSocketMessage) => void
type StateChangeHandler = (state: STTState) => void
type TranscriptionHandler = (result: TranscriptionResult) => void
type ErrorHandler = (error: string) => void

class WebSocketClient {
  private ws: WebSocket | null = null
  private url: string
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private isConnecting = false
  private shouldReconnect = true

  // Event handlers
  private messageHandlers: Map<string, MessageHandler[]> = new Map()
  private stateChangeHandlers: StateChangeHandler[] = []
  private transcriptionHandlers: TranscriptionHandler[] = []
  private errorHandlers: ErrorHandler[] = []
  private connectionHandlers: ((connected: boolean) => void)[] = []

  constructor(url: string = 'ws://localhost:8000/api/v1/ws/stt') {
    this.url = url
  }

  connect(clientId?: string): Promise<void> {
    if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) {
      return Promise.resolve()
    }

    this.isConnecting = true
    this.shouldReconnect = true

    return new Promise((resolve, reject) => {
      try {
        const wsUrl = clientId ? `${this.url}?client_id=${clientId}` : this.url
        this.ws = new WebSocket(wsUrl)

        this.ws.onopen = () => {
          console.log('WebSocket connected')
          this.isConnecting = false
          this.reconnectAttempts = 0
          this.notifyConnectionHandlers(true)
          resolve()
        }

        this.ws.onmessage = (event) => {
          try {
            const message: WebSocketMessage = JSON.parse(event.data)
            this.handleMessage(message)
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error)
          }
        }

        this.ws.onclose = (event) => {
          console.log('WebSocket disconnected:', event.code, event.reason)
          this.isConnecting = false
          this.notifyConnectionHandlers(false)

          if (this.shouldReconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.scheduleReconnect()
          }
        }

        this.ws.onerror = (event) => {
          console.error('WebSocket error:', event)
          this.isConnecting = false
          this.notifyErrorHandlers('WebSocket connection error')
          reject(new Error('WebSocket connection failed'))
        }
      } catch (error) {
        this.isConnecting = false
        reject(error)
      }
    })
  }

  disconnect(): void {
    this.shouldReconnect = false
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.notifyConnectionHandlers(false)
  }

  private scheduleReconnect(): void {
    this.reconnectAttempts++
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)

    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`)

    setTimeout(() => {
      if (this.shouldReconnect) {
        this.connect()
      }
    }, delay)
  }

  private handleMessage(message: WebSocketMessage): void {
    console.log('WebSocket received message:', message.type, message.data)

    // Handle specific message types
    switch (message.type) {
      case 'state_change':
        this.notifyStateChangeHandlers(message.data)
        break
      case 'transcription':
      case 'transcription_result':
      case 'transcription_partial':
        this.notifyTranscriptionHandlers(message.data)
        break
      case 'error':
        this.notifyErrorHandlers(message.data.error || 'Unknown error')
        break
      case 'recording_started':
      case 'recording_stopped':
        this.notifyStateChangeHandlers(message.data)
        break
    }

    // Notify generic message handlers
    const handlers = this.messageHandlers.get(message.type) || []
    handlers.forEach(handler => handler(message))

    // Notify catch-all handlers
    const allHandlers = this.messageHandlers.get('*') || []
    allHandlers.forEach(handler => handler(message))
  }

  private notifyStateChangeHandlers(state: STTState): void {
    this.stateChangeHandlers.forEach(handler => handler(state))
  }

  private notifyTranscriptionHandlers(result: TranscriptionResult): void {
    this.transcriptionHandlers.forEach(handler => handler(result))
  }

  private notifyErrorHandlers(error: string): void {
    this.errorHandlers.forEach(handler => handler(error))
  }

  private notifyConnectionHandlers(connected: boolean): void {
    console.log(`Notifying ${this.connectionHandlers.length} connection handlers: ${connected}`)
    this.connectionHandlers.forEach(handler => handler(connected))
  }

  // Public methods for sending messages
  sendCommand(command: string, parameters: any = {}): void {
    this.sendMessage({
      type: 'command',
      data: {
        command,
        parameters
      }
    })
  }

  startRecording(): void {
    this.sendCommand('start_recording')
  }

  stopRecording(): void {
    this.sendCommand('stop_recording')
  }

  resetRecording(): void {
    this.sendCommand('reset_recording')
  }

  subscribeToChannels(channels: string[]): void {
    this.sendCommand('subscribe', { channels })
  }

  unsubscribeFromChannels(channels: string[]): void {
    this.sendCommand('unsubscribe', { channels })
  }

  ping(): void {
    this.sendMessage({
      type: 'ping',
      data: {}
    })
  }

  private sendMessage(message: Partial<WebSocketMessage>): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        ...message,
        timestamp: new Date().toISOString()
      }))
    } else {
      console.warn('WebSocket not connected, cannot send message:', message)
    }
  }

  // Event handler registration methods
  onMessage(type: string, handler: MessageHandler): () => void {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, [])
    }
    this.messageHandlers.get(type)!.push(handler)

    // Return unsubscribe function
    return () => {
      const handlers = this.messageHandlers.get(type)
      if (handlers) {
        const index = handlers.indexOf(handler)
        if (index > -1) {
          handlers.splice(index, 1)
        }
      }
    }
  }

  onStateChange(handler: StateChangeHandler): () => void {
    this.stateChangeHandlers.push(handler)
    return () => {
      const index = this.stateChangeHandlers.indexOf(handler)
      if (index > -1) {
        this.stateChangeHandlers.splice(index, 1)
      }
    }
  }

  onTranscription(handler: TranscriptionHandler): () => void {
    this.transcriptionHandlers.push(handler)
    return () => {
      const index = this.transcriptionHandlers.indexOf(handler)
      if (index > -1) {
        this.transcriptionHandlers.splice(index, 1)
      }
    }
  }

  onError(handler: ErrorHandler): () => void {
    this.errorHandlers.push(handler)
    return () => {
      const index = this.errorHandlers.indexOf(handler)
      if (index > -1) {
        this.errorHandlers.splice(index, 1)
      }
    }
  }

  onConnectionChange(handler: (connected: boolean) => void): () => void {
    this.connectionHandlers.push(handler)
    return () => {
      const index = this.connectionHandlers.indexOf(handler)
      if (index > -1) {
        this.connectionHandlers.splice(index, 1)
      }
    }
  }

  // Status methods
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN
  }

  getReadyState(): number | null {
    return this.ws?.readyState || null
  }
}

// Export singleton instance
export const wsClient = new WebSocketClient()
export type {
  WebSocketMessage,
  MessageHandler,
  StateChangeHandler,
  TranscriptionHandler,
  ErrorHandler
}