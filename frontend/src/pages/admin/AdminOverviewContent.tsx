import { useEffect, useState } from 'react'
import { adminAPI } from '@/lib/api'
import toast from 'react-hot-toast'
import { useTranslation } from '@/lib/translations'
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

export default function AdminOverviewContent() {
  const t = useTranslation()
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
      toast.error(error.response?.data?.detail || (t.common.status === 'Statut' ? 'Impossible de charger le tableau de bord admin' : 'Failed to load admin overview'))
    } finally {
      setLoading(false)
    }
  }

  const formatDate = (value: string) => {
    const date = new Date(value)
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div className="space-y-6">
      {/* Totals */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          title={t.admin.totalUsers}
          value={data ? data.totals.total_users : '--'}
          subtitle={`${data?.totals.active_users ?? '--'} ${t.admin.activeUsers} • ${data?.totals.pending_users ?? '--'} ${t.admin.pendingUsers}`}
          icon={<UsersIcon className="w-5 h-5" />}
          loading={loading}
        />
        <StatCard
          title={t.admin.totalAgents}
          value={data ? data.totals.total_agents : '--'}
          subtitle={`${data?.totals.active_agents ?? '--'} ${t.admin.activeAgents} • ${data?.totals.public_agents ?? '--'} ${t.admin.publicAgents}`}
          icon={<MicrophoneIcon className="w-5 h-5" />}
          iconColor="from-purple-500 to-pink-500"
          loading={loading}
        />
        <StatCard
          title={t.admin.totalCalls}
          value={data ? data.usage.calls_last_30_days : '--'}
          subtitle={`${data?.usage.calls_last_24_hours ?? '--'} ${t.common.status === 'Statut' ? 'sur les 24 dernières heures' : 'in the last 24 hours'}`}
          icon={<PhoneIcon className="w-5 h-5" />}
          iconColor="from-indigo-500 to-cyan-500"
          loading={loading}
        />
        <StatCard
          title={t.admin.openTickets}
          value={data ? data.totals.open_tickets : '--'}
          subtitle={`${data?.totals.total_calls ?? '--'} ${t.common.status === 'Statut' ? 'appels au total' : 'total calls'}`}
          icon={<TicketIcon className="w-5 h-5" />}
          iconColor="from-amber-500 to-orange-500"
          loading={loading}
        />
      </div>

      {/* Usage & Revenue */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader
            title={t.admin.usage}
            subtitle={t.common.status === 'Statut' ? 'Minutes et appels consommés sur la plateforme' : 'Minutes and calls consumed on the platform'}
            icon={<MicrophoneIcon className="w-6 h-6" />}
          />
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">{t.common.status === 'Statut' ? 'Minutes totales' : 'Total Minutes'}</p>
                <p className="text-2xl font-semibold text-gray-900 dark:text-white">
                  {data ? data.usage.minutes_total.toFixed(1) : '--'} {t.common.status === 'Statut' ? 'min' : 'min'}
                </p>
              </div>
              <Badge variant="info" size="sm">
                + {data ? data.usage.minutes_last_30_days.toFixed(1) : '--'} {t.common.status === 'Statut' ? 'min (30j)' : 'min (30d)'}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">{t.common.status === 'Statut' ? 'Appels 30 derniers jours' : 'Calls last 30 days'}</p>
                <p className="text-lg font-medium text-gray-900 dark:text-white">
                  {data ? data.usage.calls_last_30_days : '--'}
                </p>
              </div>
              <Badge variant="default" size="sm">
                {data ? data.usage.calls_last_24_hours : '--'} {t.common.status === 'Statut' ? 'sur 24h' : 'in 24h'}
              </Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader
            title={t.admin.revenue}
            subtitle={t.common.status === 'Statut' ? 'Transactions réussies estimées' : 'Estimated successful transactions'}
            icon={<CurrencyDollarIcon className="w-6 h-6" />}
          />
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">{t.common.status === 'Statut' ? 'Revenus cumulés' : 'Total Revenue'}</p>
                <p className="text-2xl font-semibold text-gray-900 dark:text-white">
                  ${data ? data.financial.revenue_total.toFixed(2) : '--'}
                </p>
              </div>
              <Badge variant="success" size="sm">
                ${data ? data.financial.revenue_last_30_days.toFixed(2) : '--'} / {t.common.status === 'Statut' ? '30j' : '30d'}
              </Badge>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent activity */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Card>
          <CardHeader
            title={t.admin.recentUsers}
            subtitle={t.common.status === 'Statut' ? '5 dernières inscriptions' : '5 latest registrations'}
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
              <p className="text-sm text-gray-500 dark:text-gray-400">{t.common.status === 'Statut' ? 'Aucune inscription récente.' : 'No recent registrations.'}</p>
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
                  {user.is_approved ? t.admin.approved : t.admin.pending}
                </Badge>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader
            title={t.admin.recentAgents}
            subtitle={t.common.status === 'Statut' ? '5 derniers agents créés' : '5 latest agents created'}
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
              <p className="text-sm text-gray-500 dark:text-gray-400">{t.common.status === 'Statut' ? 'Aucun agent créé récemment.' : 'No agents created recently.'}</p>
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
                    {agent.is_active ? t.admin.active : t.admin.inactive}
                  </Badge>
                  <Badge variant={agent.is_public ? 'purple' : 'default'} size="sm">
                    {agent.is_public ? t.admin.public : t.admin.private}
                  </Badge>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader
            title={t.admin.recentTickets}
            subtitle={t.common.status === 'Statut' ? '5 derniers tickets support' : '5 latest support tickets'}
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
              <p className="text-sm text-gray-500 dark:text-gray-400">{t.common.status === 'Statut' ? 'Aucun ticket pour le moment.' : 'No tickets at the moment.'}</p>
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
  )
}

