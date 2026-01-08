/// <reference types="vite/client" />
import axios from 'axios'
import { useAuthStore } from '@/store/authStore'

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

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
  
  // Email verification
  requestVerification: (email: string) =>
    api.post('/auth/request-verification', { email }),
  
  verifyEmail: (token: string) =>
    api.get(`/auth/verify-email?token=${token}`),
  
  // Password reset
  forgotPassword: (email: string) =>
    api.post('/auth/forgot-password', { email }),
  
  resetPassword: (token: string, newPassword: string) =>
    api.post('/auth/reset-password', { token, new_password: newPassword }),
}

// Agents API
export const agentsAPI = {
  list: () => api.get('/agents/'),
  
  get: (id: number) => api.get(`/agents/${id}`),
  
  create: (data: any) => api.post('/agents/', data),
  
  update: (id: number, data: any) => api.put(`/agents/${id}`, data),
  
  delete: (id: number) => api.delete(`/agents/${id}`),
  
  getDemoAgent: () => api.get('/agents/public/demo'),
  
  getStats: (id: number) => api.get(`/agents/${id}/stats`),
  
  getLeads: (id: number) => api.get(`/agents/${id}/leads`),
  
  // Outbound Scripts
  listScripts: (agentId: number, activeOnly: boolean = false) =>
    api.get(`/agents/${agentId}/scripts`, { params: { active_only: activeOnly } }),
  
  getScript: (agentId: number, scriptId: number) =>
    api.get(`/agents/${agentId}/scripts/${scriptId}`),
  
  createScript: (agentId: number, data: any) =>
    api.post(`/agents/${agentId}/scripts`, data),
  
  updateScript: (agentId: number, scriptId: number, data: any) =>
    api.put(`/agents/${agentId}/scripts/${scriptId}`, data),
  
  deleteScript: (agentId: number, scriptId: number) =>
    api.delete(`/agents/${agentId}/scripts/${scriptId}`),
  
  toggleScriptFavorite: (agentId: number, scriptId: number) =>
    api.post(`/agents/${agentId}/scripts/${scriptId}/toggle-favorite`),
}

// Calls API
export const callsAPI = {
  list: (params?: { page?: number; per_page?: number; status?: string; action_required?: boolean; favorite?: boolean; search?: string; agent_id?: number }) => 
    api.get('/calls/', { params }),
  
  get: (id: number) => api.get(`/calls/${id}`),
  
  getTranscript: (id: number) => api.get(`/calls/${id}/transcript`),
  
  generateSummary: (id: number) => api.post(`/calls/${id}/generate-summary`),
  
  sendEmail: (id: number, data: { to_email: string; subject: string; body: string; from_email?: string; from_name?: string }) =>
    api.post(`/calls/${id}/send-email`, data),
  
  getStats: (days: number = 30) => api.get('/calls/stats/overview', { params: { days } }),
  
  delete: (id: number) => api.delete(`/calls/${id}`),
  
  bulkDelete: (callIds: number[]) => api.post('/calls/bulk/delete', { call_ids: callIds }),
  
  recalculate: (id: number) => api.post(`/calls/${id}/recalculate`),
  
  recalculateAll: () => api.post('/calls/recalculate-all'),
  
  sendMessage: (id: number, content: string) => api.post(`/calls/${id}/messages`, { content }),
  
  toggleFavorite: (id: number) => api.post(`/calls/${id}/toggle-favorite`),
  
  bulkToggleFavorite: (callIds: number[], isFavorite: boolean) => 
    api.post('/calls/bulk/favorite', { call_ids: callIds, is_favorite: isFavorite }),
  
  // Outbound calls
  makeOutboundCall: (data: { from_phone_number: string; to_number: string; agent_id: number; script_id?: number }) =>
    api.post('/calls/outbound', data),
  
  getAvailablePhoneNumbers: (agentId?: number) => 
    api.get('/calls/outbound/phone-numbers', { params: agentId ? { agent_id: agentId } : {} }),
  
  getSipStatus: () => api.get('/calls/outbound/sip-status'),
  
  reloadSipRegistrations: () => api.post('/calls/outbound/sip-reload'),
  
  hangupCall: (id: number) => api.post(`/calls/${id}/hangup`),
}

// Libraries API
export const librariesAPI = {
  listPublic: (params?: { category?: string; search?: string }) =>
    api.get('/libraries/public', { params }),
  
  listMy: (params?: { category?: string; search?: string }) =>
    api.get('/libraries/my', { params }),
  
  get: (id: number) => api.get(`/libraries/${id}`),
  
  save: (id: number) => api.post(`/libraries/save/${id}`),
  
  create: (data: any) => api.post('/libraries/', data),
  
  update: (id: number, data: any) => api.put(`/libraries/${id}`, data),
  
  delete: (id: number) => api.delete(`/libraries/${id}`),
  
  listCategories: () => api.get('/libraries/categories/list'),
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

// Integrations API
export const integrationsAPI = {
  list: (params?: { integration_type?: string; provider?: string; is_active?: boolean }) =>
    api.get('/integrations/', { params }),
  
  get: (id: number) =>
    api.get(`/integrations/${id}`),
  
  create: (data: {
    name: string
    description?: string
    integration_type: string
    provider: string
    config: Record<string, any>
  }) => api.post('/integrations/', data),
  
  update: (id: number, data: {
    name?: string
    description?: string
    config?: Record<string, any>
    is_active?: boolean
  }) => api.put(`/integrations/${id}`, data),
  
  delete: (id: number) =>
    api.delete(`/integrations/${id}`),
  
  test: (id: number) =>
    api.post(`/integrations/${id}/test`),
  
  sync: (id: number) =>
    api.post(`/integrations/${id}/sync`),
  
  getTypes: () =>
    api.get('/integrations/types/list'),
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

// Admin API
export const adminAPI = {
  // Users
  listUsers: (params?: { 
    skip?: number; 
    limit?: number; 
    search?: string; 
    is_approved?: boolean; 
    is_active?: boolean;
    sort_by?: string;
    order?: string;
  }) =>
    api.get('/admin/users', { params }),
  
  getUser: (userId: number) =>
    api.get(`/admin/users/${userId}`),
  
  updateUser: (userId: number, data: {
    is_approved?: boolean;
    is_active?: boolean;
    is_superuser?: boolean;
    subscription_tier?: string;
  }) =>
    api.patch(`/admin/users/${userId}`, data),
  
  approveUser: (userId: number) =>
    api.post(`/admin/users/${userId}/approve`),
  
  rejectUser: (userId: number) =>
    api.post(`/admin/users/${userId}/reject`),
  
  activateUser: (userId: number) =>
    api.post(`/admin/users/${userId}/activate`),
  
  deactivateUser: (userId: number) =>
    api.post(`/admin/users/${userId}/deactivate`),
  
  // Stats
  getUserStats: () =>
    api.get('/admin/users/stats/summary'),

  // Overview
  getOverview: () =>
    api.get('/admin/overview'),

  // Agents
  listAgents: (params?: {
    skip?: number
    limit?: number
    search?: string
    is_active?: boolean
    is_public?: boolean
    owner_id?: number
  }) =>
    api.get('/admin/agents', { params }),

  updateAgent: (agentId: number, data: {
    is_active?: boolean
    is_public?: boolean
    rag_enabled?: boolean
  }) =>
    api.patch(`/admin/agents/${agentId}`, data),

  // Support
  listSupportTickets: (params?: {
    skip?: number
    limit?: number
    status?: string
    priority?: string
    search?: string
  }) =>
    api.get('/admin/support/tickets', { params }),

  updateSupportTicket: (ticketId: number, data: {
    status?: string
    priority?: string
    response_message?: string
  }) =>
    api.patch(`/admin/support/tickets/${ticketId}`, data),
}

// Default export for backward compatibility
export default api

