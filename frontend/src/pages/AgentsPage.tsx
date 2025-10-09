import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { agentsAPI } from '@/lib/api'
import toast from 'react-hot-toast'
import { PlusIcon, PencilIcon, TrashIcon } from '@heroicons/react/24/outline'

interface Agent {
  id: number
  name: string
  description: string
  language: string
  is_active: boolean
  is_public: boolean
}

export default function AgentsPage() {
  const queryClient = useQueryClient()
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingAgent, setEditingAgent] = useState<Agent | null>(null)
  
  const { data: agents, isLoading } = useQuery({
    queryKey: ['agents'],
    queryFn: async () => {
      const response = await agentsAPI.list()
      return response.data
    },
  })
  
  const deleteAgentMutation = useMutation({
    mutationFn: (id: number) => agentsAPI.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] })
      toast.success('Agent supprimé avec succès')
    },
    onError: () => {
      toast.error('Erreur lors de la suppression')
    },
  })
  
  const handleDelete = (id: number) => {
    if (confirm('Êtes-vous sûr de vouloir supprimer cet agent ?')) {
      deleteAgentMutation.mutate(id)
    }
  }
  
  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
            Mes Agents
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Gérez vos agents vocaux intelligents
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="btn-primary flex items-center"
        >
          <PlusIcon className="w-5 h-5 mr-2" />
          Nouvel Agent
        </button>
      </div>
      
      {isLoading ? (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto"></div>
        </div>
      ) : agents && agents.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {agents.map((agent: Agent) => (
            <div key={agent.id} className="card hover:shadow-lg transition-shadow">
              <div className="flex items-start justify-between mb-4">
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">
                    {agent.name}
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {agent.description || 'Aucune description'}
                  </p>
                </div>
                <div className="flex space-x-2">
                  <button
                    onClick={() => setEditingAgent(agent)}
                    className="p-2 text-gray-600 hover:text-primary-600 dark:text-gray-400"
                  >
                    <PencilIcon className="w-5 h-5" />
                  </button>
                  <button
                    onClick={() => handleDelete(agent.id)}
                    className="p-2 text-gray-600 hover:text-red-600 dark:text-gray-400"
                  >
                    <TrashIcon className="w-5 h-5" />
                  </button>
                </div>
              </div>
              
              <div className="space-y-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-gray-600 dark:text-gray-400">Langue</span>
                  <span className="text-gray-900 dark:text-white font-medium">
                    {agent.language}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-600 dark:text-gray-400">Statut</span>
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                    agent.is_active
                      ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                      : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                  }`}>
                    {agent.is_active ? 'Actif' : 'Inactif'}
                  </span>
                </div>
                {agent.is_public && (
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600 dark:text-gray-400">Visibilité</span>
                    <span className="px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                      Public
                    </span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="card text-center py-12">
          <p className="text-gray-600 dark:text-gray-400 mb-4">
            Vous n'avez pas encore créé d'agent
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="btn-primary"
          >
            Créer mon premier agent
          </button>
        </div>
      )}
      
      {/* Create/Edit Modal */}
      {(showCreateModal || editingAgent) && (
        <AgentFormModal
          agent={editingAgent}
          onClose={() => {
            setShowCreateModal(false)
            setEditingAgent(null)
          }}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ['agents'] })
            setShowCreateModal(false)
            setEditingAgent(null)
          }}
        />
      )}
    </div>
  )
}

interface AgentFormModalProps {
  agent: Agent | null
  onClose: () => void
  onSuccess: () => void
}

function AgentFormModal({ agent, onClose, onSuccess }: AgentFormModalProps) {
  const [formData, setFormData] = useState({
    name: agent?.name || '',
    description: agent?.description || '',
    language: agent?.language || 'fr-FR',
    voice_id: 'fr-FR-Neural2-A',
    system_prompt: agent ? '' : 'Tu es un assistant vocal intelligent et serviable qui répond en français.',
    is_public: agent?.is_public || false,
  })
  
  const mutation = useMutation({
    mutationFn: (data: any) => {
      return agent
        ? agentsAPI.update(agent.id, data)
        : agentsAPI.create(data)
    },
    onSuccess: () => {
      toast.success(agent ? 'Agent modifié' : 'Agent créé avec succès')
      onSuccess()
    },
    onError: () => {
      toast.error('Erreur lors de la sauvegarde')
    },
  })
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    mutation.mutate(formData)
  }
  
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
            {agent ? 'Modifier l\'agent' : 'Nouvel agent'}
          </h2>
          
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Nom de l'agent *
              </label>
              <input
                type="text"
                required
                className="input"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Description
              </label>
              <textarea
                className="input"
                rows={3}
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Langue
              </label>
              <select
                className="input"
                value={formData.language}
                onChange={(e) => setFormData({ ...formData, language: e.target.value })}
              >
                <option value="fr-FR">Français (France)</option>
                <option value="fr-CA">Français (Canada)</option>
                <option value="en-US">English (US)</option>
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Instructions système *
              </label>
              <textarea
                required
                className="input"
                rows={5}
                placeholder="Décrivez le comportement de l'agent..."
                value={formData.system_prompt}
                onChange={(e) => setFormData({ ...formData, system_prompt: e.target.value })}
              />
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Instructions qui définissent le comportement et la personnalité de l'agent
              </p>
            </div>
            
            <div className="flex items-center">
              <input
                type="checkbox"
                id="is_public"
                className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                checked={formData.is_public}
                onChange={(e) => setFormData({ ...formData, is_public: e.target.checked })}
              />
              <label htmlFor="is_public" className="ml-2 text-sm text-gray-700 dark:text-gray-300">
                Rendre cet agent public (démo)
              </label>
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
                {mutation.isPending ? 'Sauvegarde...' : 'Sauvegarder'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}

