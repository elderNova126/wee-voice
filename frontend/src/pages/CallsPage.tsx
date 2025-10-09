import { useEffect, useState } from 'react'
import { PhoneIcon, ClockIcon, CurrencyDollarIcon } from '@heroicons/react/24/outline'
import DashboardLayout from '@/layouts/DashboardLayout'
import { callsAPI } from '@/lib/api'
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
  summary: string
  sentiment: string
}

export default function CallsPage() {
  const [calls, setCalls] = useState<Call[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedCall, setSelectedCall] = useState<Call | null>(null)

  useEffect(() => {
    loadCalls()
  }, [])

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
          {calls.map((call) => (
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
                    <div className="flex items-center gap-2 mb-1">
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
                    </div>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
                      {call.started_at ? formatDate(call.started_at) : 'Initializing...'}
                    </p>
                    {call.summary && (
                      <p className="text-sm text-gray-600 dark:text-gray-300 line-clamp-2">
                        {call.summary}
                      </p>
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
          ))}
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
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadTranscript()
  }, [call.id])

  const loadTranscript = async () => {
    try {
      const response = await callsAPI.getTranscript(call.id)
      setTranscript(response.data)
    } catch (error) {
      console.error('Failed to load transcript:', error)
    } finally {
      setLoading(false)
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
              Session ID: {call.session_id}
            </p>
          </div>

          <div className="space-y-6">
            {/* Metadata */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">Status</p>
                <p className="text-lg font-medium text-gray-900 dark:text-white capitalize">
                  {call.status}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">Duration</p>
                <p className="text-lg font-medium text-gray-900 dark:text-white">
                  {call.duration_minutes?.toFixed(1) || '0.0'} minutes
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">Cost</p>
                <p className="text-lg font-medium text-gray-900 dark:text-white">
                  ${call.cost?.toFixed(2) || '0.00'}
                </p>
              </div>
              {call.sentiment && (
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Sentiment</p>
                  <p className="text-lg font-medium text-gray-900 dark:text-white capitalize">
                    {call.sentiment}
                  </p>
                </div>
              )}
            </div>

            {/* Summary */}
            {call.summary && (
              <div>
                <h4 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                  Summary
                </h4>
                <p className="text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-900 p-4 rounded-lg">
                  {call.summary}
                </p>
              </div>
            )}

            {/* Transcript */}
            <div>
              <h4 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                Transcript
              </h4>
              {loading ? (
                <div className="bg-gray-50 dark:bg-gray-900 p-4 rounded-lg animate-pulse">
                  <div className="h-20 bg-gray-200 dark:bg-gray-700 rounded"></div>
                </div>
              ) : transcript ? (
                <div className="bg-gray-50 dark:bg-gray-900 p-4 rounded-lg space-y-3 max-h-96 overflow-y-auto">
                  {Array.isArray(transcript) ? (
                    transcript.map((message: any, index: number) => (
                      <div key={index} className="text-sm">
                        <span className={`font-medium ${
                          message.role === 'user' ? 'text-blue-600 dark:text-blue-400' : 'text-green-600 dark:text-green-400'
                        }`}>
                          {message.role === 'user' ? 'User' : 'Agent'}:
                        </span>
                        <span className="ml-2 text-gray-700 dark:text-gray-300">
                          {message.content}
                        </span>
                      </div>
                    ))
                  ) : (
                    <p className="text-gray-700 dark:text-gray-300">{transcript}</p>
                  )}
                </div>
              ) : (
                <p className="text-gray-500 dark:text-gray-400 text-sm">No transcript available</p>
              )}
            </div>
          </div>

          <div className="mt-6 flex justify-end">
            <button
              onClick={onClose}
              className="btn-secondary"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
