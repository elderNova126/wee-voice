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

const INTEGRATION_TYPE_LABELS: Record<string, string> = {
  calendar: '📅 Calendar',
  email: '📧 Email',
  contact_management: '👥 Contacts',
  database: '💾 Database',
  crm: '📊 CRM',
  accounting: '💰 Accounting',
  other: '🔧 Other',
}

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
  inactive: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  error: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
  pending_auth: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300',
}

export default function IntegrationsPage() {
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
      toast.error(error.response?.data?.detail || 'Failed to load integrations')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this integration?')) return
    try {
      await integrationsAPI.delete(id)
      toast.success('Integration deleted successfully')
      loadIntegrations()
    } catch (error: any) {
      console.error('Failed to delete integration:', error)
      toast.error(error.response?.data?.detail || 'Failed to delete integration')
    }
  }

  const handleTest = async (id: number) => {
    setTestingIds((prev) => new Set(prev).add(id))
    try {
      const response = await integrationsAPI.test(id)
      if (response.data.success) {
        toast.success('Connection test successful')
      } else {
        toast.error(response.data.message || 'Connection test failed')
      }
      loadIntegrations()
    } catch (error: any) {
      console.error('Test failed:', error)
      toast.error(error.response?.data?.detail || 'Connection test failed')
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
        toast.success('Sync completed successfully')
      } else {
        toast.error(response.data.message || 'Sync failed')
      }
      loadIntegrations()
    } catch (error: any) {
      console.error('Sync failed:', error)
      toast.error(error.response?.data?.detail || 'Sync failed')
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
      toast.success(`Integration ${!currentStatus ? 'activated' : 'deactivated'}`)
      loadIntegrations()
    } catch (error: any) {
      console.error('Failed to update integration:', error)
      toast.error(error.response?.data?.detail || 'Failed to update integration')
    }
  }

  return (
    <DashboardLayout>
      <div className="mb-8 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Integrations</h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            Connect your calendar, email, CRM, and other business tools
          </p>
        </div>
        <Link
          to="/dashboard/integrations/new"
          className="inline-flex items-center px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium shadow-sm transition"
        >
          <PlusIcon className="h-5 w-5 mr-2" />
          New Integration
        </Link>
      </div>

      {/* Filters */}
      <div className="mb-6 flex gap-4 items-center">
        <select
          value={filter.type || ''}
          onChange={(e) => setFilter({ ...filter, type: e.target.value || undefined })}
          className="px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
        >
          <option value="">All Types</option>
          {Object.entries(INTEGRATION_TYPE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <select
          value={filter.status || ''}
          onChange={(e) => setFilter({ ...filter, status: e.target.value || undefined })}
          className="px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
        >
          <option value="">All Statuses</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
          <option value="error">Error</option>
          <option value="pending_auth">Pending Auth</option>
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
            No Integrations Yet
          </h3>
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-400 max-w-sm">
            Connect your business tools to extend your voice agent capabilities.
          </p>
          <Link
            to="/dashboard/integrations/new"
            className="mt-6 inline-flex items-center px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium transition"
          >
            <PlusIcon className="h-5 w-5 mr-2" />
            Create Integration
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
                      {INTEGRATION_TYPE_LABELS[integration.integration_type]?.split(' ')[0] || '🔧'}
                    </span>
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                        {integration.name}
                      </h3>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        {INTEGRATION_TYPE_LABELS[integration.integration_type]} • {integration.provider.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
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
                        Last synced: {new Date(integration.last_sync_at).toLocaleString()}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 ml-4">
                  <button
                    onClick={() => handleTest(integration.id)}
                    disabled={testingIds.has(integration.id)}
                    className="p-2 rounded-lg bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 transition disabled:opacity-50"
                    title="Test Connection"
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
                    title="Sync Data"
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
                    title={integration.is_active ? 'Deactivate' : 'Activate'}
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
                    title="Edit"
                  >
                    <PencilIcon className="h-4 w-4" />
                  </Link>
                  <button
                    onClick={() => handleDelete(integration.id)}
                    className="p-2 rounded-lg bg-gray-100 hover:bg-red-100 dark:bg-gray-700 dark:hover:bg-red-900 text-red-600 transition"
                    title="Delete"
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


