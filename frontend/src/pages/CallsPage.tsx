import { ChangeEvent, FormEvent, useCallback, useEffect, useState, useRef } from 'react'
import { PhoneIcon, ClockIcon, CurrencyDollarIcon, FunnelIcon } from '@heroicons/react/24/outline'
import DashboardLayout from '@/layouts/DashboardLayout'
import { callsAPI } from '@/lib/api'
import { useAuthStore } from '@/store/authStore'
import toast from 'react-hot-toast'

interface Call {
  id: number
  agent_id: number
  session_id: string
  status: string
  duration_minutes: number
  cost: number
  started_at: string | null  // Nullable - set when session actually starts
  ended_at: string | null
  summary?: string | null
  sentiment?: string | null
  transcript?: string | null
  callback_requested?: boolean
  callback_reason?: string | null
  action_items?: string[]
  action_tags?: string[]
  summarization_status?: string | null  // "summarized", "not_summarized", or null
  messages?: CallMessage[]  // Messages for the call
}

interface CallMessage {
  role: string
  content: string
  timestamp: string
}

interface CallWithDetails extends Call {
  key_points?: string[]
  messages?: CallMessage[]
}

const partitionFollowUpTags = (tags: string[] = []) => {
  return tags.reduce(
    (acc, tag) => {
      const normalized = tag.toLowerCase()
      if (normalized.includes('request')) {
        acc.actionRequests.push(tag)
      } else {
        acc.others.push(tag)
      }
      return acc
    },
    { actionRequests: [] as string[], others: [] as string[] }
  )
}

const getTagColor = (tag: string) => {
  const normalized = tag.toLowerCase()
  if (normalized.includes('request')) {
    return 'bg-amber-200 text-amber-900 dark:bg-amber-900 dark:text-amber-100 border border-amber-400 dark:border-amber-600'
  }
  if (normalized.includes('email')) {
    return 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-100'
  }
  if (normalized.includes('message')) {
    return 'bg-sky-100 text-sky-800 dark:bg-sky-900 dark:text-sky-100'
  }
  if (normalized.includes('callback')) {
    return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100'
  }
  if (normalized.includes('meeting') || normalized.includes('rdv') || normalized.includes('rendez')) {
    return 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-100'
  }
  if (normalized.includes('quote') || normalized.includes('devis')) {
    return 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-100'
  }
  if (normalized.includes('share document')) {
    return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-100'
  }
  if (normalized.includes('book demo')) {
    return 'bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-100'
  }
  return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
}

export default function CallsPage() {
  const [calls, setCalls] = useState<Call[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedCall, setSelectedCall] = useState<Call | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [actionRequiredFilter, setActionRequiredFilter] = useState<boolean | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const token = useAuthStore(state => state.token)

  useEffect(() => {
    loadCalls()
    
    // Connect to WebSocket for real-time updates
    if (token) {
      const wsUrl = `${import.meta.env.VITE_API_URL?.replace('http', 'ws') || 'ws://localhost:8000'}/api/v1/ws/calls/monitor?token=${token}`
      const ws = new WebSocket(wsUrl)
      
      ws.onopen = () => {
        console.log('Connected to call monitor WebSocket')
      }
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'call_update') {
            // Update the call in the list, or add it if it doesn't exist
            setCalls(prevCalls => {
              const existingIndex = prevCalls.findIndex(call => call.id === data.call.id)
              if (existingIndex >= 0) {
                // Update existing call
                const updatedCall = { ...prevCalls[existingIndex], ...data.call }
                
                // If there's a new message, we need to reload the call to get full details
                if (data.call.new_message) {
                  // Reload call details to get updated messages
                  callsAPI.get(data.call.id).then(response => {
                    setCalls(prevCalls => 
                      prevCalls.map(call => 
                        call.id === data.call.id 
                          ? { ...call, ...response.data }
                          : call
                      )
                    )
                  }).catch(err => {
                    console.error('Error reloading call:', err)
                  })
                }
                
                return prevCalls.map(call => 
                  call.id === data.call.id 
                    ? updatedCall
                    : call
                )
              } else {
                // Add new call at the beginning (most recent first)
                return [data.call, ...prevCalls]
              }
            })
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error)
        }
      }
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
      }
      
      ws.onclose = () => {
        console.log('Disconnected from call monitor WebSocket')
        // Attempt to reconnect after 5 seconds
        setTimeout(() => {
          if (token) {
            // Reconnect logic would go here if needed
          }
        }, 5000)
      }
      
      wsRef.current = ws
      
      return () => {
        ws.close()
      }
    }
  }, [token])

  const loadCalls = async () => {
    try {
      const response = await callsAPI.list()
      setCalls(response.data)
    } catch (error) {
      console.error('Failed to load calls:', error)
      toast.error('Failed to load calls')
    } finally {
      setLoading(false)
    }
  }

  const recalculateAllCalls = async () => {
    try {
      const response = await callsAPI.recalculateAll()
      toast.success(`Recalculated ${response.data.updated_count} calls`)
      loadCalls() // Reload calls to show updated values
    } catch (error) {
      console.error('Failed to recalculate calls:', error)
      toast.error('Failed to recalculate calls')
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString()
  }

  const getSentimentColor = (sentiment: string) => {
    switch (sentiment?.toLowerCase()) {
      case 'positive':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      case 'negative':
        return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'completed':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      case 'failed':
        return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
      case 'in_progress':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
      case 'summarizing':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
    }
  }

  return (
    <DashboardLayout>
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Call History</h1>
            <p className="mt-2 text-gray-600 dark:text-gray-400">
              View and analyze all voice agent calls
            </p>
          </div>
          <button
            onClick={recalculateAllCalls}
            className="btn-secondary flex items-center"
          >
            <ClockIcon className="h-4 w-4 mr-2" />
            Recalculate All
          </button>
        </div>
        
        {/* Filters */}
        <div className="mt-6 flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <FunnelIcon className="h-5 w-5 text-gray-500 dark:text-gray-400" />
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Filters:</span>
          </div>
          
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="all">All Status</option>
            <option value="initiated">Initiated</option>
            <option value="in_progress">In Progress</option>
            <option value="summarizing">Summarizing</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="interrupted">Interrupted</option>
          </select>
          
          <select
            value={actionRequiredFilter === null ? 'all' : actionRequiredFilter ? 'yes' : 'no'}
            onChange={(e) => {
              const value = e.target.value
              setActionRequiredFilter(value === 'all' ? null : value === 'yes')
            }}
            className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="all">All Calls</option>
            <option value="yes">Action Required</option>
            <option value="no">No Action Required</option>
          </select>
        </div>
      </div>
      
      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="card animate-pulse">
              <div className="h-20 bg-gray-200 dark:bg-gray-700 rounded"></div>
            </div>
          ))}
        </div>
      ) : calls.length === 0 ? (
        <div className="card text-center py-12">
          <PhoneIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-semibold text-gray-900 dark:text-white">No calls yet</h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Start testing your agents to see call history here.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {calls
            .filter(call => {
              if (statusFilter !== 'all' && call.status !== statusFilter) {
                return false
              }
              if (actionRequiredFilter !== null) {
                const { actionRequests } = partitionFollowUpTags(call.action_tags ?? [])
                const hasActionRequired = actionRequests.length > 0
                if (actionRequiredFilter && !hasActionRequired) return false
                if (!actionRequiredFilter && hasActionRequired) return false
              }
              return true
            })
            .map((call) => {
            const { actionRequests, others } = partitionFollowUpTags(call.action_tags ?? [])
            return (
              <div
                key={call.id}
                className="card hover:shadow-lg transition-shadow cursor-pointer"
                onClick={() => setSelectedCall(call)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start space-x-4 flex-1">
                    <div className="p-3 bg-blue-100 dark:bg-blue-900 rounded-lg">
                      <PhoneIcon className="h-6 w-6 text-blue-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                          Call #{call.id}
                        </h3>
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${getStatusColor(call.status)}`}>
                          {call.status}
                        </span>
                        {call.sentiment && (
                          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${getSentimentColor(call.sentiment)}`}>
                            {call.sentiment}
                          </span>
                        )}
                        {actionRequests.length > 0 && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200 uppercase tracking-wide">
                            Action Required
                          </span>
                        )}
                        {call.summarization_status && (
                          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                            call.summarization_status === 'summarized'
                              ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                              : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                          }`}>
                            {call.summarization_status === 'summarized' ? 'Summarized' : 'No Summarized'}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
                        {call.started_at ? formatDate(call.started_at) : 'Initializing...'}
                      </p>
                      {call.summary && (
                        <p className="text-sm text-gray-600 dark:text-gray-300 line-clamp-2">
                          {call.summary}
                        </p>
                      )}
                      {actionRequests.length > 0 && (
                        <div className="flex flex-wrap gap-2 mt-3">
                          {actionRequests.map((tag, index) => (
                            <span
                              key={`request-${tag}-${index}`}
                              className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${getTagColor(tag)}`}
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                      {others.length > 0 && (
                        <div className={`flex flex-wrap gap-2 ${actionRequests.length > 0 ? 'mt-2' : 'mt-3'}`}>
                          {others.map((tag, index) => (
                            <span
                              key={`other-${tag}-${index}`}
                              className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${getTagColor(tag)}`}
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-6 ml-4">
                    <div className="text-right">
                      <div className="flex items-center text-sm text-gray-500 dark:text-gray-400">
                        <ClockIcon className="h-4 w-4 mr-1" />
                        {call.duration_minutes?.toFixed(1) || '0.0'} min
                      </div>
                      <div className="flex items-center text-sm text-gray-500 dark:text-gray-400 mt-1">
                        <CurrencyDollarIcon className="h-4 w-4 mr-1" />
                        ${call.cost?.toFixed(2) || '0.00'}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Call Details Modal */}
      {selectedCall && (
        <CallDetailsModal
          call={selectedCall}
          onClose={() => setSelectedCall(null)}
        />
      )}
    </DashboardLayout>
  )
}

// Call Details Modal
interface CallDetailsModalProps {
  call: Call
  onClose: () => void
}

function CallDetailsModal({ call, onClose }: CallDetailsModalProps) {
  const [transcript, setTranscript] = useState<any>(null)
  const [loadingTranscript, setLoadingTranscript] = useState(true)
  const [callDetails, setCallDetails] = useState<CallWithDetails | null>(null)
  const [loadingDetails, setLoadingDetails] = useState(true)
  const [generatingSummary, setGeneratingSummary] = useState(false)
  const [showEmailComposer, setShowEmailComposer] = useState(false)
  const [sendingEmail, setSendingEmail] = useState(false)
  const [emailForm, setEmailForm] = useState({
    to_email: '',
    subject: `Follow-up for call #${call.id}`,
    body: ''
  })
  const token = useAuthStore(state => state.token)
  const wsRef = useRef<WebSocket | null>(null)

  const loadCallDetails = useCallback(async () => {
    setLoadingDetails(true)
    try {
      const response = await callsAPI.get(call.id)
      setCallDetails(response.data)
    } catch (error) {
      console.error('Failed to load call details:', error)
      toast.error('Failed to load call details')
    } finally {
      setLoadingDetails(false)
    }
  }, [call.id])

  const loadTranscript = useCallback(async () => {
    setLoadingTranscript(true)
    try {
      const response = await callsAPI.getTranscript(call.id)
      const { transcript: rawTranscript, transcript_json: structuredTranscript } = response.data ?? {}
      setTranscript(structuredTranscript ?? rawTranscript ?? null)
    } catch (error: any) {
      const status = error?.response?.status
      if (status === 404) {
        // No transcript stored for this call; fall back to any cached value
        setTranscript(call.transcript ?? null)
      } else {
        console.error('Failed to load transcript:', error)
        toast.error('Failed to load transcript')
      }
    } finally {
      setLoadingTranscript(false)
    }
  }, [call.id, call.transcript])

  useEffect(() => {
    loadCallDetails()
    loadTranscript()
    
    // Connect to WebSocket for real-time message updates
    if (token) {
      const wsUrl = `${import.meta.env.VITE_API_URL?.replace('http', 'ws') || 'ws://localhost:8000'}/api/v1/ws/calls/monitor?token=${token}`
      const ws = new WebSocket(wsUrl)
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'call_update' && data.call.id === call.id) {
            // If there's a new message, reload call details
            if (data.call.new_message) {
              loadCallDetails()
            } else {
              // Update call details with other updates
              setCallDetails(prev => prev ? { ...prev, ...data.call } : prev)
            }
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error)
        }
      }
      
      wsRef.current = ws
      
      return () => {
        ws.close()
      }
    }
  }, [loadCallDetails, loadTranscript, call.id, token])

  const handleGenerateSummary = async () => {
    setGeneratingSummary(true)
    try {
      await callsAPI.generateSummary(call.id)
      toast.success('Résumé régénéré')
      await Promise.all([loadCallDetails(), loadTranscript()])
    } catch (error) {
      console.error('Failed to regenerate summary:', error)
      toast.error('Erreur lors de la régénération du résumé')
    } finally {
      setGeneratingSummary(false)
    }
  }

  const displayCall = callDetails ?? call
  const { actionRequests: modalActionRequests, others: modalOtherTags } = partitionFollowUpTags(displayCall.action_tags ?? [])
  const transcriptSource: any = transcript ?? displayCall.transcript
  const transcriptAvailable = Boolean(transcriptSource)
  const hasEmailRequest = modalActionRequests.some((tag) => tag.toLowerCase().includes('email'))

  useEffect(() => {
    setEmailForm((prev) => ({
      ...prev,
      subject: `Follow-up for call #${call.id}`
    }))
  }, [call.id])

  const handleEmailFieldChange = (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = event.target
    setEmailForm((prev) => ({
      ...prev,
      [name]: value
    }))
  }

  const handleSendEmail = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!emailForm.to_email.trim()) {
      toast.error('Recipient email is required')
      return
    }
    if (!emailForm.subject.trim()) {
      toast.error('Subject is required')
      return
    }
    if (!emailForm.body.trim()) {
      toast.error('Email body cannot be empty')
      return
    }

    try {
      setSendingEmail(true)
      await callsAPI.sendEmail(displayCall.id, {
        to_email: emailForm.to_email.trim(),
        subject: emailForm.subject.trim(),
        body: emailForm.body.trim(),
      })
      toast.success('Email sent successfully')
      setShowEmailComposer(false)
      setEmailForm({
        to_email: '',
        subject: `Follow-up for call #${call.id}`,
        body: ''
      })
      await loadCallDetails()
    } catch (error: any) {
      const message = error?.response?.data?.detail || 'Failed to send email'
      toast.error(message)
      console.error('Failed to send follow-up email:', error)
    } finally {
      setSendingEmail(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={onClose} />

        <div className="relative bg-white dark:bg-gray-800 rounded-lg max-w-3xl w-full p-6 shadow-xl max-h-[90vh] overflow-y-auto">
          <div className="mb-6">
            <h3 className="text-2xl font-bold text-gray-900 dark:text-white">
              Call Details
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Session ID: {displayCall.session_id}
            </p>
            {transcriptAvailable && (
              <button
                onClick={handleGenerateSummary}
                disabled={generatingSummary || loadingDetails}
                className="btn-primary mt-4 flex items-center"
              >
                <ClockIcon className="h-4 w-4 mr-2" />
                {generatingSummary
                  ? 'Régénération...'
                  : displayCall.summary
                    ? 'Régénérer le résumé'
                    : 'Générer un résumé'}
              </button>
            )}
          </div>

          <div className="space-y-6">
            {/* Metadata */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">Status</p>
                <p className="text-lg font-medium text-gray-900 dark:text-white capitalize">
                  {displayCall.status}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">Duration</p>
                <p className="text-lg font-medium text-gray-900 dark:text-white">
                  {displayCall.duration_minutes?.toFixed(1) || '0.0'} minutes
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">Cost</p>
                <p className="text-lg font-medium text-gray-900 dark:text-white">
                  ${displayCall.cost?.toFixed(2) || '0.00'}
                </p>
              </div>
              {displayCall.sentiment && (
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Sentiment</p>
                  <p className="text-lg font-medium text-gray-900 dark:text-white capitalize">
                    {displayCall.sentiment}
                  </p>
                </div>
              )}
            </div>

            {/* Follow-up tags */}
            {displayCall.action_tags && displayCall.action_tags.length > 0 && (
              <div>
                <h4 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                  Actions de suivi détectées
                </h4>
                {modalActionRequests.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-2">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200 uppercase tracking-wide">
                      Action Required
                    </span>
                    {modalActionRequests.map((tag, index) => (
                      <span
                        key={`modal-request-tag-${tag}-${index}`}
                        className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${getTagColor(tag)}`}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
                {modalOtherTags.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {modalOtherTags.map((tag, index) => (
                      <span
                        key={`modal-tag-${tag}-${index}`}
                        className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${getTagColor(tag)}`}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {hasEmailRequest && (
              <div className="rounded-lg border border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950/40 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h5 className="text-sm font-semibold text-amber-900 dark:text-amber-200">
                      Send follow-up email
                    </h5>
                    <p className="text-xs text-amber-700 dark:text-amber-300">
                      Complete the action request by emailing the customer directly.
                    </p>
                  </div>
                  <button
                    onClick={() => setShowEmailComposer((prev) => !prev)}
                    className="btn-secondary btn-xs"
                  >
                    {showEmailComposer ? 'Close' : 'Compose'}
                  </button>
                </div>

                {showEmailComposer && (
                  <form onSubmit={handleSendEmail} className="space-y-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                        To
                      </label>
                      <input
                        type="email"
                        name="to_email"
                        value={emailForm.to_email}
                        onChange={handleEmailFieldChange}
                        placeholder="customer@example.com"
                        className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Subject
                      </label>
                      <input
                        type="text"
                        name="subject"
                        value={emailForm.subject}
                        onChange={handleEmailFieldChange}
                        className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Message
                      </label>
                      <textarea
                        name="body"
                        rows={6}
                        value={emailForm.body}
                        onChange={handleEmailFieldChange}
                        className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                        placeholder="Draft your follow-up email..."
                        required
                      />
                    </div>
                    <div className="flex items-center justify-end gap-2">
                      <button
                        type="button"
                        className="btn-secondary btn-sm"
                        onClick={() => setShowEmailComposer(false)}
                        disabled={sendingEmail}
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        className="btn-primary btn-sm"
                        disabled={sendingEmail}
                      >
                        {sendingEmail ? 'Sending...' : 'Send email'}
                      </button>
                    </div>
                  </form>
                )}
              </div>
            )}

            {/* Action items */}
            {displayCall.action_items && displayCall.action_items.length > 0 && (
              <div>
                <h4 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                  Détails des actions à entreprendre
                </h4>
                <ul className="list-disc list-inside space-y-1 text-gray-700 dark:text-gray-300">
                  {displayCall.action_items.map((item, index) => (
                    <li key={`modal-action-${index}`}>{item}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Summary */}
            {displayCall.summary && (
              <div>
                <h4 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                  Summary
                </h4>
                <p className="text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-900 p-4 rounded-lg">
                  {displayCall.summary}
                </p>
              </div>
            )}

            {/* Messages - Real-time conversation */}
            {displayCall.messages && displayCall.messages.length > 0 && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-lg font-semibold text-gray-900 dark:text-white">
                    Messages {displayCall.status === 'in_progress' || displayCall.status === 'summarizing' ? (
                      <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                        Live
                      </span>
                    ) : null}
                  </h4>
                </div>
                <div className="bg-gray-50 dark:bg-gray-900 p-4 rounded-lg space-y-3 max-h-96 overflow-y-auto">
                  {displayCall.messages.map((message: any, index: number) => (
                    <div
                      key={index}
                      className={`p-3 rounded-lg ${
                        message.role === 'user'
                          ? 'bg-blue-50 dark:bg-blue-900/30 ml-8'
                          : message.role === 'system'
                          ? 'bg-gray-100 dark:bg-gray-800 mr-8'
                          : 'bg-gray-50 dark:bg-gray-800 mr-8'
                      }`}
                    >
                      <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                        {message.role === 'user' ? 'Visitor' : message.role === 'system' ? 'System' : 'Agent'} • {message.timestamp ? new Date(message.timestamp).toLocaleTimeString() : ''}
                      </div>
                      <div className="text-sm text-gray-900 dark:text-white">
                        {message.content}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Transcript */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Transcript
                </h4>
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {transcriptSource ? 'Transcript chargé' : 'Transcript indisponible'}
                </span>
              </div>
              {loadingTranscript ? (
                <div className="bg-gray-50 dark:bg-gray-900 p-4 rounded-lg animate-pulse">
                  <div className="h-20 bg-gray-200 dark:bg-gray-700 rounded"></div>
                </div>
              ) : transcriptSource ? (
                <div className="bg-gray-50 dark:bg-gray-900 p-4 rounded-lg space-y-3 max-h-96 overflow-y-auto">
                  {Array.isArray(transcriptSource) ? (
                    transcriptSource.map((message: any, index: number) => (
                      <div key={index} className="text-sm">
                        <span
                          className={`font-medium ${
                            message.role === 'user'
                              ? 'text-blue-600 dark:text-blue-400'
                              : 'text-green-600 dark:text-green-400'
                          }`}
                        >
                          {message.role === 'user' ? 'User' : 'Agent'}:
                        </span>
                        <span className="ml-2 text-gray-700 dark:text-gray-300">
                          {message.content}
                        </span>
                      </div>
                    ))
                  ) : (
                    <p className="text-gray-700 dark:text-gray-300">{transcriptSource}</p>
                  )}
                </div>
              ) : (
                <p className="text-gray-500 dark:text-gray-400 text-sm">No transcript available</p>
              )}
            </div>
          </div>

          <div className="mt-6 flex justify-end">
            <button onClick={onClose} className="btn-secondary">
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
