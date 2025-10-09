import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { callsAPI } from '@/lib/api'
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import {
  PhoneIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  ArrowRightIcon,
} from '@heroicons/react/24/outline'

interface Call {
  id: number
  session_id: string
  status: string
  duration_minutes: number
  cost: number
  started_at: string
  summary: string | null
  sentiment: string | null
}

const statusConfig: Record<string, { label: string; color: string; icon: any }> = {
  completed: {
    label: 'Terminé',
    color: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    icon: CheckCircleIcon,
  },
  in_progress: {
    label: 'En cours',
    color: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
    icon: PhoneIcon,
  },
  failed: {
    label: 'Échoué',
    color: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
    icon: XCircleIcon,
  },
  interrupted: {
    label: 'Interrompu',
    color: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
    icon: ClockIcon,
  },
}

export default function CallsPage() {
  const [statusFilter, setStatusFilter] = useState<string>('all')
  
  const { data: calls, isLoading } = useQuery({
    queryKey: ['calls', statusFilter],
    queryFn: async () => {
      const params = statusFilter !== 'all' ? { status: statusFilter } : {}
      const response = await callsAPI.list(params)
      return response.data
    },
  })
  
  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
            Historique des Appels
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Consultez et analysez vos conversations
          </p>
        </div>
      </div>
      
      {/* Filters */}
      <div className="mb-6 flex items-center space-x-4">
        <select
          className="input"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="all">Tous les appels</option>
          <option value="completed">Terminés</option>
          <option value="in_progress">En cours</option>
          <option value="failed">Échoués</option>
          <option value="interrupted">Interrompus</option>
        </select>
      </div>
      
      {/* Calls List */}
      {isLoading ? (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto"></div>
        </div>
      ) : calls && calls.length > 0 ? (
        <div className="space-y-4">
          {calls.map((call: Call) => {
            const status = statusConfig[call.status] || statusConfig.completed
            const StatusIcon = status.icon
            
            return (
              <Link
                key={call.id}
                to={`/dashboard/calls/${call.id}`}
                className="card hover:shadow-lg transition-shadow block"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4 flex-1">
                    <div className={`p-3 rounded-lg ${status.color.split(' ')[0]}`}>
                      <StatusIcon className={`w-6 h-6 ${status.color.split(' ')[1]}`} />
                    </div>
                    
                    <div className="flex-1">
                      <div className="flex items-center space-x-3 mb-2">
                        <h3 className="font-semibold text-gray-900 dark:text-white">
                          Appel #{call.id}
                        </h3>
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${status.color}`}>
                          {status.label}
                        </span>
                        {call.sentiment && (
                          <span className="px-2 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
                            {call.sentiment}
                          </span>
                        )}
                      </div>
                      
                      <div className="flex items-center space-x-6 text-sm text-gray-600 dark:text-gray-400">
                        <div className="flex items-center">
                          <ClockIcon className="w-4 h-4 mr-1" />
                          {call.duration_minutes.toFixed(1)} min
                        </div>
                        <div>
                          {format(new Date(call.started_at), 'PPpp', { locale: fr })}
                        </div>
                        <div>
                          ${call.cost.toFixed(3)}
                        </div>
                      </div>
                      
                      {call.summary && (
                        <p className="mt-2 text-sm text-gray-600 dark:text-gray-400 line-clamp-2">
                          {call.summary}
                        </p>
                      )}
                    </div>
                  </div>
                  
                  <ArrowRightIcon className="w-5 h-5 text-gray-400" />
                </div>
              </Link>
            )
          })}
        </div>
      ) : (
        <div className="card text-center py-12">
          <PhoneIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400 mb-4">
            Aucun appel trouvé
          </p>
        </div>
      )}
    </div>
  )
}

