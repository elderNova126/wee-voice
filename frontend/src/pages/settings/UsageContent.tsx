import { useState, useEffect } from 'react'
import { usageAPI } from '@/lib/api'
import { useTranslation } from '@/lib/translations'
import toast from 'react-hot-toast'
import { 
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer 
} from 'recharts'

interface UsageSummary {
  total_minutes: number
  total_cost: number
  total_calls: number
  average_call_duration: number
  current_month_minutes: number
  current_month_cost: number
}

interface UsageByMonth {
  month: string
  minutes: number
  cost: number
  calls: number
}

interface UsageByDay {
  date: string
  minutes: number
  cost: number
  calls: number
}

interface UsageByAgent {
  agent_id: number
  agent_name: string
  minutes: number
  cost: number
  calls: number
}

interface UsageAnalytics {
  summary: UsageSummary
  by_month: UsageByMonth[]
  by_day: UsageByDay[]
  by_agent: UsageByAgent[]
}

const COLORS = ['#6366f1', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#06b6d4']

export default function UsageContent() {
  const t = useTranslation()
  const [analytics, setAnalytics] = useState<UsageAnalytics | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeView, setActiveView] = useState<'day' | 'month'>('day')
  const [dateRange, setDateRange] = useState({ days: 30, months: 12 })

  useEffect(() => {
    loadUsageAnalytics()
  }, [])

  const loadUsageAnalytics = async () => {
    try {
      setLoading(true)
      const response = await usageAPI.getAnalytics()
      setAnalytics(response.data)
    } catch (error) {
      console.error('Error loading usage analytics:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleExport = async () => {
    try {
      const response = await usageAPI.exportData()
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `usage_export_${new Date().toISOString().split('T')[0]}.csv`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      toast.success(t.common.status === 'Statut' ? 'Données exportées avec succès' : 'Data exported successfully')
    } catch (error) {
      console.error('Error exporting data:', error)
      toast.error(t.common.status === 'Statut' ? 'Échec de l\'exportation des données' : 'Failed to export data')
    }
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount)
  }

  const formatMinutes = (minutes: number) => {
    const hours = Math.floor(minutes / 60)
    const mins = Math.floor(minutes % 60)
    if (hours > 0) {
      return `${hours}h ${mins}m`
    }
    return `${mins}m`
  }

  const summary = analytics?.summary || {
    total_minutes: 0,
    total_cost: 0,
    total_calls: 0,
    average_call_duration: 0,
    current_month_minutes: 0,
    current_month_cost: 0
  }
  const by_month = analytics?.by_month || []
  const by_day = analytics?.by_day || []
  const by_agent = analytics?.by_agent || []

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">{t.usage.title}</h2>
          <p className="mt-1 text-gray-600 dark:text-gray-400">{t.usage.subtitle}</p>
        </div>
        <button
          onClick={handleExport}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 flex items-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          {t.common.status === 'Statut' ? 'Exporter CSV' : 'Export CSV'}
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 dark:text-gray-400">{t.common.status === 'Statut' ? 'Dépenses totales' : 'Total Spend'}</p>
              {loading ? (
                <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-24 mt-1 animate-pulse"></div>
              ) : (
                <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
                  {formatCurrency(summary.total_cost)}
                </p>
              )}
            </div>
            <div className="bg-indigo-100 dark:bg-indigo-900/30 rounded-full p-3">
              <svg className="w-6 h-6 text-indigo-600 dark:text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
          {loading ? (
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-32 mt-2 animate-pulse"></div>
          ) : (
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
              {formatCurrency(summary.current_month_cost)} {t.common.status === 'Statut' ? 'ce mois' : 'this month'}
            </p>
          )}
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 dark:text-gray-400">{t.usage.minutes}</p>
              {loading ? (
                <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-20 mt-1 animate-pulse"></div>
              ) : (
                <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
                  {formatMinutes(summary.total_minutes)}
                </p>
              )}
            </div>
            <div className="bg-green-100 dark:bg-green-900/30 rounded-full p-3">
              <svg className="w-6 h-6 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
          {loading ? (
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-28 mt-2 animate-pulse"></div>
          ) : (
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
              {formatMinutes(summary.current_month_minutes)} {t.common.status === 'Statut' ? 'ce mois' : 'this month'}
            </p>
          )}
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 dark:text-gray-400">{t.dashboard.totalCalls}</p>
              {loading ? (
                <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-20 mt-1 animate-pulse"></div>
              ) : (
                <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
                  {summary.total_calls.toLocaleString()}
                </p>
              )}
            </div>
            <div className="bg-purple-100 dark:bg-purple-900/30 rounded-full p-3">
              <svg className="w-6 h-6 text-purple-600 dark:text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 dark:text-gray-400">{t.common.status === 'Statut' ? 'Durée moyenne d\'appel' : 'Avg Call Duration'}</p>
              {loading ? (
                <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-16 mt-1 animate-pulse"></div>
              ) : (
                <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
                  {formatMinutes(summary.average_call_duration)}
                </p>
              )}
            </div>
            <div className="bg-orange-100 dark:bg-orange-900/30 rounded-full p-3">
              <svg className="w-6 h-6 text-orange-600 dark:text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
          </div>
        </div>
      </div>

      {/* Time-based Charts */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-8">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">{t.common.status === 'Statut' ? 'Utilisation dans le temps' : 'Usage Over Time'}</h2>
          <div className="flex gap-2">
            <button
              onClick={() => setActiveView('day')}
              className={`px-4 py-2 rounded-lg ${
                activeView === 'day'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
              }`}
            >
              {t.common.status === 'Statut' ? 'Quotidien' : 'Daily'}
            </button>
            <button
              onClick={() => setActiveView('month')}
              className={`px-4 py-2 rounded-lg ${
                activeView === 'month'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
              }`}
            >
              {t.common.status === 'Statut' ? 'Mensuel' : 'Monthly'}
            </button>
          </div>
        </div>

        {loading ? (
          <div className="h-64 bg-gray-200 dark:bg-gray-700 rounded animate-pulse"></div>
        ) : activeView === 'day' ? (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={by_day.slice().reverse()}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="date" 
                tickFormatter={(date) => new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              />
              <YAxis yAxisId="left" />
              <YAxis yAxisId="right" orientation="right" />
              <Tooltip 
                labelFormatter={(date) => new Date(date).toLocaleDateString()}
                formatter={(value: any, name: string) => {
                  if (name === 'cost') return [formatCurrency(value), t.common.status === 'Statut' ? 'Coût' : 'Cost']
                  if (name === 'minutes') return [formatMinutes(value), t.usage.minutes]
                  return [value, name]
                }}
              />
              <Legend />
              <Bar yAxisId="left" dataKey="minutes" fill="#6366f1" name={t.usage.minutes} />
              <Bar yAxisId="right" dataKey="cost" fill="#10b981" name={t.common.status === 'Statut' ? 'Coût ($)' : 'Cost ($)'} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={by_month.slice().reverse()}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis yAxisId="left" />
              <YAxis yAxisId="right" orientation="right" />
              <Tooltip 
                formatter={(value: any, name: string) => {
                  if (name === 'cost') return [formatCurrency(value), t.common.status === 'Statut' ? 'Coût' : 'Cost']
                  if (name === 'minutes') return [formatMinutes(value), t.usage.minutes]
                  return [value, name]
                }}
              />
              <Legend />
              <Line yAxisId="left" type="monotone" dataKey="minutes" stroke="#6366f1" strokeWidth={2} name={t.usage.minutes} />
              <Line yAxisId="right" type="monotone" dataKey="cost" stroke="#10b981" strokeWidth={2} name={t.common.status === 'Statut' ? 'Coût ($)' : 'Cost ($)'} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Usage by Agent */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Pie Chart */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-6 text-gray-900 dark:text-white">{t.common.status === 'Statut' ? 'Utilisation par agent' : 'Usage by Agent'}</h2>
          {loading ? (
            <div className="h-64 bg-gray-200 dark:bg-gray-700 rounded animate-pulse"></div>
          ) : by_agent.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={by_agent}
                  dataKey="minutes"
                  nameKey="agent_name"
                  cx="50%"
                  cy="50%"
                  outerRadius={100}
                  label={(entry) => `${entry.agent_name}: ${formatMinutes(entry.minutes)}`}
                >
                  {by_agent.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip 
                  formatter={(value: any) => formatMinutes(value)}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-center text-gray-500 dark:text-gray-400 py-12">{t.common.status === 'Statut' ? 'Aucune donnée d\'agent disponible' : 'No agent data available'}</p>
          )}
        </div>

        {/* Agent Details Table */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-6 text-gray-900 dark:text-white">{t.common.status === 'Statut' ? 'Répartition par agent' : 'Agent Breakdown'}</h2>
          {loading ? (
            <div className="space-y-4">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="flex items-center justify-between p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
                  <div className="flex items-center gap-3 flex-1">
                    <div className="w-4 h-4 rounded-full bg-gray-200 dark:bg-gray-700 animate-pulse"></div>
                    <div>
                      <div className="h-5 bg-gray-200 dark:bg-gray-700 rounded w-32 mb-2 animate-pulse"></div>
                      <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-20 animate-pulse"></div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="h-5 bg-gray-200 dark:bg-gray-700 rounded w-20 mb-2 animate-pulse"></div>
                    <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-16 animate-pulse"></div>
                  </div>
                </div>
              ))}
            </div>
          ) : by_agent.length > 0 ? (
            <div className="space-y-4">
              {by_agent.map((agent, index) => (
                <div key={agent.agent_id} className="flex items-center justify-between p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
                  <div className="flex items-center gap-3">
                    <div 
                      className="w-4 h-4 rounded-full" 
                      style={{ backgroundColor: COLORS[index % COLORS.length] }}
                    ></div>
                    <div>
                      <p className="font-medium text-gray-900 dark:text-white">{agent.agent_name}</p>
                      <p className="text-sm text-gray-500 dark:text-gray-400">{agent.calls} {t.common.status === 'Statut' ? 'appels' : 'calls'}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold text-gray-900 dark:text-white">{formatCurrency(agent.cost)}</p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">{formatMinutes(agent.minutes)}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-gray-500 dark:text-gray-400 py-12">{t.common.status === 'Statut' ? 'Aucune donnée d\'agent disponible' : 'No agent data available'}</p>
          )}
        </div>
      </div>
    </div>
  )
}

