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
  
  recalculate: (id: number) => api.post(`/calls/${id}/recalculate`),
  
  recalculateAll: () => api.post('/calls/recalculate-all'),
}

// API Keys API
export const apiKeysAPI = {
  list: () => api.get('/auth/api-keys'),
  
  create: (data: { name: string }) => api.post('/auth/api-keys', data),
  
  delete: (id: number) => api.delete(`/auth/api-keys/${id}`),
}

// Billing API
export const billingAPI = {
  getTransactions: (skip = 0, limit = 100) => 
    api.get('/billing/transactions', { params: { skip, limit } }),
  
  getInvoices: (skip = 0, limit = 100) => 
    api.get('/billing/invoices', { params: { skip, limit } }),
  
  createPaymentIntent: (data: { amount: number; description?: string }) =>
    api.post('/billing/create-payment-intent', data),
  
  upgradeSubscription: (data: { tier: string; payment_method_id: string }) =>
    api.post('/billing/upgrade-subscription', data),
  
  cancelSubscription: () =>
    api.post('/billing/cancel-subscription'),
  
  getSubscription: () =>
    api.get('/billing/subscription'),
  
  getCreditBalance: () =>
    api.get('/billing/credit-balance'),
  
  topUpCredits: (data: { amount: number }) =>
    api.post('/billing/top-up-credits', data),
}

// Usage API
export const usageAPI = {
  getRecords: (params?: { skip?: number; limit?: number; start_date?: string; end_date?: string }) =>
    api.get('/usage/records', { params }),
  
  getSummary: () =>
    api.get('/usage/summary'),
  
  getByMonth: (months = 12) =>
    api.get('/usage/by-month', { params: { months } }),
  
  getByDay: (days = 30) =>
    api.get('/usage/by-day', { params: { days } }),
  
  getByAgent: () =>
    api.get('/usage/by-agent'),
  
  getAnalytics: () =>
    api.get('/usage/analytics'),
  
  recordCall: (callId: number) =>
    api.post(`/usage/record-call/${callId}`),
  
  exportData: (params?: { start_date?: string; end_date?: string }) =>
    api.get('/usage/export', { 
      params,
      responseType: 'blob'
    }),
}

// Security API
export const securityAPI = {
  // Domain allowlist
  getDomains: (skip = 0, limit = 100) =>
    api.get('/security/domains', { params: { skip, limit } }),
  
  createDomain: (data: { domain: string; description?: string }) =>
    api.post('/security/domains', data),
  
  updateDomain: (id: number, data: { description?: string; is_active?: boolean }) =>
    api.put(`/security/domains/${id}`, data),
  
  deleteDomain: (id: number) =>
    api.delete(`/security/domains/${id}`),
  
  regenerateDomainKey: (id: number) =>
    api.post(`/security/domains/${id}/regenerate-key`),
  
  // IP allowlist
  getIPs: (skip = 0, limit = 100) =>
    api.get('/security/ips', { params: { skip, limit } }),
  
  createIP: (data: { ip_address: string; ip_range?: string; description?: string }) =>
    api.post('/security/ips', data),
  
  updateIP: (id: number, data: { description?: string; is_active?: boolean }) =>
    api.put(`/security/ips/${id}`, data),
  
  deleteIP: (id: number) =>
    api.delete(`/security/ips/${id}`),
  
  // Security logs
  getLogs: (params?: { skip?: number; limit?: number; event_type?: string; severity?: string }) =>
    api.get('/security/logs', { params }),
}

// Profile API
export const profileAPI = {
  getProfile: () =>
    api.get('/profile/me'),
  
  updateProfile: (data: { full_name?: string; email?: string }) =>
    api.put('/profile/me', data),
  
  changePassword: (data: { current_password: string; new_password: string; confirm_password: string }) =>
    api.post('/profile/change-password', data),
  
  getStats: () =>
    api.get('/profile/stats'),
  
  deleteAccount: (password: string) =>
    api.delete('/profile/me', { params: { password } }),
}

// Support API
export const supportAPI = {
  createTicket: (data: { name: string; email: string; subject: string; message: string; category: string }) =>
    api.post('/support/tickets', data),
  
  getTickets: () =>
    api.get('/support/tickets'),
  
  getTicketByNumber: (ticketNumber: string) =>
    api.get(`/support/tickets/${ticketNumber}`),
  
  addResponse: (ticketNumber: string, data: { message: string }) =>
    api.post(`/support/tickets/${ticketNumber}/responses`, data),
  
  getCategories: () =>
    api.get('/support/categories'),
}

// WebSocket API
export class VoiceWebSocket {
  private ws: WebSocket | null = null
  private agentId: number
  private apiKey: string | null
  private token: string | null
  
  constructor(agentId: number, apiKey: string | null = null, token: string | null = null) {
    this.agentId = agentId
    this.apiKey = apiKey
    this.token = token
  }
  
  connect(
    onMessage: (event: MessageEvent) => void,
    onError: (event: Event) => void,
    onClose: (event: CloseEvent) => void
  ) {
    const wsUrl = API_URL.replace('http', 'ws')
    let url = `${wsUrl}/api/v1/ws/voice/${this.agentId}`
    
    // Add authentication
    if (this.apiKey) {
      url += `?api_key=${this.apiKey}`
    } else if (this.token) {
      url += `?token=${this.token}`
    }
    
    this.ws = new WebSocket(url)
    
    this.ws.onopen = () => {
      console.log('WebSocket connected')
    }
    
    this.ws.onmessage = (event) => {
      onMessage(event)
    }
    
    this.ws.onerror = (event) => {
      console.error('WebSocket error:', event)
      onError(event)
    }
    
    this.ws.onclose = (event) => {
      console.log('WebSocket closed:', event.code, event.reason)
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
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        // Send end_session message with timestamp
        const endedAt = new Date().toISOString()
        const message = JSON.stringify({ 
          type: 'end_session',
          ended_at: endedAt
        })
        this.ws.send(message)
        
        // Wait to ensure message is delivered before closing
        setTimeout(() => {
          if (this.ws) {
            this.ws.close(1000, 'Client requested disconnect')
            this.ws = null
          }
        }, 200)
      } catch (error) {
        console.error('Error sending end_session:', error)
        if (this.ws) {
          this.ws.close()
          this.ws = null
        }
      }
    } else if (this.ws) {
      this.ws = null
    }
  }
}

