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
  PhoneArrowUpRightIcon,
  XMarkIcon,
  DocumentTextIcon,
  PlusIcon,
  TrashIcon,
  StarIcon,
} from '@heroicons/react/24/outline'
import { StarIcon as StarIconSolid } from '@heroicons/react/24/solid'
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

interface PhoneNumber {
  phone_number: string
  is_registered: boolean
  agent_id?: number
  status?: string
  country_code?: string
}

interface OutboundScript {
  id: number
  agent_id: number
  name: string
  description: string | null
  opening_message: string
  main_content: string | null
  closing_message: string | null
  tone: string
  objective: string | null
  key_points: string | null
  objection_handling: string | null
  is_active: boolean
  is_favorite: boolean
  use_count: number
  last_used_at: string | null
  created_at: string
}

type TabType = 'overview' | 'leads' | 'calls' | 'scripts'

export default function AgentDetailPage() {
  const t = useTranslation()
  const { agentId } = useParams<{ agentId: string }>()
  const navigate = useNavigate()
  
  const [agent, setAgent] = useState<Agent | null>(null)
  const [stats, setStats] = useState<AgentStats | null>(null)
  const [leads, setLeads] = useState<Lead[]>([])
  const [calls, setCalls] = useState<Call[]>([])
  const [scripts, setScripts] = useState<OutboundScript[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<TabType>('overview')
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null)
  const [showCallModal, setShowCallModal] = useState(false)
  const [showScriptModal, setShowScriptModal] = useState(false)
  const [editingScript, setEditingScript] = useState<OutboundScript | null>(null)

  useEffect(() => {
    if (agentId) {
      loadAgentData()
    }
  }, [agentId])

  const loadAgentData = async () => {
    if (!agentId) return
    
    setLoading(true)
    try {
      const [agentRes, statsRes, leadsRes, callsRes, scriptsRes] = await Promise.all([
        agentsAPI.get(parseInt(agentId)),
        agentsAPI.getStats(parseInt(agentId)),
        agentsAPI.getLeads(parseInt(agentId)),
        callsAPI.list({ agent_id: parseInt(agentId), per_page: 20 }),
        agentsAPI.listScripts(parseInt(agentId))
      ])
      
      setAgent(agentRes.data)
      setStats(statsRes.data)
      setLeads(leadsRes.data.leads)
      setCalls(callsRes.data.items)
      setScripts(scriptsRes.data)
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
          {(['overview', 'leads', 'calls', 'scripts'] as TabType[]).map((tab) => (
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
              {tab === 'scripts' && <DocumentTextIcon className="h-4 w-4 inline mr-2" />}
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
              {tab === 'scripts' && scripts.length > 0 && (
                <span className="ml-1.5 px-1.5 py-0.5 text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-full">
                  {scripts.length}
                </span>
              )}
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
          onCallLead={(lead) => {
            setSelectedLead(lead)
            setShowCallModal(true)
          }}
        />
      )}
      
      {activeTab === 'calls' && (
        <CallsTab 
          calls={calls}
          formatDate={formatDate}
          getSentimentIcon={getSentimentIcon}
        />
      )}
      
      {activeTab === 'scripts' && agent && (
        <ScriptsTab
          scripts={scripts}
          agentId={agent.id}
          onCreateNew={() => {
            setEditingScript(null)
            setShowScriptModal(true)
          }}
          onEdit={(script) => {
            setEditingScript(script)
            setShowScriptModal(true)
          }}
          onRefresh={loadAgentData}
        />
      )}
      
      {/* Outbound Call Modal */}
      {showCallModal && selectedLead && agent && (
        <OutboundCallModal
          lead={selectedLead}
          agentId={agent.id}
          agentName={agent.name}
          scripts={scripts.filter(s => s.is_active)}
          onClose={() => {
            setShowCallModal(false)
            setSelectedLead(null)
          }}
          onSuccess={() => {
            setShowCallModal(false)
            setSelectedLead(null)
            loadAgentData()
          }}
        />
      )}
      
      {/* Script Edit Modal */}
      {showScriptModal && agent && (
        <ScriptModal
          agentId={agent.id}
          script={editingScript}
          onClose={() => {
            setShowScriptModal(false)
            setEditingScript(null)
          }}
          onSave={() => {
            setShowScriptModal(false)
            setEditingScript(null)
            loadAgentData()
          }}
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
  getSentimentIcon,
  onCallLead
}: { 
  leads: Lead[]
  formatRelativeDate: (date: string | null) => string
  getSentimentIcon: (sentiment: string | null) => React.ReactNode
  onCallLead: (lead: Lead) => void
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
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Actions
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
                <td className="px-6 py-4 whitespace-nowrap text-right">
                  <button
                    onClick={() => onCallLead(lead)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700 text-white text-sm font-medium shadow-sm hover:shadow-md transition-all"
                    title="Call this lead"
                  >
                    <PhoneArrowUpRightIcon className="h-4 w-4" />
                    Call
                  </button>
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

// Outbound Call Modal
function OutboundCallModal({
  lead,
  agentId,
  agentName,
  scripts,
  onClose,
  onSuccess
}: {
  lead: Lead
  agentId: number
  agentName: string
  scripts: OutboundScript[]
  onClose: () => void
  onSuccess: () => void
}) {
  const [phoneNumbers, setPhoneNumbers] = useState<PhoneNumber[]>([])
  const [selectedPhone, setSelectedPhone] = useState<string>('')
  const [selectedScript, setSelectedScript] = useState<OutboundScript | null>(null)
  const [loading, setLoading] = useState(true)
  const [calling, setCalling] = useState(false)
  const [callStatus, setCallStatus] = useState<'idle' | 'calling' | 'connected' | 'error'>('idle')
  const [errorMessage, setErrorMessage] = useState('')

  useEffect(() => {
    loadPhoneNumbers()
    // Pre-select favorite script if available
    const favoriteScript = scripts.find(s => s.is_favorite)
    if (favoriteScript) {
      setSelectedScript(favoriteScript)
    }
  }, [scripts])

  const loadPhoneNumbers = async () => {
    try {
      const response = await callsAPI.getAvailablePhoneNumbers(agentId)
      const numbers = response.data.phone_numbers || []
      setPhoneNumbers(numbers)
      if (numbers.length > 0) {
        setSelectedPhone(numbers[0].phone_number)
      }
    } catch (error) {
      console.error('Failed to load phone numbers:', error)
      toast.error('Failed to load available phone numbers')
    } finally {
      setLoading(false)
    }
  }

  const handleCall = async () => {
    if (!selectedPhone) {
      toast.error('Please select a phone number to call from')
      return
    }

    setCalling(true)
    setCallStatus('calling')
    setErrorMessage('')

    try {
      const response = await callsAPI.makeOutboundCall({
        from_phone_number: selectedPhone,
        to_number: lead.phone,
        agent_id: agentId,
        script_id: selectedScript?.id
      })

      if (response.data.success) {
        setCallStatus('connected')
        toast.success('Call initiated successfully!')
        setTimeout(() => {
          onSuccess()
        }, 2000)
      } else {
        setCallStatus('error')
        setErrorMessage(response.data.message || 'Failed to initiate call')
        toast.error(response.data.message || 'Failed to initiate call')
      }
    } catch (error: any) {
      setCallStatus('error')
      const message = error?.response?.data?.detail || 'Failed to initiate call'
      setErrorMessage(message)
      toast.error(message)
    } finally {
      setCalling(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 backdrop-blur-sm">
      <div className="fixed inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-w-md w-full p-6 z-10 border border-gray-200 dark:border-gray-700">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-bold text-gray-900 dark:text-white">
            Call Lead
          </h3>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >
            <XMarkIcon className="h-5 w-5 text-gray-500" />
          </button>
        </div>

        {/* Lead Info */}
        <div className="bg-gray-50 dark:bg-gray-900 rounded-xl p-4 mb-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center text-white font-bold text-lg">
              {lead.name ? lead.name.charAt(0).toUpperCase() : '#'}
            </div>
            <div>
              <p className="font-medium text-gray-900 dark:text-white">
                {lead.name || 'Unknown'}
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {lead.phone}
              </p>
            </div>
          </div>
        </div>

        {/* Agent Info */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            AI Agent
          </label>
          <div className="flex items-center gap-3 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
            <MicrophoneIcon className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            <span className="text-sm font-medium text-blue-900 dark:text-blue-100">
              {agentName}
            </span>
          </div>
        </div>

        {/* Script Selection */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Call Script (Optional)
          </label>
          {scripts.length === 0 ? (
            <div className="p-4 bg-gray-50 dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700">
              <p className="text-sm text-gray-600 dark:text-gray-400">
                No outbound scripts created yet. The agent will use its default behavior.
              </p>
            </div>
          ) : (
            <div className="space-y-2 max-h-40 overflow-y-auto">
              {/* No Script Option */}
              <label
                className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all ${
                  !selectedScript
                    ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/20'
                    : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
                }`}
              >
                <input
                  type="radio"
                  name="script"
                  checked={!selectedScript}
                  onChange={() => setSelectedScript(null)}
                  className="text-purple-600 focus:ring-purple-500"
                />
                <div className="flex-1">
                  <span className="font-medium text-gray-900 dark:text-white">
                    No script (default behavior)
                  </span>
                </div>
              </label>
              
              {/* Available Scripts */}
              {scripts.map((script) => (
                <label
                  key={script.id}
                  className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all ${
                    selectedScript?.id === script.id
                      ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/20'
                      : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
                  }`}
                >
                  <input
                    type="radio"
                    name="script"
                    checked={selectedScript?.id === script.id}
                    onChange={() => setSelectedScript(script)}
                    className="text-purple-600 focus:ring-purple-500"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-900 dark:text-white truncate">
                        {script.name}
                      </span>
                      {script.is_favorite && (
                        <StarIconSolid className="h-4 w-4 text-yellow-500 flex-shrink-0" />
                      )}
                    </div>
                    {script.description && (
                      <p className="text-xs text-gray-500 dark:text-gray-400 truncate mt-0.5">
                        {script.description}
                      </p>
                    )}
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400">
                        {script.tone}
                      </span>
                      <span className="text-xs text-gray-400">
                        Used {script.use_count}x
                      </span>
                    </div>
                  </div>
                </label>
              ))}
            </div>
          )}
        </div>

        {/* Phone Number Selection */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Call From
          </label>
          {loading ? (
            <div className="p-3 bg-gray-100 dark:bg-gray-700 rounded-lg animate-pulse">
              <div className="h-5 bg-gray-300 dark:bg-gray-600 rounded w-3/4" />
            </div>
          ) : phoneNumbers.length === 0 ? (
            <div className="p-4 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-200 dark:border-amber-800">
              <p className="text-sm text-amber-800 dark:text-amber-200">
                No phone number assigned to this agent. Please assign an active phone number to <strong>{agentName}</strong> first.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {phoneNumbers.map((phone) => (
                <label
                  key={phone.phone_number}
                  className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all ${
                    selectedPhone === phone.phone_number
                      ? 'border-green-500 bg-green-50 dark:bg-green-900/20'
                      : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
                  }`}
                >
                  <input
                    type="radio"
                    name="phone"
                    value={phone.phone_number}
                    checked={selectedPhone === phone.phone_number}
                    onChange={(e) => setSelectedPhone(e.target.value)}
                    className="text-green-600 focus:ring-green-500"
                  />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-900 dark:text-white">
                        {phone.phone_number}
                      </span>
                      {phone.country_code && (
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          ({phone.country_code})
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`text-xs px-1.5 py-0.5 rounded ${
                        phone.status === 'active' 
                          ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                          : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
                      }`}>
                        {phone.status || 'unknown'}
                      </span>
                      {phone.is_registered && (
                        <span className="text-xs text-green-600 dark:text-green-400">
                          ✓ SIP Ready
                        </span>
                      )}
                    </div>
                  </div>
                </label>
              ))}
            </div>
          )}
        </div>

        {/* Status Display */}
        {callStatus === 'calling' && (
          <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
            <div className="flex items-center gap-3">
              <div className="animate-spin rounded-full h-5 w-5 border-2 border-blue-600 border-t-transparent" />
              <span className="text-sm text-blue-800 dark:text-blue-200">
                Initiating call...
              </span>
            </div>
          </div>
        )}

        {callStatus === 'connected' && (
          <div className="mb-6 p-4 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
            <div className="flex items-center gap-3">
              <PhoneIcon className="h-5 w-5 text-green-600 animate-pulse" />
              <span className="text-sm text-green-800 dark:text-green-200">
                Call initiated! The AI agent is now handling the call.
              </span>
            </div>
          </div>
        )}

        {callStatus === 'error' && (
          <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
            <p className="text-sm text-red-800 dark:text-red-200">
              {errorMessage}
            </p>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-3 rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-medium hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleCall}
            disabled={calling || !selectedPhone || phoneNumbers.length === 0 || callStatus === 'connected'}
            className="flex-1 inline-flex justify-center items-center gap-2 px-4 py-3 rounded-lg bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700 disabled:from-gray-400 disabled:to-gray-500 text-white font-medium shadow-lg hover:shadow-xl disabled:shadow-none transition-all"
          >
            {calling ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                Calling...
              </>
            ) : (
              <>
                <PhoneArrowUpRightIcon className="h-5 w-5" />
                Start Call
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

// Scripts Tab Component
function ScriptsTab({
  scripts,
  agentId,
  onCreateNew,
  onEdit,
  onRefresh
}: {
  scripts: OutboundScript[]
  agentId: number
  onCreateNew: () => void
  onEdit: (script: OutboundScript) => void
  onRefresh: () => void
}) {
  const handleToggleFavorite = async (script: OutboundScript) => {
    try {
      await agentsAPI.toggleScriptFavorite(agentId, script.id)
      onRefresh()
    } catch (error) {
      console.error('Failed to toggle favorite:', error)
      toast.error('Failed to update favorite status')
    }
  }

  const handleDelete = async (script: OutboundScript) => {
    if (!confirm(`Are you sure you want to delete "${script.name}"?`)) return
    
    try {
      await agentsAPI.deleteScript(agentId, script.id)
      toast.success('Script deleted')
      onRefresh()
    } catch (error) {
      console.error('Failed to delete script:', error)
      toast.error('Failed to delete script')
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Outbound Call Scripts
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Create and manage scripts for outbound calls. Scripts guide the AI agent's conversation.
          </p>
        </div>
        <button
          onClick={onCreateNew}
          className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-500 to-indigo-600 hover:from-purple-600 hover:to-indigo-700 text-white font-medium rounded-lg shadow-md hover:shadow-lg transition-all"
        >
          <PlusIcon className="h-5 w-5" />
          New Script
        </button>
      </div>

      {/* Scripts List */}
      {scripts.length === 0 ? (
        <div className="text-center py-12 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
          <DocumentTextIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h4 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            No scripts yet
          </h4>
          <p className="text-gray-600 dark:text-gray-400 mb-6 max-w-sm mx-auto">
            Create your first outbound call script to guide AI conversations with leads.
          </p>
          <button
            onClick={onCreateNew}
            className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white font-medium rounded-lg transition-colors"
          >
            <PlusIcon className="h-5 w-5" />
            Create Your First Script
          </button>
        </div>
      ) : (
        <div className="grid gap-4">
          {scripts.map((script) => (
            <div
              key={script.id}
              className="bg-white dark:bg-gray-800 rounded-xl p-5 border border-gray-200 dark:border-gray-700 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-2">
                    <h4 className="text-lg font-semibold text-gray-900 dark:text-white truncate">
                      {script.name}
                    </h4>
                    <button
                      onClick={() => handleToggleFavorite(script)}
                      className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                      title={script.is_favorite ? 'Remove from favorites' : 'Add to favorites'}
                    >
                      {script.is_favorite ? (
                        <StarIconSolid className="h-5 w-5 text-yellow-500" />
                      ) : (
                        <StarIcon className="h-5 w-5 text-gray-400 hover:text-yellow-500" />
                      )}
                    </button>
                    {!script.is_active && (
                      <span className="px-2 py-0.5 text-xs font-medium rounded bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400">
                        Inactive
                      </span>
                    )}
                  </div>
                  
                  {script.description && (
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                      {script.description}
                    </p>
                  )}
                  
                  {/* Opening Message Preview */}
                  <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-3 mb-3">
                    <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Opening:</p>
                    <p className="text-sm text-gray-700 dark:text-gray-300 line-clamp-2">
                      "{script.opening_message}"
                    </p>
                  </div>
                  
                  {/* Meta Info */}
                  <div className="flex flex-wrap items-center gap-3 text-sm">
                    <span className="px-2 py-1 rounded-full bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400">
                      {script.tone}
                    </span>
                    {script.objective && (
                      <span className="text-gray-600 dark:text-gray-400">
                        Goal: {script.objective.slice(0, 50)}{script.objective.length > 50 ? '...' : ''}
                      </span>
                    )}
                    <span className="text-gray-500 dark:text-gray-500">
                      Used {script.use_count}x
                    </span>
                    {script.last_used_at && (
                      <span className="text-gray-400 dark:text-gray-500">
                        Last: {new Date(script.last_used_at).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </div>
                
                {/* Actions */}
                <div className="flex items-center gap-2 flex-shrink-0">
                  <button
                    onClick={() => onEdit(script)}
                    className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400 transition-colors"
                    title="Edit script"
                  >
                    <PencilIcon className="h-5 w-5" />
                  </button>
                  <button
                    onClick={() => handleDelete(script)}
                    className="p-2 rounded-lg hover:bg-red-100 dark:hover:bg-red-900/30 text-gray-600 dark:text-gray-400 hover:text-red-600 dark:hover:text-red-400 transition-colors"
                    title="Delete script"
                  >
                    <TrashIcon className="h-5 w-5" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// Script Modal Component
function ScriptModal({
  agentId,
  script,
  onClose,
  onSave
}: {
  agentId: number
  script: OutboundScript | null
  onClose: () => void
  onSave: () => void
}) {
  const [saving, setSaving] = useState(false)
  const [formData, setFormData] = useState({
    name: script?.name || '',
    description: script?.description || '',
    opening_message: script?.opening_message || '',
    main_content: script?.main_content || '',
    closing_message: script?.closing_message || '',
    tone: script?.tone || 'professional',
    objective: script?.objective || '',
    key_points: script?.key_points || '',
    objection_handling: script?.objection_handling || '',
    is_active: script?.is_active ?? true,
    is_favorite: script?.is_favorite ?? false
  })

  const toneOptions = [
    { value: 'professional', label: 'Professional', desc: 'Formal and business-like' },
    { value: 'friendly', label: 'Friendly', desc: 'Warm and approachable' },
    { value: 'casual', label: 'Casual', desc: 'Relaxed and conversational' },
    { value: 'formal', label: 'Formal', desc: 'Very proper and respectful' },
    { value: 'enthusiastic', label: 'Enthusiastic', desc: 'Energetic and excited' }
  ]

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!formData.name.trim()) {
      toast.error('Please enter a script name')
      return
    }
    if (!formData.opening_message.trim()) {
      toast.error('Please enter an opening message')
      return
    }

    setSaving(true)
    try {
      if (script) {
        await agentsAPI.updateScript(agentId, script.id, formData)
        toast.success('Script updated successfully')
      } else {
        await agentsAPI.createScript(agentId, formData)
        toast.success('Script created successfully')
      }
      onSave()
    } catch (error: any) {
      console.error('Failed to save script:', error)
      toast.error(error?.response?.data?.detail || 'Failed to save script')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 backdrop-blur-sm">
      <div className="fixed inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-hidden z-10 border border-gray-200 dark:border-gray-700">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-xl font-bold text-gray-900 dark:text-white">
            {script ? 'Edit Script' : 'New Outbound Script'}
          </h3>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >
            <XMarkIcon className="h-5 w-5 text-gray-500" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 overflow-y-auto max-h-[calc(90vh-180px)]">
          <div className="space-y-6">
            {/* Basic Info */}
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Script Name *
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., Product Demo Intro"
                  className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-white focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>
              
              <div className="sm:col-span-2">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Description
                </label>
                <input
                  type="text"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Brief description of when to use this script"
                  className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-white focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Tone
                </label>
                <select
                  value={formData.tone}
                  onChange={(e) => setFormData({ ...formData, tone: e.target.value })}
                  className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-white focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                >
                  {toneOptions.map(opt => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label} - {opt.desc}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Call Objective
                </label>
                <input
                  type="text"
                  value={formData.objective}
                  onChange={(e) => setFormData({ ...formData, objective: e.target.value })}
                  placeholder="e.g., Schedule a demo"
                  className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-white focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>
            </div>

            {/* Script Content */}
            <div className="space-y-4 border-t border-gray-200 dark:border-gray-700 pt-6">
              <h4 className="text-sm font-semibold text-gray-900 dark:text-white">
                Script Content
              </h4>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Opening Message * <span className="text-gray-400 font-normal">(What the agent says first)</span>
                </label>
                <textarea
                  value={formData.opening_message}
                  onChange={(e) => setFormData({ ...formData, opening_message: e.target.value })}
                  placeholder="Hello! This is [Agent Name] from [Company]. Am I speaking with [Lead Name]? I'm calling because..."
                  rows={3}
                  className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-white focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Main Content <span className="text-gray-400 font-normal">(Key talking points)</span>
                </label>
                <textarea
                  value={formData.main_content}
                  onChange={(e) => setFormData({ ...formData, main_content: e.target.value })}
                  placeholder="Main points to cover during the call..."
                  rows={4}
                  className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-white focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Closing Message <span className="text-gray-400 font-normal">(How to wrap up)</span>
                </label>
                <textarea
                  value={formData.closing_message}
                  onChange={(e) => setFormData({ ...formData, closing_message: e.target.value })}
                  placeholder="Thank you for your time. To summarize..."
                  rows={2}
                  className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-white focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>
            </div>

            {/* Advanced Settings */}
            <div className="space-y-4 border-t border-gray-200 dark:border-gray-700 pt-6">
              <h4 className="text-sm font-semibold text-gray-900 dark:text-white">
                Advanced Settings
              </h4>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Key Points <span className="text-gray-400 font-normal">(One per line)</span>
                </label>
                <textarea
                  value={formData.key_points}
                  onChange={(e) => setFormData({ ...formData, key_points: e.target.value })}
                  placeholder="- Introduce the product&#10;- Ask about current challenges&#10;- Present solution benefits"
                  rows={3}
                  className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-white focus:ring-2 focus:ring-purple-500 focus:border-transparent font-mono text-sm"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Objection Handling
                </label>
                <textarea
                  value={formData.objection_handling}
                  onChange={(e) => setFormData({ ...formData, objection_handling: e.target.value })}
                  placeholder="How to respond to common objections like 'I'm not interested' or 'Call me back later'..."
                  rows={3}
                  className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-white focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>

              {/* Toggles */}
              <div className="flex flex-wrap gap-6">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.is_active}
                    onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                    className="rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                  />
                  <span className="text-sm text-gray-700 dark:text-gray-300">Active</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.is_favorite}
                    onChange={(e) => setFormData({ ...formData, is_favorite: e.target.checked })}
                    className="rounded border-gray-300 text-yellow-500 focus:ring-yellow-500"
                  />
                  <span className="text-sm text-gray-700 dark:text-gray-300">Mark as favorite</span>
                </label>
              </div>
            </div>
          </div>
        </form>

        {/* Footer */}
        <div className="flex gap-3 p-6 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 px-4 py-3 rounded-lg bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-medium hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={saving}
            className="flex-1 inline-flex justify-center items-center gap-2 px-4 py-3 rounded-lg bg-gradient-to-r from-purple-500 to-indigo-600 hover:from-purple-600 hover:to-indigo-700 disabled:from-gray-400 disabled:to-gray-500 text-white font-medium shadow-lg hover:shadow-xl disabled:shadow-none transition-all"
          >
            {saving ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                Saving...
              </>
            ) : (
              <>
                {script ? 'Update Script' : 'Create Script'}
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

