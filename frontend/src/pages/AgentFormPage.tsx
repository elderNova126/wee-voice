import { useState, useEffect, useCallback } from 'react'
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

  const loadAgent = useCallback(async (agentId: number) => {
    try {
      const { data: agent } = await agentsAPI.get(agentId)
      setFormData({
        name: agent.name,
        description: agent.description || '',
        language: agent.language || 'fr-FR',
        system_prompt: agent.system_prompt || '',
        is_public: agent.is_public ?? false,
        is_active: agent.is_active ?? true
      })
    } catch (err) {
      toast.error('Failed to load agent.')
      navigate('/dashboard/agents')
    } finally {
      setLoadingAgent(false)
    }
  }, [navigate])

  useEffect(() => {
    if (isEdit && id) loadAgent(parseInt(id))
  }, [isEdit, id, loadAgent])

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    const { name, type, value } = e.target
    if (type === 'checkbox') {
      const target = e.target as HTMLInputElement
      setFormData(prev => ({ ...prev, [name]: target.checked }))
    } else {
      setFormData(prev => ({ ...prev, [name]: value }))
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      if (isEdit && id) {
        await agentsAPI.update(Number(id), formData)
        toast.success('✅ Agent updated successfully')
      } else {
        await agentsAPI.create(formData)
        toast.success('🎉 Agent created successfully')
      }
      navigate('/dashboard/agents')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save agent.')
    } finally {
      setLoading(false)
    }
  }

  if (loadingAgent) {
    return (
      <DashboardLayout>
        <div className="animate-pulse max-w-3xl space-y-6">
          <div className="h-8 w-1/3 rounded bg-gray-200 dark:bg-gray-700"></div>
          <div className="h-64 rounded bg-gray-200 dark:bg-gray-700"></div>
        </div>
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout>
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <Link
            to="/dashboard/agents"
            className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition"
          >
            <ArrowLeftIcon className="mr-1 h-4 w-4" />
            Back to Agents
          </Link>
          <h1 className="mt-2 text-3xl font-semibold text-gray-900 dark:text-white tracking-tight">
            {isEdit ? 'Edit Agent' : 'Create New Agent'}
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Configure details, behavior, and language for your AI agent.
          </p>
        </div>
      </div>

      {/* Form Card */}
      <form
        onSubmit={handleSubmit}
        className="relative mx-auto max-w-5xl rounded-2xl border border-gray-200 dark:border-gray-700/80 bg-gradient-to-b from-white to-gray-50 dark:from-gray-800 dark:to-gray-850 p-8 shadow-[0_2px_20px_-5px_rgba(0,0,0,0.1)] backdrop-blur-sm transition-all"
      >
        {/* Gradient border accent */}
        <div className="pointer-events-none absolute inset-0 rounded-2xl ring-1 ring-inset ring-gray-200 dark:ring-gray-700"></div>

        <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
          {/* LEFT COLUMN */}
          <div className="space-y-6">
            {/* Agent Name */}
            <div className="group">
              <label htmlFor="name" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                Agent Name *
              </label>
              <input
                id="name"
                name="name"
                required
                value={formData.name}
                onChange={handleChange}
                placeholder="Customer Support Bot"
                className="mt-1 w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white/80 dark:bg-gray-900/60 px-3 py-2 text-sm text-gray-900 dark:text-white shadow-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-400 focus:ring-offset-0 transition-all"
              />
            </div>

            {/* Description */}
            <div>
              <label htmlFor="description" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                Description
              </label>
              <textarea
                id="description"
                name="description"
                rows={3}
                value={formData.description}
                onChange={handleChange}
                placeholder="Briefly describe this agent’s role..."
                className="mt-1 w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white/80 dark:bg-gray-900/60 px-3 py-2 text-sm text-gray-900 dark:text-white shadow-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-400 focus:ring-offset-0 transition-all resize-none"
              />
            </div>

            {/* Language */}
            <div>
              <label htmlFor="language" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                Language *
              </label>
              <select
                id="language"
                name="language"
                required
                value={formData.language}
                onChange={handleChange}
                className="mt-1 w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white/80 dark:bg-gray-900/60 px-3 py-2 text-sm text-gray-900 dark:text-white shadow-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-400 focus:ring-offset-0 transition-all"
              >
                <option value="fr-FR">🇫🇷 French</option>
                <option value="en-US">🇬🇧 English</option>
              </select>
            </div>

            {/* Checkboxes */}
            <div className="space-y-3 pt-4 border-t border-gray-100 dark:border-gray-700/50">
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  name="is_active"
                  checked={formData.is_active}
                  onChange={handleChange}
                  className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  Active (can receive calls)
                </span>
              </label>

              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  name="is_public"
                  checked={formData.is_public}
                  onChange={handleChange}
                  className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  Public (no authentication)
                </span>
              </label>
            </div>
          </div>

          {/* RIGHT COLUMN */}
          <div>
            <label htmlFor="system_prompt" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
              System Prompt *
            </label>
            <textarea
              id="system_prompt"
              name="system_prompt"
              required
              rows={14}
              value={formData.system_prompt}
              onChange={handleChange}
              className="mt-1 w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white/80 dark:bg-gray-900/60 px-3 py-2 font-mono text-sm text-gray-900 dark:text-white shadow-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-400 focus:ring-offset-0 transition-all resize-none"
              placeholder={
                formData.language === 'fr-FR'
                  ? 'Tu es un assistant vocal intelligent et serviable.\nRéponds avec courtoisie et précision.'
                  : 'You are a helpful and intelligent voice assistant.\nRespond courteously and clearly.'
              }
            />
            <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
              Defines the assistant’s tone, context, and behavior.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-10 flex justify-end gap-3 border-t border-gray-200 dark:border-gray-700/60 pt-6">
          <Link
            to="/dashboard/agents"
            className="inline-flex items-center justify-center rounded-lg border border-gray-300 dark:border-gray-600 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700/40 transition"
          >
            Cancel
          </Link>
          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center justify-center rounded-lg bg-gradient-to-r from-primary-600 to-primary-500 hover:from-primary-700 hover:to-primary-600 text-white px-5 py-2 text-sm font-medium shadow-md transition disabled:opacity-70"
          >
            {loading ? 'Saving...' : isEdit ? 'Update Agent' : 'Create Agent'}
          </button>
        </div>
      </form>
    </DashboardLayout>
  )
}
