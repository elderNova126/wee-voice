import { useState, useEffect, useRef } from 'react'
import { XMarkIcon, PaperAirplaneIcon } from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { useAuthStore } from '@/store/authStore'
import { API_URL } from '@/lib/api'

interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  id?: string
  isTyping?: boolean
  isStreaming?: boolean
}

interface TextChatTestProps {
  agentId: number
  agentName: string
  onClose: () => void
}

export default function TextChatTest({ agentId, agentName, onClose }: TextChatTestProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputMessage, setInputMessage] = useState('')
  const [isConnected, setIsConnected] = useState(false)
  const [isConnecting, setIsConnecting] = useState(true)
  const [isWaitingForResponse, setIsWaitingForResponse] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WebSocket | null>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    let mounted = true
    
    // Connect to text chat WebSocket
    const token = useAuthStore.getState().token
    
    if (!token) {
      toast.error('Authentication required. Please log in.')
      setIsConnecting(false)
      return
    }
    
    const wsUrl = API_URL.replace('http', 'ws')
    const url = `${wsUrl}/api/v1/ws/text/${agentId}?token=${token}`
    
    console.log('Connecting to:', url)
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      if (!mounted) return
      console.log('✓ Text chat connected')
      setIsConnected(true)
      setIsConnecting(false)
    }

    ws.onmessage = (event) => {
      if (!mounted) return
      try {
        console.log('📨 Received message:', event.data)
        const data = JSON.parse(event.data)
        
        if (data.type === 'session_started') {
          console.log('✓ Session started:', data)
        } else if (data.type === 'message_chunk' && data.role === 'assistant') {
          // Handle streaming chunks
          setIsWaitingForResponse(false)
          
          setMessages(prev => {
            const lastMessage = prev[prev.length - 1]
            const isLastMessageAssistant = lastMessage && lastMessage.role === 'assistant' && lastMessage.isStreaming
            
            if (isLastMessageAssistant) {
              // Update existing streaming message
              return prev.map((msg, idx) => 
                idx === prev.length - 1
                  ? { ...msg, content: msg.content + data.content, isStreaming: !data.done }
                  : msg
              )
            } else {
              // Create new streaming message
              return [...prev, {
                role: 'assistant',
                content: data.content,
                timestamp: data.timestamp || new Date().toISOString(),
                id: `stream-${Date.now()}`,
                isStreaming: !data.done
              }]
            }
          })
        } else if (data.type === 'message' && data.role === 'assistant') {
          // Handle final complete message (for backward compatibility or fallback)
          setIsWaitingForResponse(false)
          
          setMessages(prev => {
            const lastMessage = prev[prev.length - 1]
            const isLastMessageAssistant = lastMessage && lastMessage.role === 'assistant' && lastMessage.isStreaming
            
            if (isLastMessageAssistant) {
              // Replace streaming message with final message
              return prev.map((msg, idx) => 
                idx === prev.length - 1
                  ? { ...msg, content: data.content, isStreaming: false, id: undefined }
                  : msg
              )
            } else {
              // Add new message
              return [...prev, {
                role: 'assistant',
                content: data.content,
                timestamp: data.timestamp || new Date().toISOString()
              }]
            }
          })
        } else if (data.type === 'error') {
          setIsWaitingForResponse(false)
          console.error('Server error:', data.message)
          toast.error(data.message || 'An error occurred')
          setMessages(prev => [...prev, {
            role: 'system',
            content: `Error: ${data.message}`,
            timestamp: new Date().toISOString()
          }])
        }
      } catch (error) {
        console.error('Error parsing message:', error, event.data)
      }
    }

    ws.onerror = (error) => {
      if (!mounted) return
      console.error('WebSocket error:', error)
      toast.error('Failed to connect to chat service. Please try again.')
      setIsConnecting(false)
      setIsConnected(false)
    }

    ws.onclose = (event) => {
      if (!mounted) return
      console.log('WebSocket closed:', event.code, event.reason)
      setIsConnected(false)
      
      if (event.code === 1006) {
        toast.error('Connection lost. Please check your network.')
      }
    }

    // Cleanup on unmount
    return () => {
      mounted = false
      console.log('Cleaning up WebSocket connection...')
      if (ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(JSON.stringify({ type: 'end_session' }))
        } catch (error) {
          console.log('Error sending end_session:', error)
        }
      }
      ws.close()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agentId])

  const handleSendMessage = () => {
    const message = inputMessage.trim()
    if (!message || !isConnected || !wsRef.current || isWaitingForResponse) return

    // Add user message to UI
    setMessages(prev => [...prev, {
      role: 'user',
      content: message,
      timestamp: new Date().toISOString()
    }])

    // Set loading state
    setIsWaitingForResponse(true)

    // Send to server
    wsRef.current.send(JSON.stringify({
      type: 'message',
      content: message
    }))

    // Clear input
    setInputMessage('')
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-w-2xl w-full h-[600px] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700 bg-gradient-to-r from-blue-600 to-purple-600 rounded-t-2xl">
          <div>
            <h3 className="text-lg font-semibold text-white">💬 {agentName}</h3>
            <p className="text-xs text-blue-100">
              {isConnecting ? 'Connecting...' : isConnected ? 'Connected' : 'Disconnected'}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-white hover:bg-white/20 rounded-lg transition"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-gray-50 dark:bg-gray-900/50">
          {isConnecting && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                <p className="mt-4 text-sm text-gray-500 dark:text-gray-400">Connecting to agent...</p>
              </div>
            </div>
          )}

          {!isConnecting && messages.length === 0 && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center max-w-sm">
                <div className="text-6xl mb-4">💬</div>
                <h4 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
                  Start the conversation!
                </h4>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Type a message below to chat with the AI assistant.
                </p>
              </div>
            </div>
          )}

          {messages.map((message, index) => (
            <div
              key={message.id || index}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} ${
                message.role === 'system' ? 'justify-center' : ''
              }`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                  message.role === 'user'
                    ? 'bg-blue-600 text-white rounded-br-sm'
                    : message.role === 'system'
                    ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-200 text-sm text-center'
                    : 'bg-white dark:bg-gray-800 text-gray-900 dark:text-white border border-gray-200 dark:border-gray-700 rounded-bl-sm'
                }`}
              >
                <p className="text-sm leading-relaxed whitespace-pre-wrap">
                  {message.content}
                  {(message.isTyping || message.isStreaming) && (
                    <span className="inline-block w-2 h-4 ml-1 bg-indigo-500 animate-pulse"></span>
                  )}
                </p>
                {!message.isTyping && !message.isStreaming && (
                  <p
                    className={`text-xs mt-1 ${
                      message.role === 'user'
                        ? 'text-blue-100'
                        : message.role === 'system'
                        ? 'text-yellow-700 dark:text-yellow-300'
                        : 'text-gray-400'
                    }`}
                  >
                    {new Date(message.timestamp).toLocaleTimeString()}
                  </p>
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="p-4 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 rounded-b-2xl">
          <div className="flex gap-2 items-end">
            <div className="flex-1 relative">
              <textarea
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={isConnected ? (isWaitingForResponse ? "Waiting for response..." : "Type your message...") : "Connecting..."}
                disabled={!isConnected || isWaitingForResponse}
                rows={1}
                className="w-full px-4 py-3 pr-12 bg-gray-50 dark:bg-gray-900/50 border-2 border-gray-200 dark:border-gray-700 rounded-2xl text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:focus:border-blue-400 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed resize-none min-h-[52px] max-h-[120px] overflow-y-auto transition-all shadow-sm hover:border-gray-300 dark:hover:border-gray-600"
                style={{ 
                  height: 'auto',
                  minHeight: '52px'
                }}
                onInput={(e) => {
                  const target = e.target as HTMLTextAreaElement
                  target.style.height = 'auto'
                  target.style.height = `${Math.min(target.scrollHeight, 120)}px`
                }}
              />
            </div>
            <div className="flex gap-2 flex-shrink-0">
              <button
                onClick={handleSendMessage}
                disabled={!isConnected || !inputMessage.trim() || isWaitingForResponse}
                className="h-[52px] w-[52px] bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 active:scale-95 text-white rounded-2xl font-medium transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center shadow-lg hover:shadow-xl disabled:shadow-none group"
                title="Send message (Enter)"
              >
                {isWaitingForResponse ? (
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                ) : (
                  <PaperAirplaneIcon className="h-5 w-5 transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
                )}
              </button>
            </div>
          </div>
          <div className="flex items-center justify-between mt-2.5">
            <p className="text-xs text-gray-400 dark:text-gray-500">
              <span className="hidden sm:inline">Press Enter to send</span>
              <span className="sm:hidden">Enter to send</span>
              <span className="mx-1.5">•</span>
              <span className="hidden sm:inline">Shift + Enter for new line</span>
              <span className="sm:hidden">Shift+Enter</span>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

