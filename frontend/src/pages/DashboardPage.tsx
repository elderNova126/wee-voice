import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { 
  MicrophoneIcon, 
  PhoneIcon, 
  ClockIcon,
  CurrencyDollarIcon 
} from '@heroicons/react/24/outline'
import DashboardLayout from '@/layouts/DashboardLayout'
import { agentsAPI, callsAPI } from '@/lib/api'
import toast from 'react-hot-toast'

interface Stats {
  total_agents: number
  total_calls: number
  total_minutes: number
  total_cost: number
}

export default function DashboardPage() {
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
      const [agentsResponse, callsResponse] = await Promise.all([
        agentsAPI.list(),
        callsAPI.list()
      ])

      const agents = agentsResponse.data
      const calls = callsResponse.data

      const totalMinutes = calls.reduce((sum: number, call: any) => sum + (call.duration_minutes || 0), 0)
      const totalCost = calls.reduce((sum: number, call: any) => sum + (call.cost || 0), 0)

      setStats({
        total_agents: agents.length,
        total_calls: calls.length,
        total_minutes: totalMinutes,
        total_cost: totalCost
      })
    } catch (error) {
      console.error('Failed to load stats:', error)
      toast.error('Failed to load dashboard statistics')
    } finally {
      setLoading(false)
    }
  }

  const statCards = [
    {
      name: 'Total Agents',
      value: stats.total_agents,
      icon: MicrophoneIcon,
      color: 'bg-blue-500',
      link: '/dashboard/agents'
    },
    {
      name: 'Total Calls',
      value: stats.total_calls,
      icon: PhoneIcon,
      color: 'bg-green-500',
      link: '/dashboard/calls'
    },
    {
      name: 'Minutes Used',
      value: stats.total_minutes.toFixed(1),
      icon: ClockIcon,
      color: 'bg-purple-500',
      link: '/dashboard/calls'
    },
    {
      name: 'Total Cost',
      value: `$${stats.total_cost.toFixed(2)}`,
      icon: CurrencyDollarIcon,
      color: 'bg-orange-500',
      link: '/dashboard/calls'
    }
  ]

  return (
    <DashboardLayout>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Dashboard</h1>
        <p className="mt-2 text-gray-600 dark:text-gray-400">
          Welcome back! Here's an overview of your voice agents.
        </p>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="card animate-pulse">
              <div className="h-20 bg-gray-200 dark:bg-gray-700 rounded"></div>
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {statCards.map((stat) => (
            <Link
              key={stat.name}
              to={stat.link}
              className="card hover:shadow-lg transition-shadow"
            >
              <div className="flex items-center">
                <div className={`p-3 rounded-lg ${stat.color}`}>
                  <stat.icon className="h-6 w-6 text-white" />
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
                    {stat.name}
                  </p>
                  <p className="text-2xl font-semibold text-gray-900 dark:text-white">
                    {stat.value}
                  </p>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* Quick Actions */}
      <div className="mt-8">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
          Quick Actions
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Link
            to="/dashboard/agents/new"
            className="card hover:bg-primary-50 dark:hover:bg-primary-900 transition-colors text-center p-6"
          >
            <MicrophoneIcon className="h-12 w-12 text-primary-600 mx-auto mb-2" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-white">
              Create New Agent
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Build a custom voice agent
            </p>
          </Link>

          <Link
            to="/dashboard/api-keys"
            className="card hover:bg-green-50 dark:hover:bg-green-900 transition-colors text-center p-6"
          >
            <svg className="h-12 w-12 text-green-600 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
            </svg>
            <h3 className="text-lg font-medium text-gray-900 dark:text-white">
              Manage API Keys
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Create and manage access keys
            </p>
          </Link>

          <Link
            to="/demo"
            className="card hover:bg-purple-50 dark:hover:bg-purple-900 transition-colors text-center p-6"
          >
            <svg className="h-12 w-12 text-purple-600 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h3 className="text-lg font-medium text-gray-900 dark:text-white">
              Try Demo
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Test the public demo agent
            </p>
          </Link>
        </div>
      </div>
    </DashboardLayout>
  )
}
