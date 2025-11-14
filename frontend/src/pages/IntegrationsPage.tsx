import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  PlusIcon,
  PencilIcon,
  TrashIcon,
  CheckCircleIcon,
  XCircleIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline'
import DashboardLayout from '@/layouts/DashboardLayout'
import { integrationsAPI } from '@/lib/api'
import toast from 'react-hot-toast'
import { useTranslation } from '@/lib/translations'

interface Integration {
  id: number
  name: string
  description: string | null
  integration_type: string
  provider: string
  status: string
  is_active: boolean
  last_sync_at: string | null
  last_error: string | null
  created_at: string
}

const getIntegrationTypeLabel = (type: string, t: any): string => {
  const labels: Record<string, string> = {
    calendar: t?.integrations?.typeCalendar || '📅 Calendar',
    email: t?.integrations?.typeEmail || '📧 Email',
    contact_management: t?.integrations?.typeContactManagement || '👥 Contacts',
    database: t?.integrations?.typeDatabase || '💾 Database',
    crm: t?.integrations?.typeCRM || '📊 CRM',
    accounting: t?.integrations?.typeAccounting || '💰 Accounting',
    other: t?.integrations?.typeOther || '🔧 Other',
  }
  return labels[type] || type
}

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
  inactive: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  error: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
  pending_auth: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300',
}

export default function IntegrationsPage() {
  const t = useTranslation()
  const [integrations, setIntegrations] = useState<Integration[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<{
    type?: string
    status?: string
  }>({})
  const [testingIds, setTestingIds] = useState<Set<number>>(new Set())
  const [syncingIds, setSyncingIds] = useState<Set<number>>(new Set())

  useEffect(() => {
    loadIntegrations()
  }, [filter])

  const loadIntegrations = async () => {
    try {
      const params: any = {}
      if (filter.type) params.integration_type = filter.type
      if (filter.status) params.status = filter.status
      
      const response = await integrationsAPI.list(params)
      setIntegrations(response.data)
    } catch (error: any) {
      console.error('Failed to load integrations:', error)
      toast.error(error.response?.data?.detail || t.integrations.loadError)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm(t.integrations.deleteConfirm)) return
    try {
      await integrationsAPI.delete(id)
      toast.success(t.integrations.deleteSuccess)
      loadIntegrations()
    } catch (error: any) {
      console.error('Failed to delete integration:', error)
      toast.error(error.response?.data?.detail || t.integrations.deleteError)
    }
  }

  const handleTest = async (id: number) => {
    setTestingIds((prev) => new Set(prev).add(id))
    try {
      const response = await integrationsAPI.test(id)
      if (response.data.success) {
        toast.success(t.integrations.testSuccess)
      } else {
        toast.error(response.data.message || t.integrations.testError)
      }
      loadIntegrations()
    } catch (error: any) {
      console.error('Test failed:', error)
      toast.error(error.response?.data?.detail || t.integrations.testError)
    } finally {
      setTestingIds((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    }
  }

  const handleSync = async (id: number) => {
    setSyncingIds((prev) => new Set(prev).add(id))
    try {
      const response = await integrationsAPI.sync(id)
      if (response.data.success) {
        toast.success(t.integrations.syncSuccess)
      } else {
        toast.error(response.data.message || t.integrations.syncError)
      }
      loadIntegrations()
    } catch (error: any) {
      console.error('Sync failed:', error)
      toast.error(error.response?.data?.detail || t.integrations.syncError)
    } finally {
      setSyncingIds((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    }
  }

  const toggleActive = async (id: number, currentStatus: boolean) => {
    try {
      await integrationsAPI.update(id, { is_active: !currentStatus })
      toast.success(t.common.status === 'Statut' ? `Intégration ${!currentStatus ? 'activée' : 'désactivée'}` : `Integration ${!currentStatus ? 'activated' : 'deactivated'}`)
      loadIntegrations()
    } catch (error: any) {
      console.error('Failed to update integration:', error)
      toast.error(error.response?.data?.detail || t.integrations.activateError)
    }
  }

  return (
    <DashboardLayout>
      <div className="mb-8 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">{t.integrations.title}</h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            {t.integrations.subtitle}
          </p>
        </div>
        <Link
          to="/dashboard/integrations/new"
          className="inline-flex items-center px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium shadow-sm transition"
        >
          <PlusIcon className="h-5 w-5 mr-2" />
          {t.integrations.newIntegration}
        </Link>
      </div>

      {/* Filters */}
      <div className="mb-6 flex gap-4 items-center">
        <select
          value={filter.type || ''}
          onChange={(e) => setFilter({ ...filter, type: e.target.value || undefined })}
          className="px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
        >
          <option value="">{t?.integrations?.allTypes || 'All Types'}</option>
          {['calendar', 'email', 'contact_management', 'database', 'crm', 'accounting', 'other'].map((value) => (
            <option key={value} value={value}>
              {getIntegrationTypeLabel(value, t)}
            </option>
          ))}
        </select>
        <select
          value={filter.status || ''}
          onChange={(e) => setFilter({ ...filter, status: e.target.value || undefined })}
          className="px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
        >
          <option value="">{t.integrations.allStatuses}</option>
          <option value="active">{t.integrations.active}</option>
          <option value="inactive">{t.integrations.inactive}</option>
          <option value="error">{t.integrations.error}</option>
          <option value="pending_auth">{t.integrations.pendingAuth}</option>
        </select>
      </div>

      {/* Loading Skeleton */}
      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="bg-white dark:bg-gray-800 p-6 rounded-2xl shadow animate-pulse"
            >
              <div className="h-24 bg-gray-200 dark:bg-gray-700 rounded-xl" />
            </div>
          ))}
        </div>
      ) : integrations.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 px-6 text-center bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl shadow-sm">
          <div className="bg-blue-100 dark:bg-blue-900 p-4 rounded-full mb-4">
            <PlusIcon className="h-10 w-10 text-blue-600 dark:text-blue-300" />
          </div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            {t.integrations.noIntegrations}
          </h3>
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-400 max-w-sm">
            {t.common.status === 'Statut' ? 'Connectez vos outils métier pour étendre les capacités de votre agent vocal.' : 'Connect your business tools to extend your voice agent capabilities.'}
          </p>
          <Link
            to="/dashboard/integrations/new"
            className="mt-6 inline-flex items-center px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium transition"
          >
            <PlusIcon className="h-5 w-5 mr-2" />
            {t.integrations.createIntegration}
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {integrations.map((integration) => (
            <div
              key={integration.id}
              className="bg-white dark:bg-gray-800 p-6 rounded-2xl shadow-sm hover:shadow-lg transition-all"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="text-2xl">
                      {getIntegrationTypeLabel(integration.integration_type, t)?.split(' ')[0] || '🔧'}
                    </span>
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                        {integration.name}
                      </h3>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        {getIntegrationTypeLabel(integration.integration_type, t)} • {integration.provider.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      </p>
                    </div>
                  </div>
                  
                  {integration.description && (
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                      {integration.description}
                    </p>
                  )}

                  <div className="flex items-center gap-4 flex-wrap">
                    <span
                      className={`px-2.5 py-1 text-xs font-medium rounded-full ${STATUS_COLORS[integration.status] || STATUS_COLORS.inactive}`}
                    >
                      {integration.status}
                    </span>
                    {integration.last_error && (
                      <div className="flex items-center gap-1 text-xs text-red-600 dark:text-red-400">
                        <ExclamationTriangleIcon className="h-4 w-4" />
                        <span>{integration.last_error.substring(0, 50)}...</span>
                      </div>
                    )}
                    {integration.last_sync_at && (
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        {t.integrations.lastSynced} {new Date(integration.last_sync_at).toLocaleString()}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 ml-4">
                  <button
                    onClick={() => handleTest(integration.id)}
                    disabled={testingIds.has(integration.id)}
                    className="p-2 rounded-lg bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 transition disabled:opacity-50"
                    title={t.integrations.testConnection}
                  >
                    {testingIds.has(integration.id) ? (
                      <ArrowPathIcon className="h-4 w-4 animate-spin" />
                    ) : (
                      <CheckCircleIcon className="h-4 w-4" />
                    )}
                  </button>
                  <button
                    onClick={() => handleSync(integration.id)}
                    disabled={syncingIds.has(integration.id) || !integration.is_active}
                    className="p-2 rounded-lg bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 transition disabled:opacity-50"
                    title={t.integrations.syncData}
                  >
                    {syncingIds.has(integration.id) ? (
                      <ArrowPathIcon className="h-4 w-4 animate-spin" />
                    ) : (
                      <ArrowPathIcon className="h-4 w-4" />
                    )}
                  </button>
                  <button
                    onClick={() => toggleActive(integration.id, integration.is_active)}
                    className={`p-2 rounded-lg transition ${
                      integration.is_active
                        ? 'bg-green-100 hover:bg-green-200 dark:bg-green-900 dark:hover:bg-green-800 text-green-700 dark:text-green-300'
                        : 'bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300'
                    }`}
                    title={integration.is_active ? t.integrations.deactivate : t.integrations.activate}
                  >
                    {integration.is_active ? (
                      <CheckCircleIcon className="h-4 w-4" />
                    ) : (
                      <XCircleIcon className="h-4 w-4" />
                    )}
                  </button>
                  <Link
                    to={`/dashboard/integrations/${integration.id}/edit`}
                    className="p-2 rounded-lg bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 transition"
                    title={t.common.edit}
                  >
                    <PencilIcon className="h-4 w-4" />
                  </Link>
                  <button
                    onClick={() => handleDelete(integration.id)}
                    className="p-2 rounded-lg bg-gray-100 hover:bg-red-100 dark:bg-gray-700 dark:hover:bg-red-900 text-red-600 transition"
                    title={t.common.delete}
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </DashboardLayout>
  )
}


