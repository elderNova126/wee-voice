import { useState, useEffect } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { ArrowLeftIcon } from '@heroicons/react/24/outline'
import DashboardLayout from '@/layouts/DashboardLayout'
import { agentsAPI } from '@/lib/api'
import toast from 'react-hot-toast'

interface AgentFormData {
  name: string
  description: string
  language: string
  system_prompt: string
  is_public: boolean
  is_active: boolean
}

export default function AgentFormPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isEdit = Boolean(id)

  const [formData, setFormData] = useState<AgentFormData>({
    name: '',
    description: '',
    language: 'fr-FR',
    system_prompt: '',
    is_public: false,
    is_active: true
  })
  const [loading, setLoading] = useState(false)
  const [loadingAgent, setLoadingAgent] = useState(isEdit)

  useEffect(() => {
    if (isEdit && id) {
      loadAgent(parseInt(id))
    }
  }, [isEdit, id])

  const loadAgent = async (agentId: number) => {
    try {
      const response = await agentsAPI.get(agentId)
      const agent = response.data
      setFormData({
        name: agent.name,
        description: agent.description || '',
        language: agent.language,
        system_prompt: agent.system_prompt,
        is_public: agent.is_public,
        is_active: agent.is_active
      })
    } catch (error) {
      console.error('Failed to load agent:', error)
      toast.error('Failed to load agent')
      navigate('/dashboard/agents')
    } finally {
      setLoadingAgent(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    try {
      if (isEdit && id) {
        await agentsAPI.update(parseInt(id), formData)
        toast.success('Agent updated successfully')
      } else {
        await agentsAPI.create(formData)
        toast.success('Agent created successfully')
      }
      navigate('/dashboard/agents')
    } catch (error: any) {
      console.error('Failed to save agent:', error)
      toast.error(error.response?.data?.detail || 'Failed to save agent')
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? (e.target as HTMLInputElement).checked : value
    }))
  }

  if (loadingAgent) {
    return (
      <DashboardLayout>
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-1/4 mb-4"></div>
          <div className="h-64 bg-gray-200 dark:bg-gray-700 rounded"></div>
        </div>
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout>
      <div className="mb-8">
        <Link
          to="/dashboard/agents"
          className="inline-flex items-center text-gray-600 dark:text-gray-400 hover:text-primary-600 mb-4"
        >
          <ArrowLeftIcon className="w-5 h-5 mr-2" />
          Back to Agents
        </Link>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          {isEdit ? 'Edit Agent' : 'Create New Agent'}
        </h1>
      </div>

      <div className="max-w-3xl">
        <form onSubmit={handleSubmit} className="card">
          <div className="space-y-6">
            {/* Name */}
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Agent Name *
              </label>
              <input
                type="text"
                id="name"
                name="name"
                value={formData.name}
                onChange={handleChange}
                required
                className="input"
                placeholder="e.g., Customer Support Agent"
              />
            </div>

            {/* Description */}
            <div>
              <label htmlFor="description" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Description
              </label>
              <textarea
                id="description"
                name="description"
                value={formData.description}
                onChange={handleChange}
                rows={3}
                className="input"
                placeholder="Brief description of what this agent does..."
              />
            </div>

            {/* Language */}
            <div>
              <label htmlFor="language" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Language *
              </label>
              <select
                id="language"
                name="language"
                value={formData.language}
                onChange={handleChange}
                required
                className="input"
              >
                <option value="fr-FR">🇫🇷 French</option>
                <option value="en-US">🇬🇧 English</option>
              </select>
            </div>

            {/* System Prompt */}
            <div>
              <label htmlFor="system_prompt" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                System Prompt *
              </label>
              <textarea
                id="system_prompt"
                name="system_prompt"
                value={formData.system_prompt}
                onChange={handleChange}
                required
                rows={8}
                className="input font-mono text-sm"
                placeholder={formData.language === 'fr-FR' 
                  ? "Tu es un assistant vocal intelligent et serviable.\nTu réponds aux questions des clients avec courtoisie.\nTu peux aider avec les commandes, retours, et questions générales."
                  : "You are an intelligent and helpful voice assistant.\nYou answer customer questions courteously.\nYou can help with orders, returns, and general inquiries."
                }
              />
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Define how your agent should behave and respond. Be specific about its role and capabilities.
              </p>
            </div>

            {/* Checkboxes */}
            <div className="space-y-4">
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="is_active"
                  name="is_active"
                  checked={formData.is_active}
                  onChange={handleChange}
                  className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                />
                <label htmlFor="is_active" className="ml-2 block text-sm text-gray-700 dark:text-gray-300">
                  Active (agent can receive calls)
                </label>
              </div>

              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="is_public"
                  name="is_public"
                  checked={formData.is_public}
                  onChange={handleChange}
                  className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                />
                <label htmlFor="is_public" className="ml-2 block text-sm text-gray-700 dark:text-gray-300">
                  Public (available without authentication)
                </label>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="mt-8 flex justify-end gap-3">
            <Link
              to="/dashboard/agents"
              className="btn-secondary"
            >
              Cancel
            </Link>
            <button
              type="submit"
              disabled={loading}
              className="btn-primary"
            >
              {loading ? 'Saving...' : (isEdit ? 'Update Agent' : 'Create Agent')}
            </button>
          </div>
        </form>
      </div>
    </DashboardLayout>
  )
}

