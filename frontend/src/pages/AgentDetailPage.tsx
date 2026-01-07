import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import {
  ArrowLeftIcon,
  PhoneIcon,
  UserGroupIcon,
  ChartBarIcon,
  ClockIcon,
  CurrencyDollarIcon,
  ChatBubbleLeftRightIcon,
  ExclamationTriangleIcon,
  FaceSmileIcon,
  FaceFrownIcon,
  MinusCircleIcon,
  CalendarIcon,
  PlayIcon,
  PencilIcon,
  MicrophoneIcon,
} from '@heroicons/react/24/outline'
import DashboardLayout from '@/layouts/DashboardLayout'
import { agentsAPI, callsAPI } from '@/lib/api'
import toast from 'react-hot-toast'
import { useTranslation } from '@/lib/translations'

interface Agent {
  id: number
  name: string
  description: string
  language: string
  is_active: boolean
  is_public: boolean
  interaction_mode: string
  created_at: string
}

interface AgentStats {
  total_calls: number
  total_minutes: number
  total_cost: number
  unique_leads: number
  action_required: number
  status_breakdown: Record<string, number>
  sentiment_breakdown: Record<string, number>
}

interface Lead {
  phone: string
  name: string | null
  call_count: number
  last_contact: string | null
  total_duration: number
  last_sentiment: string | null
  has_action_required: boolean
}

interface Call {
  id: number
  status: string
  duration_minutes: number
  cost: number
  started_at: string | null
  summary: string | null
  sentiment: string | null
  caller_phone: string | null
  caller_name: string | null
  action_tags: string[] | null
  has_messages: boolean
}

type TabType = 'overview' | 'leads' | 'calls'

export default function AgentDetailPage() {
  const t = useTranslation()
  const { agentId } = useParams<{ agentId: string }>()
  const navigate = useNavigate()
  
  const [agent, setAgent] = useState<Agent | null>(null)
  const [stats, setStats] = useState<AgentStats | null>(null)
  const [leads, setLeads] = useState<Lead[]>([])
  const [calls, setCalls] = useState<Call[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<TabType>('overview')

  useEffect(() => {
    if (agentId) {
      loadAgentData()
    }
  }, [agentId])

  const loadAgentData = async () => {
    if (!agentId) return
    
    setLoading(true)
    try {
      const [agentRes, statsRes, leadsRes, callsRes] = await Promise.all([
        agentsAPI.get(parseInt(agentId)),
        agentsAPI.getStats(parseInt(agentId)),
        agentsAPI.getLeads(parseInt(agentId)),
        callsAPI.list({ agent_id: parseInt(agentId), per_page: 20 })
      ])
      
      setAgent(agentRes.data)
      setStats(statsRes.data)
      setLeads(leadsRes.data.leads)
      setCalls(callsRes.data.items)
    } catch (error) {
      console.error('Failed to load agent data:', error)
      toast.error('Failed to load agent data')
      navigate('/dashboard/agents')
    } finally {
      setLoading(false)
    }
  }

  const getSentimentIcon = (sentiment: string | null) => {
    switch (sentiment?.toLowerCase()) {
      case 'positive':
        return <FaceSmileIcon className="h-5 w-5 text-green-500" />
      case 'negative':
        return <FaceFrownIcon className="h-5 w-5 text-red-500" />
      default:
        return <MinusCircleIcon className="h-5 w-5 text-gray-400" />
    }
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'N/A'
    return new Date(dateString).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const formatRelativeDate = (dateString: string | null) => {
    if (!dateString) return 'Never'
    const date = new Date(dateString)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const days = Math.floor(diff / (1000 * 60 * 60 * 24))
    
    if (days === 0) return 'Today'
    if (days === 1) return 'Yesterday'
    if (days < 7) return `${days} days ago`
    if (days < 30) return `${Math.floor(days / 7)} weeks ago`
    return date.toLocaleDateString()
  }

  if (loading) {
    return (
      <DashboardLayout>
        <div className="animate-pulse space-y-6">
          <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-1/4" />
          <div className="h-32 bg-gray-200 dark:bg-gray-700 rounded" />
          <div className="grid grid-cols-4 gap-4">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="h-24 bg-gray-200 dark:bg-gray-700 rounded" />
            ))}
          </div>
        </div>
      </DashboardLayout>
    )
  }

  if (!agent || !stats) {
    return (
      <DashboardLayout>
        <div className="text-center py-12">
          <p className="text-gray-600 dark:text-gray-400">Agent not found</p>
        </div>
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout>
      {/* Header */}
      <div className="mb-6">
        <Link
          to="/dashboard/agents"
          className="inline-flex items-center text-gray-600 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 mb-4 transition-colors"
        >
          <ArrowLeftIcon className="h-4 w-4 mr-2" />
          Back to Agents
        </Link>
        
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow-lg">
              {agent.interaction_mode === 'text' ? (
                <ChatBubbleLeftRightIcon className="h-8 w-8 text-white" />
              ) : agent.interaction_mode === 'both' ? (
                <div className="flex">
                  <MicrophoneIcon className="h-6 w-6 text-white" />
                  <ChatBubbleLeftRightIcon className="h-6 w-6 text-white" />
                </div>
              ) : (
                <MicrophoneIcon className="h-8 w-8 text-white" />
              )}
            </div>
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white">
                {agent.name}
              </h1>
              <p className="text-gray-600 dark:text-gray-400 text-sm mt-1">
                {agent.description || 'No description'}
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <Link
              to={`/dashboard/agents/${agent.id}/edit`}
              className="inline-flex items-center px-4 py-2 rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
            >
              <PencilIcon className="h-4 w-4 mr-2" />
              Edit
            </Link>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <StatCard
          icon={<PhoneIcon className="h-6 w-6" />}
          label="Total Calls"
          value={stats.total_calls}
          color="blue"
        />
        <StatCard
          icon={<UserGroupIcon className="h-6 w-6" />}
          label="Leads"
          value={stats.unique_leads}
          color="green"
        />
        <StatCard
          icon={<ClockIcon className="h-6 w-6" />}
          label="Minutes"
          value={`${stats.total_minutes.toFixed(1)}`}
          color="purple"
        />
        <StatCard
          icon={<CurrencyDollarIcon className="h-6 w-6" />}
          label="Cost"
          value={`$${stats.total_cost.toFixed(2)}`}
          color="amber"
        />
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700 mb-6">
        <nav className="flex space-x-4">
          {(['overview', 'leads', 'calls'] as TabType[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`pb-3 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === tab
                  ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
              }`}
            >
              {tab === 'overview' && <ChartBarIcon className="h-4 w-4 inline mr-2" />}
              {tab === 'leads' && <UserGroupIcon className="h-4 w-4 inline mr-2" />}
              {tab === 'calls' && <PhoneIcon className="h-4 w-4 inline mr-2" />}
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <OverviewTab stats={stats} />
      )}
      
      {activeTab === 'leads' && (
        <LeadsTab 
          leads={leads} 
          formatRelativeDate={formatRelativeDate}
          getSentimentIcon={getSentimentIcon}
        />
      )}
      
      {activeTab === 'calls' && (
        <CallsTab 
          calls={calls}
          formatDate={formatDate}
          getSentimentIcon={getSentimentIcon}
        />
      )}
    </DashboardLayout>
  )
}

// Stat Card Component
function StatCard({ 
  icon, 
  label, 
  value, 
  color 
}: { 
  icon: React.ReactNode
  label: string
  value: string | number
  color: 'blue' | 'green' | 'purple' | 'amber'
}) {
  const colorClasses = {
    blue: 'bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400',
    green: 'bg-green-50 dark:bg-green-900/30 text-green-600 dark:text-green-400',
    purple: 'bg-purple-50 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400',
    amber: 'bg-amber-50 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400',
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700 shadow-sm">
      <div className={`inline-flex p-2 rounded-lg ${colorClasses[color]} mb-3`}>
        {icon}
      </div>
      <p className="text-2xl font-bold text-gray-900 dark:text-white">{value}</p>
      <p className="text-sm text-gray-500 dark:text-gray-400">{label}</p>
    </div>
  )
}

// Overview Tab
function OverviewTab({ stats }: { stats: AgentStats }) {
  const totalSentiments = Object.values(stats.sentiment_breakdown).reduce((a, b) => a + b, 0)
  
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Call Status Breakdown */}
      <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Call Status
        </h3>
        <div className="space-y-3">
          {Object.entries(stats.status_breakdown).map(([status, count]) => (
            <div key={status} className="flex items-center justify-between">
              <span className="text-sm text-gray-600 dark:text-gray-400 capitalize">
                {status.replace('_', ' ')}
              </span>
              <div className="flex items-center gap-2">
                <div className="w-24 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-blue-500 rounded-full"
                    style={{ width: `${(count / stats.total_calls) * 100}%` }}
                  />
                </div>
                <span className="text-sm font-medium text-gray-900 dark:text-white w-8 text-right">
                  {count}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Sentiment Analysis */}
      <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Sentiment Analysis
        </h3>
        {totalSentiments > 0 ? (
          <div className="space-y-4">
            {Object.entries(stats.sentiment_breakdown).map(([sentiment, count]) => {
              const percentage = ((count / totalSentiments) * 100).toFixed(0)
              const color = sentiment === 'positive' ? 'bg-green-500' 
                         : sentiment === 'negative' ? 'bg-red-500' 
                         : 'bg-gray-400'
              return (
                <div key={sentiment} className="flex items-center gap-3">
                  {sentiment === 'positive' && <FaceSmileIcon className="h-5 w-5 text-green-500" />}
                  {sentiment === 'negative' && <FaceFrownIcon className="h-5 w-5 text-red-500" />}
                  {sentiment === 'neutral' && <MinusCircleIcon className="h-5 w-5 text-gray-400" />}
                  <div className="flex-1">
                    <div className="flex justify-between mb-1">
                      <span className="text-sm text-gray-600 dark:text-gray-400 capitalize">
                        {sentiment}
                      </span>
                      <span className="text-sm font-medium text-gray-900 dark:text-white">
                        {percentage}%
                      </span>
                    </div>
                    <div className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                      <div 
                        className={`h-full ${color} rounded-full`}
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <p className="text-gray-500 dark:text-gray-400 text-center py-8">
            No sentiment data available yet
          </p>
        )}
      </div>

      {/* Quick Stats */}
      <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700 lg:col-span-2">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Summary
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="text-center p-4 bg-gray-50 dark:bg-gray-900 rounded-lg">
            <p className="text-3xl font-bold text-gray-900 dark:text-white">
              {stats.total_calls > 0 ? (stats.total_minutes / stats.total_calls).toFixed(1) : '0'}
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400">Avg. Duration (min)</p>
          </div>
          <div className="text-center p-4 bg-gray-50 dark:bg-gray-900 rounded-lg">
            <p className="text-3xl font-bold text-gray-900 dark:text-white">
              ${stats.total_calls > 0 ? (stats.total_cost / stats.total_calls).toFixed(3) : '0'}
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400">Avg. Cost/Call</p>
          </div>
          <div className="text-center p-4 bg-gray-50 dark:bg-gray-900 rounded-lg">
            <p className="text-3xl font-bold text-gray-900 dark:text-white">
              {stats.unique_leads > 0 ? (stats.total_calls / stats.unique_leads).toFixed(1) : '0'}
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400">Calls/Lead</p>
          </div>
          <div className="text-center p-4 bg-amber-50 dark:bg-amber-900/20 rounded-lg">
            <p className="text-3xl font-bold text-amber-600 dark:text-amber-400">
              {stats.action_required}
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400">Actions Required</p>
          </div>
        </div>
      </div>
    </div>
  )
}

// Leads Tab
function LeadsTab({ 
  leads, 
  formatRelativeDate,
  getSentimentIcon
}: { 
  leads: Lead[]
  formatRelativeDate: (date: string | null) => string
  getSentimentIcon: (sentiment: string | null) => React.ReactNode
}) {
  if (leads.length === 0) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-xl p-12 border border-gray-200 dark:border-gray-700 text-center">
        <UserGroupIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
          No Leads Yet
        </h3>
        <p className="text-gray-500 dark:text-gray-400">
          Leads will appear here when callers with phone numbers contact this agent.
        </p>
      </div>
    )
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-50 dark:bg-gray-900">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Contact
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Calls
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Duration
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Last Contact
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Status
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
            {leads.map((lead) => (
              <tr key={lead.phone} className="hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center">
                    <div className="w-10 h-10 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center text-blue-600 dark:text-blue-400 font-medium">
                      {lead.name ? lead.name.charAt(0).toUpperCase() : '#'}
                    </div>
                    <div className="ml-4">
                      <p className="text-sm font-medium text-gray-900 dark:text-white">
                        {lead.name || 'Unknown'}
                      </p>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        {lead.phone}
                      </p>
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className="text-sm text-gray-900 dark:text-white">
                    {lead.call_count}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className="text-sm text-gray-900 dark:text-white">
                    {lead.total_duration.toFixed(1)} min
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    {formatRelativeDate(lead.last_contact)}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center gap-2">
                    {getSentimentIcon(lead.last_sentiment)}
                    {lead.has_action_required && (
                      <ExclamationTriangleIcon className="h-5 w-5 text-amber-500" title="Action Required" />
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// Calls Tab
function CallsTab({ 
  calls, 
  formatDate,
  getSentimentIcon
}: { 
  calls: Call[]
  formatDate: (date: string | null) => string
  getSentimentIcon: (sentiment: string | null) => React.ReactNode
}) {
  const navigate = useNavigate()
  
  if (calls.length === 0) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-xl p-12 border border-gray-200 dark:border-gray-700 text-center">
        <PhoneIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
          No Calls Yet
        </h3>
        <p className="text-gray-500 dark:text-gray-400">
          Call history will appear here when this agent handles calls.
        </p>
      </div>
    )
  }

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'completed':
        return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
      case 'failed':
        return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
      case 'in_progress':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
    }
  }

  return (
    <div className="space-y-3">
      {calls.map((call) => (
        <div
          key={call.id}
          onClick={() => navigate(`/dashboard/calls?callId=${call.id}`)}
          className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700 hover:shadow-md hover:border-blue-300 dark:hover:border-blue-700 transition-all cursor-pointer"
        >
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-4 flex-1 min-w-0">
              <div className={`p-2 rounded-lg ${
                call.has_messages && !call.caller_phone
                  ? 'bg-purple-100 dark:bg-purple-900/30'
                  : 'bg-blue-100 dark:bg-blue-900/30'
              }`}>
                {call.has_messages && !call.caller_phone ? (
                  <ChatBubbleLeftRightIcon className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                ) : (
                  <PhoneIcon className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-gray-900 dark:text-white">
                    {call.caller_phone || call.caller_name || `Call #${call.id}`}
                  </span>
                  <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${getStatusColor(call.status)}`}>
                    {call.status}
                  </span>
                  {call.sentiment && getSentimentIcon(call.sentiment)}
                </div>
                {call.summary && (
                  <p className="text-sm text-gray-500 dark:text-gray-400 truncate mt-1">
                    {call.summary}
                  </p>
                )}
              </div>
            </div>
            <div className="text-right flex-shrink-0">
              <p className="text-sm text-gray-900 dark:text-white">
                {call.duration_minutes.toFixed(1)} min
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {formatDate(call.started_at)}
              </p>
            </div>
          </div>
        </div>
      ))}
      
      <Link
        to="/dashboard/calls"
        className="block text-center text-blue-600 dark:text-blue-400 hover:underline py-4"
      >
        View all calls →
      </Link>
    </div>
  )
}

