import { useEffect, useState } from 'react'
import {
  PlusIcon,
  KeyIcon,
  TrashIcon,
  ClipboardIcon,
  CheckIcon,
} from '@heroicons/react/24/outline'
import { apiKeysAPI } from '@/lib/api'
import toast from 'react-hot-toast'
import { useTranslation } from '@/lib/translations'

interface APIKey {
  id: number
  name: string
  key: string
  is_active: boolean
  total_requests: number
  created_at: string
  last_used_at: string | null
}

export default function ApiKeysContent() {
  const t = useTranslation()
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
      toast.error(t.apiKeys.createError.replace('create', 'load'))
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm(t.apiKeys.deleteConfirm)) return
    try {
      await apiKeysAPI.delete(id)
      toast.success(t.apiKeys.deleteSuccess)
      loadAPIKeys()
    } catch (error) {
      console.error('Failed to delete API key:', error)
      toast.error(t.apiKeys.deleteError)
    }
  }

  const copyToClipboard = (key: string) => {
    navigator.clipboard.writeText(key)
    setCopiedKey(key)
    toast.success(t.apiKeys.copySuccess)
    setTimeout(() => setCopiedKey(null), 2000)
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return t.apiKeys.never
    return new Date(dateString).toLocaleString()
  }

  return (
    <div className="max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-10">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            {t.apiKeys.title}
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            {t.apiKeys.subtitle}
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="btn-primary flex items-center gap-2"
        >
          <PlusIcon className="h-5 w-5" />
          {t.apiKeys.createApiKey}
        </button>
      </div>

      {/* Loading Skeleton */}
      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="animate-pulse rounded-2xl border border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-800/50 h-24"></div>
          ))}
        </div>
      ) : apiKeys.length === 0 ? (
        <div className="border border-dashed border-gray-300 dark:border-gray-600 rounded-2xl py-16 text-center bg-gray-50/50 dark:bg-gray-800/50">
          <KeyIcon className="mx-auto h-10 w-10 text-gray-400 mb-3" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            {t.apiKeys.noApiKeys}
          </h3>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            {t.common.status === 'Statut' ? 'Créez votre première clé API pour commencer à intégrer vos agents.' : 'Create your first API key to start integrating your agents.'}
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="btn-primary mt-6 inline-flex items-center gap-2"
          >
            <PlusIcon className="h-5 w-5" />
            {t.apiKeys.createApiKey}
          </button>
        </div>
      ) : (
        <div className="grid gap-5">
          {apiKeys.map((apiKey) => (
            <div
              key={apiKey.id}
              className="border border-gray-200 dark:border-gray-700 rounded-2xl p-5 bg-white dark:bg-gray-800 shadow-sm hover:shadow-md transition-all"
            >
              <div className="flex justify-between items-start">
                <div className="flex gap-4 flex-1">
                  <div className="p-3 bg-primary-50 dark:bg-primary-900/30 rounded-xl flex-shrink-0">
                    <KeyIcon className="h-6 w-6 text-primary-600" />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-semibold text-gray-900 dark:text-white text-lg">
                        {apiKey.name}
                      </h3>
                      <span
                        className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                          apiKey.is_active
                            ? 'bg-green-100 text-green-800 dark:bg-green-900/60 dark:text-green-200'
                            : 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
                        }`}
                      >
                        {apiKey.is_active ? (t.common.status === 'Statut' ? 'Actif' : 'Active') : (t.common.status === 'Statut' ? 'Inactif' : 'Inactive')}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 mb-2">
                      <code className="px-3 py-1 bg-gray-100 dark:bg-gray-700 rounded text-sm font-mono">
                        {apiKey.key}
                      </code>
                      <button
                        onClick={() => copyToClipboard(apiKey.key)}
                        className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition"
                        title={t.common.status === 'Statut' ? 'Copier la clé' : 'Copy key'}
                      >
                        {copiedKey === apiKey.key ? (
                          <CheckIcon className="h-4 w-4 text-green-600" />
                        ) : (
                          <ClipboardIcon className="h-4 w-4 text-gray-500" />
                        )}
                      </button>
                    </div>

                    <div className="flex flex-wrap items-center gap-3 text-sm text-gray-500 dark:text-gray-400">
                      <span>{t.common.status === 'Statut' ? 'Créé :' : 'Created:'} {formatDate(apiKey.created_at)}</span>
                      <span>•</span>
                      <span>{t.common.status === 'Statut' ? 'Dernière utilisation :' : 'Last used:'} {formatDate(apiKey.last_used_at)}</span>
                      <span>•</span>
                      <span>{apiKey.total_requests} {t.common.status === 'Statut' ? 'requêtes' : 'requests'}</span>
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => handleDelete(apiKey.id)}
                  className="btn-secondary p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/40 rounded-lg transition"
                  title={t.common.status === 'Statut' ? 'Supprimer la clé API' : 'Delete API Key'}
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
    </div>
  )
}

// 🔑 Create API Key Modal
interface CreateAPIKeyModalProps {
  onClose: () => void
  onCreated: (apiKey: APIKey) => void
}

function CreateAPIKeyModal({ onClose, onCreated }: CreateAPIKeyModalProps) {
  const t = useTranslation()
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      const response = await apiKeysAPI.create({ name })
      toast.success(t.apiKeys.createSuccess || (t.common.status === 'Statut' ? 'Clé API créée avec succès !' : 'API key created successfully!'))
      onCreated(response.data)
      onClose()
    } catch (error: any) {
      console.error('Failed to create API key:', error)
      toast.error(error.response?.data?.detail || t.apiKeys.createError)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6">
      <div
        className="absolute inset-0 bg-gray-900/70 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-w-md w-full p-6 border border-gray-200 dark:border-gray-700">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
          {t.apiKeys.createApiKey}
        </h2>
        <form onSubmit={handleSubmit}>
          <div className="mb-5">
            <label
              htmlFor="name"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
            >
              {t.common.status === 'Statut' ? 'Nom de la clé' : 'Key Name'}
            </label>
            <input
              type="text"
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder={t.common.status === 'Statut' ? 'ex. Clé de production' : 'e.g., Production Key'}
              className="input w-full"
            />
          </div>

          <div className="bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-700 rounded-xl p-4 text-sm text-yellow-800 dark:text-yellow-200 mb-6">
            ⚠️ {t.common.status === 'Statut' ? 'Copiez votre clé API immédiatement après sa création — elle ne sera plus affichée.' : 'Copy your API key immediately after creation — it won\'t be shown again.'}
          </div>

          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="btn-secondary"
            >
              {t.common.cancel}
            </button>
            <button
              type="submit"
              disabled={loading}
              className="btn-primary"
            >
              {loading ? (t.common.status === 'Statut' ? 'Création...' : 'Creating...') : (t.common.status === 'Statut' ? 'Créer la clé' : 'Create Key')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

