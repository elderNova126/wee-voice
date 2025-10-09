import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { authAPI } from '@/lib/api'
import toast from 'react-hot-toast'
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import {
  KeyIcon,
  PlusIcon,
  TrashIcon,
  ClipboardDocumentIcon,
  CheckIcon,
} from '@heroicons/react/24/outline'

interface APIKey {
  id: number
  key: string
  name: string
  is_active: boolean
  created_at: string
  total_requests: number
  last_used_at: string | null
}

export default function ApiKeysPage() {
  const queryClient = useQueryClient()
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [copiedKey, setCopiedKey] = useState<string | null>(null)
  
  const { data: apiKeys, isLoading } = useQuery({
    queryKey: ['api-keys'],
    queryFn: async () => {
      const response = await authAPI.listApiKeys()
      return response.data
    },
  })
  
  const deleteKeyMutation = useMutation({
    mutationFn: (keyId: number) => authAPI.deleteApiKey(keyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-keys'] })
      toast.success('Clé API supprimée')
    },
    onError: () => {
      toast.error('Erreur lors de la suppression')
    },
  })
  
  const copyToClipboard = (key: string) => {
    navigator.clipboard.writeText(key)
    setCopiedKey(key)
    toast.success('Clé copiée dans le presse-papiers')
    setTimeout(() => setCopiedKey(null), 2000)
  }
  
  const handleDelete = (keyId: number) => {
    if (confirm('Êtes-vous sûr de vouloir supprimer cette clé API ?')) {
      deleteKeyMutation.mutate(keyId)
    }
  }
  
  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
            Clés API
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Gérez vos clés d'accès à l'API
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="btn-primary flex items-center"
        >
          <PlusIcon className="w-5 h-5 mr-2" />
          Nouvelle Clé
        </button>
      </div>
      
      {/* API Documentation */}
      <div className="card mb-6 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
        <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
          📚 Documentation de l'API
        </h3>
        <p className="text-gray-700 dark:text-gray-300 mb-3">
          Utilisez vos clés API pour intégrer VoiceAgent dans vos applications.
        </p>
        <div className="bg-gray-900 rounded-lg p-4 text-sm font-mono text-gray-100 overflow-x-auto">
          <div className="mb-2">// Exemple d'utilisation WebSocket</div>
          <div className="text-green-400">
            const ws = new WebSocket('ws://api.voiceagent.com/ws/voice/AGENT_ID?api_key=YOUR_API_KEY');
          </div>
        </div>
      </div>
      
      {/* API Keys List */}
      {isLoading ? (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto"></div>
        </div>
      ) : apiKeys && apiKeys.length > 0 ? (
        <div className="space-y-4">
          {apiKeys.map((apiKey: APIKey) => (
            <div key={apiKey.id} className="card">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-3 mb-3">
                    <KeyIcon className="w-5 h-5 text-primary-600" />
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                      {apiKey.name}
                    </h3>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                      apiKey.is_active
                        ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                        : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                    }`}>
                      {apiKey.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                  
                  <div className="bg-gray-100 dark:bg-gray-700 rounded-lg p-3 mb-3 flex items-center justify-between">
                    <code className="text-sm text-gray-900 dark:text-white font-mono">
                      {apiKey.key}
                    </code>
                    <button
                      onClick={() => copyToClipboard(apiKey.key)}
                      className="ml-4 p-2 text-gray-600 hover:text-primary-600 dark:text-gray-400"
                    >
                      {copiedKey === apiKey.key ? (
                        <CheckIcon className="w-5 h-5 text-green-600" />
                      ) : (
                        <ClipboardDocumentIcon className="w-5 h-5" />
                      )}
                    </button>
                  </div>
                  
                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <p className="text-gray-600 dark:text-gray-400">Créée le</p>
                      <p className="text-gray-900 dark:text-white font-medium">
                        {format(new Date(apiKey.created_at), 'PP', { locale: fr })}
                      </p>
                    </div>
                    <div>
                      <p className="text-gray-600 dark:text-gray-400">Requêtes totales</p>
                      <p className="text-gray-900 dark:text-white font-medium">
                        {apiKey.total_requests}
                      </p>
                    </div>
                    <div>
                      <p className="text-gray-600 dark:text-gray-400">Dernière utilisation</p>
                      <p className="text-gray-900 dark:text-white font-medium">
                        {apiKey.last_used_at
                          ? format(new Date(apiKey.last_used_at), 'PP', { locale: fr })
                          : 'Jamais'}
                      </p>
                    </div>
                  </div>
                </div>
                
                <button
                  onClick={() => handleDelete(apiKey.id)}
                  className="ml-4 p-2 text-gray-600 hover:text-red-600 dark:text-gray-400"
                >
                  <TrashIcon className="w-5 h-5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="card text-center py-12">
          <KeyIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400 mb-4">
            Vous n'avez pas encore créé de clé API
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="btn-primary"
          >
            Créer ma première clé
          </button>
        </div>
      )}
      
      {/* Create Modal */}
      {showCreateModal && (
        <CreateKeyModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ['api-keys'] })
            setShowCreateModal(false)
          }}
        />
      )}
    </div>
  )
}

interface CreateKeyModalProps {
  onClose: () => void
  onSuccess: () => void
}

function CreateKeyModal({ onClose, onSuccess }: CreateKeyModalProps) {
  const [name, setName] = useState('')
  
  const mutation = useMutation({
    mutationFn: (name: string) => authAPI.createApiKey(name),
    onSuccess: (response) => {
      toast.success('Clé API créée avec succès')
      // Copy to clipboard immediately
      navigator.clipboard.writeText(response.data.key)
      toast.success('Clé copiée dans le presse-papiers')
      onSuccess()
    },
    onError: () => {
      toast.error('Erreur lors de la création de la clé')
    },
  })
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    mutation.mutate(name)
  }
  
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full mx-4">
        <div className="p-6">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
            Nouvelle clé API
          </h2>
          
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Nom de la clé
              </label>
              <input
                type="text"
                required
                placeholder="ex: Production, Development..."
                className="input"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Donnez un nom descriptif pour identifier cette clé
              </p>
            </div>
            
            <div className="flex justify-end space-x-4 pt-4">
              <button
                type="button"
                onClick={onClose}
                className="btn-secondary"
              >
                Annuler
              </button>
              <button
                type="submit"
                disabled={mutation.isPending}
                className="btn-primary"
              >
                {mutation.isPending ? 'Création...' : 'Créer la clé'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}

