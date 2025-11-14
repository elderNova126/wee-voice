import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { 
  MicrophoneIcon, 
  PhoneIcon, 
  ClockIcon,
  CurrencyDollarIcon,
  PlusIcon,
  KeyIcon,
  PlayIcon
} from '@heroicons/react/24/outline'
import DashboardLayout from '@/layouts/DashboardLayout'
import { agentsAPI, callsAPI } from '@/lib/api'
import { StatCard } from '@/components/ui'
import toast from 'react-hot-toast'
import { useTranslation } from '@/lib/translations'

interface Stats {
  total_agents: number
  total_calls: number
  total_minutes: number
  total_cost: number
}

export default function DashboardPage() {
  const t = useTranslation()
  const [stats, setStats] = useState<Stats>({
    total_agents: 0,
    total_calls: 0,
    total_minutes: 0,
    total_cost: 0
  })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadStats()
  }, [])

  const loadStats = async () => {
    try {
      // Use the stats endpoint which provides all the data we need
      const [agentsResponse, statsResponse] = await Promise.all([
        agentsAPI.list(),
        callsAPI.getStats(30) // Get stats for last 30 days
      ])

      const agents = agentsResponse.data
      const stats = statsResponse.data

      // Use stats endpoint data directly - it already has totals for all calls
      setStats({
        total_agents: agents.length,
        total_calls: stats.total_calls || 0,
        total_minutes: stats.total_minutes || 0,
        total_cost: stats.total_cost || 0
      })
    } catch (error) {
      console.error('Failed to load stats:', error)
      toast.error(t.dashboard.statsLoadError)
    } finally {
      setLoading(false)
    }
  }

  return (
    <DashboardLayout>
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold bg-gradient-to-r from-gray-900 to-gray-600 dark:from-white dark:to-gray-300 bg-clip-text text-transparent mb-2">
          {t.dashboard.title}
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          {t.dashboard.welcomeMessage}
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4 mb-8">
        <StatCard
          title={t.dashboard.totalAgents}
          value={stats.total_agents}
          icon={<MicrophoneIcon className="w-5 h-5" />}
          iconColor="from-blue-500 to-blue-600"
          subtitle={t.dashboard.totalAgentsSubtitle}
          loading={loading}
        />
        <StatCard
          title={t.dashboard.totalCalls}
          value={stats.total_calls}
          icon={<PhoneIcon className="w-5 h-5" />}
          iconColor="from-green-500 to-green-600"
          subtitle={t.dashboard.totalCallsSubtitle}
          loading={loading}
        />
        <StatCard
          title={t.dashboard.totalMinutes}
          value={stats.total_minutes.toFixed(1)}
          icon={<ClockIcon className="w-5 h-5" />}
          iconColor="from-purple-500 to-purple-600"
          subtitle={t.dashboard.totalMinutesSubtitle}
          loading={loading}
        />
        <StatCard
          title={t.dashboard.totalCost}
          value={`$${stats.total_cost.toFixed(2)}`}
          icon={<CurrencyDollarIcon className="w-5 h-5" />}
          iconColor="from-orange-500 to-orange-600"
          subtitle={t.dashboard.totalCostSubtitle}
          loading={loading}
        />
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-6">
          {t.dashboard.quickActions}
        </h2>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          <Link
            to="/dashboard/agents/new"
            className="group relative overflow-hidden bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 hover:shadow-lg transition-all duration-200"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/10 to-purple-600/10 opacity-0 group-hover:opacity-100 transition-opacity duration-200"></div>
            <div className="relative">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center mb-4">
                <PlusIcon className="w-6 h-6 text-white" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                {t.quickActions.createAgent}
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                {t.quickActions.createAgentDesc}
              </p>
            </div>
          </Link>

          <Link
            to="/dashboard/api-keys"
            className="group relative overflow-hidden bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 hover:shadow-lg transition-all duration-200"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-green-500/10 to-emerald-600/10 opacity-0 group-hover:opacity-100 transition-opacity duration-200"></div>
            <div className="relative">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center mb-4">
                <KeyIcon className="w-6 h-6 text-white" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                {t.quickActions.manageApiKeys}
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                {t.quickActions.manageApiKeysDesc}
              </p>
            </div>
          </Link>

          <Link
            to="/demo"
            className="group relative overflow-hidden bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 hover:shadow-lg transition-all duration-200"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-purple-500/10 to-pink-600/10 opacity-0 group-hover:opacity-100 transition-opacity duration-200"></div>
            <div className="relative">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center mb-4">
                <PlayIcon className="w-6 h-6 text-white" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                {t.quickActions.tryDemo}
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                {t.quickActions.tryDemoDesc}
              </p>
            </div>
          </Link>
        </div>
      </div>

    </DashboardLayout>
  )
}
