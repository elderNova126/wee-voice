import { useEffect, useState } from 'react'
import DashboardLayout from '@/layouts/DashboardLayout'
import { adminAPI } from '@/lib/api'
import toast from 'react-hot-toast'
import {
  UsersIcon,
  MicrophoneIcon,
  PhoneIcon,
  CurrencyDollarIcon,
  TicketIcon,
  ClipboardDocumentListIcon,
} from '@heroicons/react/24/outline'
import { StatCard } from '@/components/ui/StatCard'
import { Card, CardContent, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'

interface OverviewTotals {
  total_users: number
  active_users: number
  pending_users: number
  total_agents: number
  active_agents: number
  public_agents: number
  total_calls: number
  open_tickets: number
}

interface OverviewUsageMetrics {
  minutes_total: number
  minutes_last_30_days: number
  calls_last_30_days: number
  calls_last_24_hours: number
}

interface OverviewFinancialMetrics {
  revenue_total: number
  revenue_last_30_days: number
}

interface RecentUser {
  id: number
  full_name: string
  email: string
  created_at: string
  is_approved: boolean
}

interface RecentAgent {
  id: number
  name: string
  owner_name: string
  owner_email: string
  is_public: boolean
  is_active: boolean
  created_at: string
}

interface RecentTicket {
  id: number
  ticket_number: string
  subject: string
  status: string
  priority: string
  created_at: string
}

interface AdminOverviewData {
  totals: OverviewTotals
  usage: OverviewUsageMetrics
  financial: OverviewFinancialMetrics
  recent: {
    users: RecentUser[]
    agents: RecentAgent[]
    tickets: RecentTicket[]
  }
}

export default function AdminOverviewPage() {
  const [data, setData] = useState<AdminOverviewData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadOverview()
  }, [])

  const loadOverview = async () => {
    try {
      setLoading(true)
      const response = await adminAPI.getOverview()
      setData(response.data)
    } catch (error: any) {
      console.error('Failed to load admin overview', error)
      toast.error(error.response?.data?.detail || 'Impossible de charger le tableau de bord admin')
    } finally {
      setLoading(false)
    }
  }

  const formatDate = (value: string) => {
    const date = new Date(value)
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
              Admin Overview
            </h1>
            <p className="mt-2 text-gray-600 dark:text-gray-400">
              Vue d&apos;ensemble de la plateforme : utilisateurs, agents, appels et support.
            </p>
          </div>
        </div>

        {/* Totals */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          <StatCard
            title="Utilisateurs"
            value={data ? data.totals.total_users : '--'}
            subtitle={`${data?.totals.active_users ?? '--'} actifs • ${data?.totals.pending_users ?? '--'} en attente`}
            icon={<UsersIcon className="w-5 h-5" />}
            loading={loading}
          />
          <StatCard
            title="Agents"
            value={data ? data.totals.total_agents : '--'}
            subtitle={`${data?.totals.active_agents ?? '--'} actifs • ${data?.totals.public_agents ?? '--'} publics`}
            icon={<MicrophoneIcon className="w-5 h-5" />}
            iconColor="from-purple-500 to-pink-500"
            loading={loading}
          />
          <StatCard
            title="Appels (30j)"
            value={data ? data.usage.calls_last_30_days : '--'}
            subtitle={`${data?.usage.calls_last_24_hours ?? '--'} sur les 24 dernières heures`}
            icon={<PhoneIcon className="w-5 h-5" />}
            iconColor="from-indigo-500 to-cyan-500"
            loading={loading}
          />
          <StatCard
            title="Tickets ouverts"
            value={data ? data.totals.open_tickets : '--'}
            subtitle={`${data?.totals.total_calls ?? '--'} appels au total`}
            icon={<TicketIcon className="w-5 h-5" />}
            iconColor="from-amber-500 to-orange-500"
            loading={loading}
          />
        </div>

        {/* Usage & Revenue */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card>
            <CardHeader
              title="Utilisation"
              subtitle="Minutes et appels consommés sur la plateforme"
              icon={<MicrophoneIcon className="w-6 h-6" />}
            />
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Minutes totales</p>
                  <p className="text-2xl font-semibold text-gray-900 dark:text-white">
                    {data ? data.usage.minutes_total.toFixed(1) : '--'} min
                  </p>
                </div>
                <Badge variant="info" size="sm">
                  + {data ? data.usage.minutes_last_30_days.toFixed(1) : '--'} min (30j)
                </Badge>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Appels 30 derniers jours</p>
                  <p className="text-lg font-medium text-gray-900 dark:text-white">
                    {data ? data.usage.calls_last_30_days : '--'}
                  </p>
                </div>
                <Badge variant="default" size="sm">
                  {data ? data.usage.calls_last_24_hours : '--'} sur 24h
                </Badge>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader
              title="Revenus"
              subtitle="Transactions réussies estimées"
              icon={<CurrencyDollarIcon className="w-6 h-6" />}
            />
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Revenus cumulés</p>
                  <p className="text-2xl font-semibold text-gray-900 dark:text-white">
                    ${data ? data.financial.revenue_total.toFixed(2) : '--'}
                  </p>
                </div>
                <Badge variant="success" size="sm">
                  ${data ? data.financial.revenue_last_30_days.toFixed(2) : '--'} / 30j
                </Badge>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Recent activity */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <Card>
            <CardHeader
              title="Nouveaux utilisateurs"
              subtitle="5 dernières inscriptions"
              icon={<UsersIcon className="w-6 h-6" />}
            />
            <CardContent className="space-y-4">
              {loading && (
                <div className="space-y-3">
                  {Array.from({ length: 5 }).map((_, index) => (
                    <div key={`user-skeleton-${index}`} className="animate-pulse space-y-2">
                      <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4"></div>
                      <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
                    </div>
                  ))}
                </div>
              )}
              {!loading && data && data.recent.users.length === 0 && (
                <p className="text-sm text-gray-500 dark:text-gray-400">Aucune inscription récente.</p>
              )}
              {!loading && data && data.recent.users.map((user) => (
                <div key={user.id} className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">
                      {user.full_name}
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {user.email}
                    </p>
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                      {formatDate(user.created_at)}
                    </p>
                  </div>
                  <Badge variant={user.is_approved ? 'success' : 'warning'} size="sm">
                    {user.is_approved ? 'Approuvé' : 'En attente'}
                  </Badge>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader
              title="Agents récents"
              subtitle="5 derniers agents créés"
              icon={<MicrophoneIcon className="w-6 h-6" />}
            />
            <CardContent className="space-y-4">
              {loading && (
                <div className="space-y-3">
                  {Array.from({ length: 5 }).map((_, index) => (
                    <div key={`agent-skeleton-${index}`} className="animate-pulse space-y-2">
                      <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-2/3"></div>
                      <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-1/3"></div>
                    </div>
                  ))}
                </div>
              )}
              {!loading && data && data.recent.agents.length === 0 && (
                <p className="text-sm text-gray-500 dark:text-gray-400">Aucun agent créé récemment.</p>
              )}
              {!loading && data && data.recent.agents.map((agent) => (
                <div key={agent.id} className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">
                      {agent.name}
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {agent.owner_name} • {agent.owner_email}
                    </p>
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                      {formatDate(agent.created_at)}
                    </p>
                  </div>
                  <div className="flex flex-col gap-1 items-end">
                    <Badge variant={agent.is_active ? 'success' : 'danger'} size="sm">
                      {agent.is_active ? 'Actif' : 'Inactif'}
                    </Badge>
                    <Badge variant={agent.is_public ? 'purple' : 'default'} size="sm">
                      {agent.is_public ? 'Public' : 'Privé'}
                    </Badge>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader
              title="Tickets récents"
              subtitle="5 derniers tickets support"
              icon={<ClipboardDocumentListIcon className="w-6 h-6" />}
            />
            <CardContent className="space-y-4">
              {loading && (
                <div className="space-y-3">
                  {Array.from({ length: 5 }).map((_, index) => (
                    <div key={`ticket-skeleton-${index}`} className="animate-pulse space-y-2">
                      <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-4/5"></div>
                      <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-2/5"></div>
                    </div>
                  ))}
                </div>
              )}
              {!loading && data && data.recent.tickets.length === 0 && (
                <p className="text-sm text-gray-500 dark:text-gray-400">Aucun ticket pour le moment.</p>
              )}
              {!loading && data && data.recent.tickets.map((ticket) => (
                <div key={ticket.id} className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">
                      {ticket.subject}
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      #{ticket.ticket_number}
                    </p>
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                      {formatDate(ticket.created_at)}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <Badge
                      variant={
                        ticket.status === 'open' ? 'warning'
                        : ticket.status === 'in_progress' ? 'info'
                        : ticket.status === 'resolved' ? 'success'
                        : 'default'
                      }
                      size="sm"
                    >
                      {ticket.status.replace('_', ' ')}
                    </Badge>
                    <Badge
                      variant={
                        ticket.priority === 'urgent' ? 'danger'
                        : ticket.priority === 'high' ? 'warning'
                        : ticket.priority === 'medium' ? 'info'
                        : 'default'
                      }
                      size="sm"
                    >
                      {ticket.priority}
                    </Badge>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </DashboardLayout>
  )
}

