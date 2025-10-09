import { useQuery } from '@tanstack/react-query'
import { callsAPI } from '@/lib/api'
import { useAuthStore } from '@/store/authStore'
import {
  PhoneIcon,
  ClockIcon,
  CurrencyDollarIcon,
  ChartBarIcon,
} from '@heroicons/react/24/outline'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

export default function DashboardPage() {
  const { user } = useAuthStore()
  
  const { data: stats, isLoading } = useQuery({
    queryKey: ['call-stats'],
    queryFn: async () => {
      const response = await callsAPI.getStats(30)
      return response.data
    },
  })
  
  const statCards = [
    {
      name: 'Total des Appels',
      value: stats?.total_calls || 0,
      icon: PhoneIcon,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50 dark:bg-blue-900',
    },
    {
      name: 'Minutes Utilisées',
      value: `${stats?.total_minutes || 0} min`,
      icon: ClockIcon,
      color: 'text-green-600',
      bgColor: 'bg-green-50 dark:bg-green-900',
    },
    {
      name: 'Coût Total',
      value: `$${stats?.total_cost || 0}`,
      icon: CurrencyDollarIcon,
      color: 'text-purple-600',
      bgColor: 'bg-purple-50 dark:bg-purple-900',
    },
    {
      name: 'Taux de Réussite',
      value: stats?.status_breakdown?.completed 
        ? `${Math.round((stats.status_breakdown.completed / stats.total_calls) * 100)}%`
        : '0%',
      icon: ChartBarIcon,
      color: 'text-orange-600',
      bgColor: 'bg-orange-50 dark:bg-orange-900',
    },
  ]
  
  // Prepare chart data
  const chartData = stats?.status_breakdown
    ? Object.entries(stats.status_breakdown).map(([status, count]) => ({
        name: status,
        value: count,
      }))
    : []
  
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
          Tableau de bord
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          Bienvenue, {user?.full_name}
        </p>
      </div>
      
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {statCards.map((stat) => (
          <div key={stat.name} className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">
                  {stat.name}
                </p>
                <p className="text-3xl font-bold text-gray-900 dark:text-white">
                  {isLoading ? '...' : stat.value}
                </p>
              </div>
              <div className={`p-3 rounded-lg ${stat.bgColor}`}>
                <stat.icon className={`w-8 h-8 ${stat.color}`} />
              </div>
            </div>
          </div>
        ))}
      </div>
      
      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Répartition par Statut
          </h3>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="value" fill="#0ea5e9" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-300 flex items-center justify-center text-gray-500 dark:text-gray-400">
              Aucune donnée disponible
            </div>
          )}
        </div>
        
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Utilisation de l'Abonnement
          </h3>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-gray-600 dark:text-gray-400">Minutes utilisées</span>
                <span className="text-gray-900 dark:text-white font-medium">
                  {stats?.total_minutes || 0} / 1000 min
                </span>
              </div>
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                <div
                  className="bg-primary-600 h-2 rounded-full"
                  style={{ width: `${Math.min(((stats?.total_minutes || 0) / 1000) * 100, 100)}%` }}
                ></div>
              </div>
            </div>
            
            <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                Abonnement actuel
              </p>
              <p className="text-xl font-semibold text-gray-900 dark:text-white capitalize">
                {user?.subscription_tier}
              </p>
            </div>
          </div>
        </div>
      </div>
      
      {/* Quick Actions */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Actions Rapides
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <a
            href="/dashboard/agents"
            className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg hover:border-primary-500 transition-colors"
          >
            <h4 className="font-medium text-gray-900 dark:text-white mb-1">
              Créer un Agent
            </h4>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Configurez un nouvel agent vocal
            </p>
          </a>
          
          <a
            href="/dashboard/calls"
            className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg hover:border-primary-500 transition-colors"
          >
            <h4 className="font-medium text-gray-900 dark:text-white mb-1">
              Voir les Appels
            </h4>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Consultez l'historique des appels
            </p>
          </a>
          
          <a
            href="/dashboard/api-keys"
            className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg hover:border-primary-500 transition-colors"
          >
            <h4 className="font-medium text-gray-900 dark:text-white mb-1">
              Gérer les API Keys
            </h4>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Créez et gérez vos clés API
            </p>
          </a>
        </div>
      </div>
    </div>
  )
}

