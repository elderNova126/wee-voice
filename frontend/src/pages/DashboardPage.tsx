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
      toast.error('Échec du chargement des statistiques')
    } finally {
      setLoading(false)
    }
  }

  return (
    <DashboardLayout>
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold bg-gradient-to-r from-gray-900 to-gray-600 dark:from-white dark:to-gray-300 bg-clip-text text-transparent mb-2">
          Tableau de Bord
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          Bienvenue ! Voici un aperçu de vos agents vocaux.
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4 mb-8">
        <StatCard
          title="Agents Totaux"
          value={stats.total_agents}
          icon={<MicrophoneIcon className="w-5 h-5" />}
          iconColor="from-blue-500 to-blue-600"
          subtitle="Agents vocaux actifs"
          loading={loading}
        />
        <StatCard
          title="Appels Totaux"
          value={stats.total_calls}
          icon={<PhoneIcon className="w-5 h-5" />}
          iconColor="from-green-500 to-green-600"
          subtitle="Appels effectués"
          loading={loading}
        />
        <StatCard
          title="Minutes Utilisées"
          value={stats.total_minutes.toFixed(1)}
          icon={<ClockIcon className="w-5 h-5" />}
          iconColor="from-purple-500 to-purple-600"
          subtitle="Temps d'appel total"
          loading={loading}
        />
        <StatCard
          title="Coût Total"
          value={`$${stats.total_cost.toFixed(2)}`}
          icon={<CurrencyDollarIcon className="w-5 h-5" />}
          iconColor="from-orange-500 to-orange-600"
          subtitle="Dépenses cumulées"
          loading={loading}
        />
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-6">
          Actions Rapides
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
                Créer un Agent
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Construisez un agent vocal personnalisé pour votre cas d'usage
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
                Gérer les Clés API
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Créez et gérez vos clés d'accès API pour l'intégration
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
                Essayer la Démo
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Testez l'agent de démonstration publique en direct
              </p>
            </div>
          </Link>
        </div>
      </div>

      {/* Getting Started Section */}
      <div className="mt-8 bg-gradient-to-r from-indigo-500 to-purple-600 rounded-xl shadow-lg p-8 text-white">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-2xl font-bold mb-2">Commencer avec VoiceAgent</h3>
            <p className="text-indigo-100 mb-4 max-w-2xl">
              Créez votre premier agent vocal en quelques minutes. Notre plateforme facilite la création d'agents intelligents avec une latence ultra-faible.
            </p>
            <div className="flex gap-4">
              <Link
                to="/dashboard/agents/new"
                className="px-6 py-2.5 bg-white text-indigo-600 rounded-lg font-medium hover:bg-indigo-50 transition-colors"
              >
                Créer un Agent
              </Link>
              <a
                href="https://docs.voiceagent.ai"
                target="_blank"
                rel="noopener noreferrer"
                className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium border-2 border-white/20 transition-colors"
              >
                Documentation
              </a>
            </div>
          </div>
          <div className="hidden lg:block">
            <MicrophoneIcon className="w-32 h-32 text-white/20" />
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
