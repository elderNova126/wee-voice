import { useEffect, useState } from 'react'
import { adminAPI } from '@/lib/api'
import toast from 'react-hot-toast'
import { useTranslation } from '@/lib/translations'
import {
  CheckCircleIcon,
  XCircleIcon,
  UserCircleIcon,
  MagnifyingGlassIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Card } from '@/components/ui/Card'
import { StatCard } from '@/components/ui/StatCard'

interface User {
  id: number
  email: string
  full_name: string
  is_active: boolean
  is_superuser: boolean
  is_approved: boolean
  subscription_tier: string
  total_minutes_used: number
  monthly_minutes_used: number
  credit_balance: number
  created_at: string
}

interface UserStats {
  total_users: number
  approved_users: number
  pending_users: number
  active_users: number
  admin_users: number
  inactive_users: number
}

export default function AdminUsersContent() {
  const t = useTranslation()
  const [users, setUsers] = useState<User[]>([])
  const [stats, setStats] = useState<UserStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filterApproved, setFilterApproved] = useState<boolean | null>(null)
  const [filterActive, setFilterActive] = useState<boolean | null>(null)

  useEffect(() => {
    loadData()
  }, [search, filterApproved, filterActive])

  const loadData = async () => {
    try {
      setLoading(true)
      const [usersRes, statsRes] = await Promise.all([
        adminAPI.listUsers({
          search: search || undefined,
          is_approved: filterApproved ?? undefined,
          is_active: filterActive ?? undefined,
          sort_by: 'created_at',
          order: 'desc',
        }),
        adminAPI.getUserStats(),
      ])
      setUsers(usersRes.data)
      setStats(statsRes.data)
    } catch (error: any) {
      console.error('Failed to load data:', error)
      toast.error(error.response?.data?.detail || (t.common.status === 'Statut' ? 'Échec du chargement des utilisateurs' : 'Failed to load users'))
    } finally {
      setLoading(false)
    }
  }

  const handleApprove = async (userId: number) => {
    try {
      await adminAPI.approveUser(userId)
      toast.success(t.admin.approveSuccess)
      loadData()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || (t.common.status === 'Statut' ? 'Échec de l\'approbation de l\'utilisateur' : 'Failed to approve user'))
    }
  }

  const handleReject = async (userId: number) => {
    try {
      await adminAPI.rejectUser(userId)
      toast.success(t.admin.rejectSuccess)
      loadData()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || (t.common.status === 'Statut' ? 'Échec du rejet de l\'utilisateur' : 'Failed to reject user'))
    }
  }

  const handleActivate = async (userId: number) => {
    try {
      await adminAPI.activateUser(userId)
      toast.success(t.admin.activateSuccess)
      loadData()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || (t.common.status === 'Statut' ? 'Échec de l\'activation de l\'utilisateur' : 'Failed to activate user'))
    }
  }

  const handleDeactivate = async (userId: number) => {
    try {
      await adminAPI.deactivateUser(userId)
      toast.success(t.admin.deactivateSuccess)
      loadData()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || (t.common.status === 'Statut' ? 'Échec de la désactivation de l\'utilisateur' : 'Failed to deactivate user'))
    }
  }

  const clearFilters = () => {
    setSearch('')
    setFilterApproved(null)
    setFilterActive(null)
  }

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <StatCard
            title={t.common.status === 'Statut' ? 'Total Utilisateurs' : 'Total Users'}
            value={stats.total_users}
            icon={<UserCircleIcon className="w-5 h-5" />}
          />
          <StatCard
            title={t.common.status === 'Statut' ? 'En attente d\'approbation' : 'Pending Approval'}
            value={stats.pending_users}
            icon={<UserCircleIcon className="w-5 h-5" />}
            iconColor="from-yellow-500 to-yellow-600"
          />
          <StatCard
            title={t.common.status === 'Statut' ? 'Utilisateurs approuvés' : 'Approved Users'}
            value={stats.approved_users}
            icon={<CheckCircleIcon className="w-5 h-5" />}
            iconColor="from-green-500 to-green-600"
          />
          <StatCard
            title={t.common.status === 'Statut' ? 'Utilisateurs actifs' : 'Active Users'}
            value={stats.active_users}
            icon={<CheckCircleIcon className="w-5 h-5" />}
            iconColor="from-blue-500 to-blue-600"
          />
          <StatCard
            title={t.common.status === 'Statut' ? 'Utilisateurs Admin' : 'Admin Users'}
            value={stats.admin_users}
            icon={<UserCircleIcon className="w-5 h-5" />}
            iconColor="from-purple-500 to-purple-600"
          />
        </div>
      )}

      {/* Filters */}
      <Card>
        <div className="p-4 space-y-4">
          <div className="flex flex-col sm:flex-row gap-4">
            {/* Search */}
            <div className="flex-1">
              <Input
                type="text"
                placeholder={t.common.status === 'Statut' ? 'Rechercher par email ou nom...' : 'Search by email or name...'}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                icon={<MagnifyingGlassIcon className="w-5 h-5" />}
              />
            </div>

            {/* Approval Filter */}
            <select
              value={filterApproved === null ? '' : filterApproved.toString()}
              onChange={(e) =>
                setFilterApproved(
                  e.target.value === ''
                    ? null
                    : e.target.value === 'true'
                )
              }
              className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            >
              <option value="">{t.common.status === 'Statut' ? 'Tous les statuts d\'approbation' : 'All Approval Status'}</option>
              <option value="true">{t.admin.approved}</option>
              <option value="false">{t.admin.pending}</option>
            </select>

            {/* Active Filter */}
            <select
              value={filterActive === null ? '' : filterActive.toString()}
              onChange={(e) =>
                setFilterActive(
                  e.target.value === '' ? null : e.target.value === 'true'
                )
              }
              className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            >
              <option value="">{t.common.status === 'Statut' ? 'Tous les statuts' : 'All Status'}</option>
              <option value="true">{t.admin.active}</option>
              <option value="false">{t.admin.inactive}</option>
            </select>

            {/* Clear Filters */}
            {(search || filterApproved !== null || filterActive !== null) && (
              <Button
                variant="outline"
                onClick={clearFilters}
                icon={<ArrowPathIcon className="w-4 h-4" />}
              >
                {t.common.status === 'Statut' ? 'Effacer' : 'Clear'}
              </Button>
            )}
          </div>
        </div>
      </Card>

      {/* Users Table */}
      <Card>
        {loading ? (
          <div className="p-8 text-center">
            <ArrowPathIcon className="h-8 w-8 animate-spin mx-auto text-gray-400" />
            <p className="mt-2 text-gray-600 dark:text-gray-400">
              {t.common.status === 'Statut' ? 'Chargement des utilisateurs...' : 'Loading users...'}
            </p>
          </div>
        ) : users.length === 0 ? (
          <div className="p-8 text-center">
            <UserCircleIcon className="h-12 w-12 mx-auto text-gray-400" />
            <p className="mt-2 text-gray-600 dark:text-gray-400">
              {t.common.status === 'Statut' ? 'Aucun utilisateur trouvé' : 'No users found'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
              <thead className="bg-gray-50 dark:bg-gray-800">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    {t.common.status === 'Statut' ? 'Utilisateur' : 'User'}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    {t.common.status}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    {t.common.status === 'Statut' ? 'Abonnement' : 'Subscription'}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    {t.common.status === 'Statut' ? 'Utilisation' : 'Usage'}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    {t.common.status === 'Statut' ? 'Créé' : 'Created'}
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    {t.common.actions}
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                {users.map((user) => (
                  <tr
                    key={user.id}
                    className="hover:bg-gray-50 dark:hover:bg-gray-700/50"
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <div className="flex-shrink-0 h-10 w-10">
                          <div className="h-10 w-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-semibold">
                            {user.full_name.charAt(0).toUpperCase()}
                          </div>
                        </div>
                        <div className="ml-4">
                          <div className="text-sm font-medium text-gray-900 dark:text-white">
                            {user.full_name}
                          </div>
                          <div className="text-sm text-gray-500 dark:text-gray-400">
                            {user.email}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex flex-col gap-1">
                        <Badge
                          variant={
                            user.is_approved ? 'success' : 'warning'
                          }
                        >
                          {user.is_approved ? t.admin.approved : t.admin.pending}
                        </Badge>
                        <Badge
                          variant={user.is_active ? 'success' : 'danger'}
                        >
                          {user.is_active ? t.admin.active : t.admin.inactive}
                        </Badge>
                        {user.is_superuser && (
                          <Badge variant="info">{t.common.status === 'Statut' ? 'Admin' : 'Admin'}</Badge>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <Badge variant="default">
                        {user.subscription_tier}
                      </Badge>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                      <div>
                        {user.total_minutes_used.toFixed(1)} {t.common.status === 'Statut' ? 'min au total' : 'min total'}
                      </div>
                      <div className="text-xs">
                        {user.monthly_minutes_used.toFixed(1)} {t.common.status === 'Statut' ? 'min ce mois' : 'min this month'}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                      {new Date(user.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex justify-end gap-2">
                        {!user.is_approved && (
                          <Button
                            size="sm"
                            variant="primary"
                            onClick={() => handleApprove(user.id)}
                            icon={<CheckCircleIcon className="w-4 h-4" />}
                            className="bg-green-600 hover:bg-green-700 focus:ring-green-500"
                          >
                            {t.admin.approve}
                          </Button>
                        )}
                        {user.is_approved && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleReject(user.id)}
                            icon={<XCircleIcon className="w-4 h-4" />}
                          >
                            {t.admin.reject}
                          </Button>
                        )}
                        {!user.is_active && (
                          <Button
                            size="sm"
                            variant="primary"
                            onClick={() => handleActivate(user.id)}
                            className="bg-green-600 hover:bg-green-700 focus:ring-green-500"
                          >
                            {t.admin.activate}
                          </Button>
                        )}
                        {user.is_active && (
                          <Button
                            size="sm"
                            variant="danger"
                            onClick={() => handleDeactivate(user.id)}
                          >
                            {t.admin.deactivate}
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}

