import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { 
  ArrowLeftIcon, 
  CloudArrowUpIcon, 
  DocumentTextIcon,
  TrashIcon,
  CheckCircleIcon 
} from '@heroicons/react/24/outline'
import DashboardLayout from '@/layouts/DashboardLayout'
import { agentsAPI, api } from '@/lib/api'
import toast from 'react-hot-toast'

interface AgentFormData {
  name: string
  description: string
  language: string
  system_prompt: string
  is_public: boolean
  is_active: boolean
  rag_enabled?: boolean
}

interface KnowledgeDocument {
  id: number
  original_filename: string
  source_type: 'pdf' | 'website'
  source_url?: string
  status: 'completed' | 'processing' | 'failed'
  total_chunks: number
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
    is_active: true,
    rag_enabled: false
  })

  const [loading, setLoading] = useState(false)
  const [loadingAgent, setLoadingAgent] = useState(isEdit)
  
  // RAG/Knowledge Base state
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([])
  const [websiteUrl, setWebsiteUrl] = useState('')
  const [uploading, setUploading] = useState(false)

  const loadAgent = useCallback(async (agentId: number) => {
    try {
      const { data: agent } = await agentsAPI.get(agentId)
      setFormData({
        name: agent.name,
        description: agent.description || '',
        language: agent.language || 'fr-FR',
        system_prompt: agent.system_prompt || '',
        is_public: agent.is_public ?? false,
        is_active: agent.is_active ?? true,
        rag_enabled: agent.rag_enabled ?? false
      })
      
      // Load documents if agent exists
      if (agent.rag_enabled) {
        try {
          const { data: docs } = await api.get(`/agents/${agentId}/documents`)
          setDocuments(docs)
        } catch (err) {
          console.log('No documents found or RAG not set up yet')
        }
      }
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

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    if (!id) {
      toast.error('Please save the agent first before uploading documents')
      return
    }

    const file = event.target.files?.[0]
    if (!file) return

    if (!file.name.endsWith('.pdf')) {
      toast.error('Only PDF files are supported')
      return
    }

    if (file.size > 10 * 1024 * 1024) {
      toast.error('File size must be less than 10MB')
      return
    }

    try {
      setUploading(true)
      const formData = new FormData()
      formData.append('file', file)

      await api.post(`/agents/${id}/documents`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })

      toast.success('Document uploaded successfully')
      // Reload documents
      const { data: docs } = await api.get(`/agents/${id}/documents`)
      setDocuments(docs)
      
      // Enable RAG if not already enabled
      if (!formData.rag_enabled) {
        setFormData(prev => ({ ...prev, rag_enabled: true }))
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to upload document')
    } finally {
      setUploading(false)
      // Reset input
      event.target.value = ''
    }
  }

  const handleWebsiteScrape = async () => {
    if (!id) {
      toast.error('Please save the agent first before adding websites')
      return
    }

    if (!websiteUrl) {
      toast.error('Please enter a website URL')
      return
    }

    try {
      new URL(websiteUrl)
    } catch {
      toast.error('Please enter a valid URL')
      return
    }

    try {
      setUploading(true)
      await api.post(`/agents/${id}/documents/website`, { url: websiteUrl })
      
      toast.success('Website scraped successfully')
      setWebsiteUrl('')
      
      // Reload documents
      const { data: docs } = await api.get(`/agents/${id}/documents`)
      setDocuments(docs)
      
      // Enable RAG if not already enabled
      if (!formData.rag_enabled) {
        setFormData(prev => ({ ...prev, rag_enabled: true }))
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to scrape website')
    } finally {
      setUploading(false)
    }
  }

  const handleDeleteDocument = async (docId: number) => {
    if (!confirm('Delete this document?')) return

    try {
      await api.delete(`/agents/${id}/documents/${docId}`)
      toast.success('Document deleted')
      setDocuments(docs => docs.filter(d => d.id !== docId))
    } catch (err: any) {
      toast.error('Failed to delete document')
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

              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  name="rag_enabled"
                  checked={formData.rag_enabled}
                  onChange={handleChange}
                  className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  Enable Knowledge Base (RAG)
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

        {/* Knowledge Base Section */}
        {isEdit && formData.rag_enabled && (
          <div className="mt-8 border-t border-gray-200 dark:border-gray-700/60 pt-8">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              📚 Knowledge Base
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
              Upload PDFs or add websites to give your agent knowledge for answering questions.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              {/* PDF Upload */}
              <div className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-6 text-center hover:border-primary-400 dark:hover:border-primary-500 transition">
                <CloudArrowUpIcon className="w-10 h-10 text-gray-400 mx-auto mb-3" />
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                  Upload PDF Document
                </p>
                <label className="cursor-pointer">
                  <input
                    type="file"
                    accept=".pdf"
                    onChange={handleFileUpload}
                    className="hidden"
                    disabled={uploading}
                  />
                  <span className="inline-block px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white text-sm font-medium rounded-lg transition disabled:opacity-50">
                    {uploading ? 'Uploading...' : 'Choose PDF'}
                  </span>
                </label>
                <p className="text-xs text-gray-500 dark:text-gray-500 mt-2">Max 10MB</p>
              </div>

              {/* Website Scraping */}
              <div className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-6 hover:border-primary-400 dark:hover:border-primary-500 transition">
                <DocumentTextIcon className="w-10 h-10 text-gray-400 mx-auto mb-3" />
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                  Scrape Website
                </p>
                <div className="flex gap-2">
                  <input
                    type="url"
                    value={websiteUrl}
                    onChange={(e) => setWebsiteUrl(e.target.value)}
                    placeholder="https://example.com"
                    className="flex-1 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900/60 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-400"
                    disabled={uploading}
                  />
                  <button
                    type="button"
                    onClick={handleWebsiteScrape}
                    disabled={uploading || !websiteUrl}
                    className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white text-sm font-medium rounded-lg transition disabled:opacity-50"
                  >
                    Add
                  </button>
                </div>
              </div>
            </div>

            {/* Documents List */}
            {documents.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                  Uploaded Knowledge ({documents.length})
                </h4>
                {documents.map((doc) => (
                  <div
                    key={doc.id}
                    className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700"
                  >
                    <div className="flex items-center gap-3 flex-1">
                      {doc.source_type === 'website' ? '🌐' : '📄'}
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                          {doc.original_filename}
                        </p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          {doc.status === 'completed' && `${doc.total_chunks} chunks`}
                          {doc.status === 'processing' && 'Processing...'}
                          {doc.status === 'failed' && 'Failed'}
                        </p>
                      </div>
                      {doc.status === 'completed' && (
                        <CheckCircleIcon className="w-5 h-5 text-green-500 flex-shrink-0" />
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => handleDeleteDocument(doc.id)}
                      className="ml-3 p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition"
                    >
                      <TrashIcon className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {documents.length === 0 && (
              <div className="text-center py-8 text-gray-500 dark:text-gray-400 text-sm">
                No documents added yet. Upload a PDF or add a website above.
              </div>
            )}
          </div>
        )}

        {!isEdit && formData.rag_enabled && (
          <div className="mt-8 border-t border-gray-200 dark:border-gray-700/60 pt-8">
            <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
              <p className="text-sm text-blue-800 dark:text-blue-300">
                💡 <strong>Tip:</strong> Save the agent first, then you can upload PDFs and add websites to the knowledge base.
              </p>
            </div>
          </div>
        )}

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
