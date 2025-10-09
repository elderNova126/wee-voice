import { useEffect, useState } from 'react'
import { PlusIcon, KeyIcon, TrashIcon, ClipboardIcon, CheckIcon } from '@heroicons/react/24/outline'
import DashboardLayout from '@/layouts/DashboardLayout'
import { apiKeysAPI } from '@/lib/api'
import toast from 'react-hot-toast'

interface APIKey {
  id: number
  name: string
  key: string
  is_active: boolean
  total_requests: number
  created_at: string
  last_used_at: string | null
}

export default function APIKeysPage() {
  const [apiKeys, setApiKeys] = useState<APIKey[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [copiedKey, setCopiedKey] = useState<string | null>(null)

  useEffect(() => {
    loadAPIKeys()
  }, [])

  const loadAPIKeys = async () => {
    try {
      const response = await apiKeysAPI.list()
      setApiKeys(response.data)
    } catch (error) {
      console.error('Failed to load API keys:', error)
      toast.error('Failed to load API keys')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this API key? This action cannot be undone.')) return

    try {
      await apiKeysAPI.delete(id)
      toast.success('API key deleted successfully')
      loadAPIKeys()
    } catch (error) {
      console.error('Failed to delete API key:', error)
      toast.error('Failed to delete API key')
    }
  }

  const copyToClipboard = (key: string) => {
    navigator.clipboard.writeText(key)
    setCopiedKey(key)
    toast.success('API key copied to clipboard')
    setTimeout(() => setCopiedKey(null), 2000)
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never'
    return new Date(dateString).toLocaleString()
  }

  return (
    <DashboardLayout>
      <div className="mb-8 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">API Keys</h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            Manage API keys for accessing your voice agents
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="btn-primary"
        >
          <PlusIcon className="h-5 w-5 mr-2" />
          New API Key
        </button>
      </div>

      {loading ? (
        <div className="space-y-4">
          {[1, 2].map((i) => (
            <div key={i} className="card animate-pulse">
              <div className="h-20 bg-gray-200 dark:bg-gray-700 rounded"></div>
            </div>
          ))}
        </div>
      ) : apiKeys.length === 0 ? (
        <div className="card text-center py-12">
          <KeyIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-semibold text-gray-900 dark:text-white">No API keys</h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Get started by creating your first API key.
          </p>
          <div className="mt-6">
            <button
              onClick={() => setShowCreateModal(true)}
              className="btn-primary"
            >
              <PlusIcon className="h-5 w-5 mr-2" />
              New API Key
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {apiKeys.map((apiKey) => (
            <div key={apiKey.id} className="card">
              <div className="flex items-start justify-between">
                <div className="flex items-start space-x-4 flex-1">
                  <div className="p-3 bg-green-100 dark:bg-green-900 rounded-lg">
                    <KeyIcon className="h-6 w-6 text-green-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                        {apiKey.name}
                      </h3>
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                        apiKey.is_active
                          ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                          : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                      }`}>
                        {apiKey.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                    <div className="flex items-center space-x-2 mb-2">
                      <code className="text-sm bg-gray-100 dark:bg-gray-700 px-3 py-1 rounded font-mono">
                        {apiKey.key}
                      </code>
                      <button
                        onClick={() => copyToClipboard(apiKey.key)}
                        className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                      >
                        {copiedKey === apiKey.key ? (
                          <CheckIcon className="h-4 w-4 text-green-600" />
                        ) : (
                          <ClipboardIcon className="h-4 w-4 text-gray-500" />
                        )}
                      </button>
                    </div>
                    <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
                      <span>Created: {formatDate(apiKey.created_at)}</span>
                      <span>•</span>
                      <span>Last used: {formatDate(apiKey.last_used_at)}</span>
                      <span>•</span>
                      <span>{apiKey.total_requests} requests</span>
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(apiKey.id)}
                  className="btn-secondary p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900"
                >
                  <TrashIcon className="h-5 w-5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <CreateAPIKeyModal
          onClose={() => setShowCreateModal(false)}
          onCreated={(newKey) => {
            setApiKeys([newKey, ...apiKeys])
            copyToClipboard(newKey.key)
          }}
        />
      )}
    </DashboardLayout>
  )
}

// Create API Key Modal
interface CreateAPIKeyModalProps {
  onClose: () => void
  onCreated: (apiKey: APIKey) => void
}

function CreateAPIKeyModal({ onClose, onCreated }: CreateAPIKeyModalProps) {
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    try {
      const response = await apiKeysAPI.create({ name })
      toast.success('API key created successfully! Key copied to clipboard.')
      onCreated(response.data)
      onClose()
    } catch (error: any) {
      console.error('Failed to create API key:', error)
      toast.error(error.response?.data?.detail || 'Failed to create API key')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={onClose} />

        <div className="relative bg-white dark:bg-gray-800 rounded-lg max-w-md w-full p-6 shadow-xl">
          <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
            Create New API Key
          </h3>

          <form onSubmit={handleSubmit}>
            <div className="mb-6">
              <label htmlFor="name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Key Name
              </label>
              <input
                type="text"
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                className="input"
                placeholder="e.g., Production API Key"
                autoFocus
              />
              <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                Give this key a descriptive name to identify where it's used.
              </p>
            </div>

            <div className="bg-yellow-50 dark:bg-yellow-900 border border-yellow-200 dark:border-yellow-700 rounded-lg p-4 mb-6">
              <p className="text-sm text-yellow-800 dark:text-yellow-200">
                ⚠️ Make sure to copy your API key after creation. You won't be able to see it again!
              </p>
            </div>

            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={onClose}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="btn-primary"
              >
                {loading ? 'Creating...' : 'Create API Key'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
