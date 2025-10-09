/// <reference types="vite/client" />
import axios from 'axios'
import { useAuthStore } from '@/store/authStore'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Auth API
export const authAPI = {
  register: (data: { email: string; password: string; full_name: string }) =>
    api.post('/auth/register', data),
  
  login: (email: string, password: string) =>
    api.post('/auth/login', new URLSearchParams({ username: email, password }), {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    }),
  
  getMe: () => api.get('/auth/me'),
  
  createApiKey: (name: string) => api.post('/auth/api-keys', { name }),
  
  listApiKeys: () => api.get('/auth/api-keys'),
  
  deleteApiKey: (keyId: number) => api.delete(`/auth/api-keys/${keyId}`),
}

// Agents API
export const agentsAPI = {
  list: () => api.get('/agents/'),
  
  get: (id: number) => api.get(`/agents/${id}`),
  
  create: (data: any) => api.post('/agents/', data),
  
  update: (id: number, data: any) => api.put(`/agents/${id}`, data),
  
  delete: (id: number) => api.delete(`/agents/${id}`),
  
  getDemoAgent: () => api.get('/agents/public/demo'),
}

// Calls API
export const callsAPI = {
  list: (params?: any) => api.get('/calls/', { params }),
  
  get: (id: number) => api.get(`/calls/${id}`),
  
  getTranscript: (id: number) => api.get(`/calls/${id}/transcript`),
  
  generateSummary: (id: number) => api.post(`/calls/${id}/generate-summary`),
  
  getStats: (days: number = 30) => api.get('/calls/stats/overview', { params: { days } }),
  
  delete: (id: number) => api.delete(`/calls/${id}`),
}

// WebSocket API
export class VoiceWebSocket {
  private ws: WebSocket | null = null
  private agentId: number
  private apiKey: string | null
  
  constructor(agentId: number, apiKey: string | null = null) {
    this.agentId = agentId
    this.apiKey = apiKey
  }
  
  connect(
    onMessage: (event: MessageEvent) => void,
    onError: (event: Event) => void,
    onClose: (event: CloseEvent) => void
  ) {
    const wsUrl = API_URL.replace('http', 'ws')
    const url = this.apiKey
      ? `${wsUrl}/api/v1/ws/voice/${this.agentId}?api_key=${this.apiKey}`
      : `${wsUrl}/api/v1/ws/voice/${this.agentId}`
    
    console.log('🔌 Attempting WebSocket connection...')
    console.log('   API_URL:', API_URL)
    console.log('   WS URL:', wsUrl)
    console.log('   Full URL:', url)
    console.log('   Agent ID:', this.agentId)
    
    this.ws = new WebSocket(url)
    
    this.ws.onopen = () => {
      console.log('✅ WebSocket connected successfully!')
    }
    
    this.ws.onmessage = (event) => {
      console.log('📨 WebSocket message received:', event.data)
      onMessage(event)
    }
    
    this.ws.onerror = (event) => {
      console.error('❌ WebSocket error:', event)
      onError(event)
    }
    
    this.ws.onclose = (event) => {
      console.log('🔌 WebSocket closed:', event.code, event.reason)
      onClose(event)
    }
  }
  
  sendAudio(audioData: ArrayBuffer) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(audioData)
    }
  }
  
  sendMessage(message: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message))
    }
  }
  
  disconnect() {
    if (this.ws) {
      this.sendMessage({ type: 'end_session' })
      this.ws.close()
      this.ws = null
    }
  }
}

