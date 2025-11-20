import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useParams, useSearchParams, Link } from 'react-router-dom'
import { useTranslation } from '@/lib/translations'
import { 
  ArrowLeftIcon, 
  CloudArrowUpIcon, 
  DocumentTextIcon,
  TrashIcon,
  CheckCircleIcon,
  UserPlusIcon,
  XMarkIcon
} from '@heroicons/react/24/outline'
import DashboardLayout from '@/layouts/DashboardLayout'
import { agentsAPI, api, librariesAPI } from '@/lib/api'
import toast from 'react-hot-toast'

interface AgentFormData {
  name: string
  description: string
  language: string
  voice_gender: string
  system_prompt: string
  greeting?: string
  email_request_enabled?: boolean
  email_request_message?: string
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
  const [searchParams] = useSearchParams()
  const t = useTranslation()
  const isEdit = Boolean(id)
  const libraryId = searchParams.get('library')

  const [formData, setFormData] = useState<AgentFormData>({
    name: '',
    description: '',
    language: 'fr-FR',
    voice_gender: 'male',
    system_prompt: '',
    greeting: '',
    email_request_enabled: false,
    email_request_message: 'Pourriez-vous nous communiquer votre adresse électronique afin que nous puissions procéder aux prochaines étapes et prendre les mesures nécessaires ?',
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
  
  // Collaborators state
  const [collaborators, setCollaborators] = useState<any[]>([])
  const [loadingCollaborators, setLoadingCollaborators] = useState(false)
  const [collaboratorEmail, setCollaboratorEmail] = useState('')
  const [collaboratorPermissions, setCollaboratorPermissions] = useState('view,edit')
  const [userPermissions, setUserPermissions] = useState<any>(null)

  const loadCollaborators = useCallback(async (agentId: number) => {
    try {
      setLoadingCollaborators(true)
      const { data } = await api.get(`/agents/${agentId}/collaborators`)
      setCollaborators(data)
    } catch (err: any) {
      console.error('Failed to load collaborators:', err)
    } finally {
      setLoadingCollaborators(false)
    }
  }, [])

  const loadAgent = useCallback(async (agentId: number) => {
    try {
      const { data: agent } = await agentsAPI.get(agentId)
      setFormData({
        name: agent.name,
        description: agent.description || '',
        language: agent.language || 'fr-FR',
        voice_gender: agent.voice_gender || 'male',
        system_prompt: agent.system_prompt || '',
        greeting: agent.greeting || '',
        email_request_enabled: agent.email_request_enabled ?? false,
        email_request_message: agent.email_request_message || 'Pourriez-vous nous communiquer votre adresse électronique afin que nous puissions procéder aux prochaines étapes et prendre les mesures nécessaires ?',
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
      
      // Load user permissions and collaborators if user can manage
      try {
        const { data: perms } = await api.get(`/agents/${agentId}/my-permissions`)
        setUserPermissions(perms)
        
        // Load collaborators if user can manage them
        if (perms.is_owner || (perms.permissions && perms.permissions.includes('manage_collaborators'))) {
          await loadCollaborators(agentId)
        }
      } catch (err) {
        console.log('Could not load permissions')
      }
    } catch (err) {
      toast.error('Failed to load agent.')
      navigate('/dashboard/agents')
    } finally {
      setLoadingAgent(false)
    }
  }, [navigate, loadCollaborators])

  useEffect(() => {
    if (isEdit && id) {
      loadAgent(parseInt(id))
    } else if (libraryId) {
      // Load library template when creating new agent from library
      loadLibrary(parseInt(libraryId))
    }
  }, [isEdit, id, libraryId, loadAgent])

  const loadLibrary = async (libId: number) => {
    try {
      setLoadingAgent(true)
      const { data: library } = await librariesAPI.get(libId)
      setFormData({
        name: library.name,
        description: library.description || '',
        language: library.language || 'fr-FR',
        voice_gender: library.voice_gender || 'male',
        system_prompt: library.system_prompt || '',
        greeting: library.greeting || '',
        email_request_enabled: library.email_request_enabled ?? false,
        email_request_message: library.email_request_message || 'Pourriez-vous nous communiquer votre adresse électronique afin que nous puissions procéder aux prochaines étapes et prendre les mesures nécessaires ?',
        is_public: false,
        is_active: true,
        rag_enabled: library.rag_enabled ?? false
      })
      toast.success(`Loaded template: ${library.name}`)
    } catch (error) {
      console.error('Failed to load library:', error)
      toast.error('Failed to load library template')
    } finally {
      setLoadingAgent(false)
    }
  }

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
        toast.success(t.agentForm.agentUpdated)
      } else {
        await agentsAPI.create(formData)
        toast.success(t.agentForm.agentCreated)
        
        // If created from library, increment usage count
        if (libraryId) {
          try {
            const { data: library } = await librariesAPI.get(Number(libraryId))
            await librariesAPI.update(Number(libraryId), {
              usage_count: (library.usage_count || 0) + 1
            })
          } catch (e) {
            // Ignore if update fails - not critical
            console.log('Could not update library usage count:', e)
          }
        }
      }
      navigate('/dashboard/agents')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || (isEdit ? t.agentForm.agentUpdateError : t.agentForm.agentCreateError))
    } finally {
      setLoading(false)
    }
  }

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    if (!id) {
      toast.error(t.agentForm.saveAgentFirst)
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
      const uploadFormData = new FormData()
      uploadFormData.append('file', file)

      await api.post(`/agents/${id}/documents`, uploadFormData, {
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

  const handleAddCollaborator = async () => {
    if (!id || !collaboratorEmail) return
    
    try {
      await api.post(`/agents/${id}/collaborators`, {
        email: collaboratorEmail,
        permissions: collaboratorPermissions
      })
      toast.success(t.common.status === 'Statut' ? 'Collaborateur ajouté' : 'Collaborator added')
      setCollaboratorEmail('')
      setCollaboratorPermissions('view,edit')
      if (id) {
        await loadCollaborators(parseInt(id))
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to add collaborator')
    }
  }

  const handleRemoveCollaborator = async (collaboratorId: number) => {
    if (!id || !confirm(t.common.status === 'Statut' ? 'Retirer ce collaborateur ?' : 'Remove this collaborator?')) return
    
    try {
      await api.delete(`/agents/${id}/collaborators/${collaboratorId}`)
      toast.success(t.common.status === 'Statut' ? 'Collaborateur retiré' : 'Collaborator removed')
      if (id) {
        await loadCollaborators(parseInt(id))
      }
    } catch (err: any) {
      toast.error('Failed to remove collaborator')
    }
  }

  const handleUpdateCollaboratorPermissions = async (collaboratorId: number, permissions: string) => {
    if (!id) return
    
    try {
      await api.put(`/agents/${id}/collaborators/${collaboratorId}`, {
        permissions: permissions
      })
      toast.success(t.common.status === 'Statut' ? 'Permissions mises à jour' : 'Permissions updated')
      if (id) {
        await loadCollaborators(parseInt(id))
      }
    } catch (err: any) {
      toast.error('Failed to update permissions')
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
            {t.agentForm.backToAgents}
          </Link>
          <h1 className="mt-2 text-3xl font-semibold text-gray-900 dark:text-white tracking-tight">
            {isEdit ? t.agentForm.editAgent : t.agentForm.createNewAgent}
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {t.agentForm.configureDetails}
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
                {t.agentForm.agentName}
              </label>
              <input
                id="name"
                name="name"
                required
                value={formData.name}
                onChange={handleChange}
                placeholder={t.agentForm.agentNamePlaceholder}
                className="mt-1 w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white/80 dark:bg-gray-900/60 px-3 py-2 text-sm text-gray-900 dark:text-white shadow-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-400 focus:ring-offset-0 transition-all"
              />
            </div>

            {/* Description */}
            <div>
              <label htmlFor="description" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                {t.agentForm.description}
              </label>
              <textarea
                id="description"
                name="description"
                rows={3}
                value={formData.description}
                onChange={handleChange}
                placeholder={t.agentForm.descriptionPlaceholder}
                className="mt-1 w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white/80 dark:bg-gray-900/60 px-3 py-2 text-sm text-gray-900 dark:text-white shadow-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-400 focus:ring-offset-0 transition-all resize-none"
              />
            </div>

            {/* Greeting */}
            <div>
              <label htmlFor="greeting" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                {t.agentForm.greeting}
              </label>
              <textarea
                id="greeting"
                name="greeting"
                rows={2}
                value={formData.greeting}
                onChange={handleChange}
                placeholder={t.agentForm.greetingPlaceholder}
                className="mt-1 w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white/80 dark:bg-gray-900/60 px-3 py-2 text-sm text-gray-900 dark:text-white shadow-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-400 focus:ring-offset-0 transition-all resize-none"
              />
              <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                {t.agentForm.greetingPlaceholder.includes('Bonjour') ? 'Premier message que l\'agent dira au début d\'une conversation.' : 'First message the agent will say when starting a conversation.'}
              </p>
            </div>

            {/* Email Request */}
            <div className="space-y-3">
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  name="email_request_enabled"
                  checked={formData.email_request_enabled}
                  onChange={handleChange}
                  className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  {t.common.status === 'Statut' ? 'Demander l\'adresse email après le message d\'accueil' : 'Request email address after greeting'}
                </span>
              </label>
              
              {formData.email_request_enabled && (
                <div>
                  <label htmlFor="email_request_message" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                    {t.common.status === 'Statut' ? 'Message de demande d\'email' : 'Email request message'}
                  </label>
                  <textarea
                    id="email_request_message"
                    name="email_request_message"
                    rows={2}
                    value={formData.email_request_message}
                    onChange={handleChange}
                    placeholder="Pourriez-vous nous communiquer votre adresse électronique afin que nous puissions procéder aux prochaines étapes et prendre les mesures nécessaires ?"
                    className="mt-1 w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white/80 dark:bg-gray-900/60 px-3 py-2 text-sm text-gray-900 dark:text-white shadow-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-400 focus:ring-offset-0 transition-all resize-none"
                  />
                  <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                    {t.common.status === 'Statut' ? 'Message qui sera dit après le message d\'accueil pour demander l\'adresse email.' : 'Message that will be said after the greeting to request the email address.'}
                  </p>
                </div>
              )}
            </div>

            {/* Language */}
            <div>
              <label htmlFor="language" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                {t.agentForm.language} *
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

            {/* Voice Gender */}
            <div>
              <label htmlFor="voice_gender" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                {t.agentForm.voiceGender} *
              </label>
              <select
                id="voice_gender"
                name="voice_gender"
                required
                value={formData.voice_gender}
                onChange={handleChange}
                className="mt-1 w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white/80 dark:bg-gray-900/60 px-3 py-2 text-sm text-gray-900 dark:text-white shadow-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-400 focus:ring-offset-0 transition-all"
              >
                <option value="male">🗣️ Male (Charon - Deep voice)</option>
                <option value="female">👤 Female (Kore - Soft voice)</option>
                <option value="neutral">🎙️ Neutral (Puck - Standard voice)</option>
              </select>
              <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                Note: All voices have a slight English accent. This is a limitation of Gemini 2.5 Flash.
              </p>
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
                  {t.agentForm.isActive} {t.common.status === 'Statut' ? '(peut recevoir des appels)' : '(can receive calls)'}
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
                  {t.agentForm.isPublic} {t.common.status === 'Statut' ? '(sans authentification)' : '(no authentication)'}
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
                  {t.agentForm.ragEnabled}
                </span>
              </label>
            </div>
          </div>

          {/* RIGHT COLUMN */}
          <div>
            <label htmlFor="system_prompt" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
              {t.agentForm.systemPrompt} *
            </label>
            <textarea
              id="system_prompt"
              name="system_prompt"
              required
              rows={14}
              value={formData.system_prompt}
              onChange={handleChange}
              className="mt-1 w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white/80 dark:bg-gray-900/60 px-3 py-2 font-mono text-sm text-gray-900 dark:text-white shadow-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-400 focus:ring-offset-0 transition-all resize-none"
              placeholder={t.agentForm.systemPromptPlaceholder}
            />
            <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
              {t.common.status === 'Statut' ? 'Définit le ton, le contexte et le comportement de l\'assistant.' : 'Defines the assistant\'s tone, context, and behavior.'}
            </p>
          </div>
        </div>

        {/* Knowledge Base Section */}
        {isEdit && formData.rag_enabled && (
          <div className="mt-8 border-t border-gray-200 dark:border-gray-700/60 pt-8">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              📚 {t.agentForm.ragEnabled}
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
              {t.common.status === 'Statut' ? 'Téléchargez des PDF ou ajoutez des sites web pour donner des connaissances à votre agent pour répondre aux questions.' : 'Upload PDFs or add websites to give your agent knowledge for answering questions.'}
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              {/* PDF Upload */}
              <div className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-6 text-center hover:border-primary-400 dark:hover:border-primary-500 transition">
                <CloudArrowUpIcon className="w-10 h-10 text-gray-400 mx-auto mb-3" />
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                  {t.agentForm.uploadDocument}
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
                    {uploading ? (t.common.status === 'Statut' ? 'Téléchargement...' : 'Uploading...') : (t.common.status === 'Statut' ? 'Choisir PDF' : 'Choose PDF')}
                  </span>
                </label>
                <p className="text-xs text-gray-500 dark:text-gray-500 mt-2">Max 10MB</p>
              </div>

              {/* Website Scraping */}
              <div className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-6 hover:border-primary-400 dark:hover:border-primary-500 transition">
                <DocumentTextIcon className="w-10 h-10 text-gray-400 mx-auto mb-3" />
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                  {t.agentForm.addWebsite}
                </p>
                <div className="flex gap-2">
                  <input
                    type="url"
                    value={websiteUrl}
                    onChange={(e) => setWebsiteUrl(e.target.value)}
                    placeholder={t.agentForm.websiteUrl}
                    className="flex-1 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900/60 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-400"
                    disabled={uploading}
                  />
                  <button
                    type="button"
                    onClick={handleWebsiteScrape}
                    disabled={uploading || !websiteUrl}
                    className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white text-sm font-medium rounded-lg transition disabled:opacity-50"
                  >
                    {t.common.status === 'Statut' ? 'Ajouter' : 'Add'}
                  </button>
                </div>
              </div>
            </div>

            {/* Documents List */}
            {documents.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                  {t.agentForm.documents} ({documents.length})
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
                          {doc.status === 'completed' && `${doc.total_chunks} ${t.common.status === 'Statut' ? 'morceaux' : 'chunks'}`}
                          {doc.status === 'processing' && t.agentForm.processing}
                          {doc.status === 'failed' && t.agentForm.failed}
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
                      title={t.agentForm.deleteDocument}
                    >
                      <TrashIcon className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {documents.length === 0 && (
              <div className="text-center py-8 text-gray-500 dark:text-gray-400 text-sm">
                {t.agentForm.noDocuments} {t.common.status === 'Statut' ? 'Téléchargez un PDF ou ajoutez un site web ci-dessus.' : 'Upload a PDF or add a website above.'}
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

        {/* Collaborators Section */}
        {isEdit && id && userPermissions && (userPermissions.is_owner || userPermissions.permissions.includes('manage_collaborators')) && (
          <div className="mt-8 border-t border-gray-200 dark:border-gray-700/60 pt-8">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              👥 {t.common.status === 'Statut' ? 'Collaborateurs' : 'Collaborators'}
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
              {t.common.status === 'Statut' ? 'Invitez d\'autres utilisateurs à collaborer sur cet agent avec des permissions spécifiques.' : 'Invite other users to collaborate on this agent with specific permissions.'}
            </p>

            {/* Add Collaborator */}
            <div className="mb-6 p-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
              <div className="flex gap-3 mb-3">
                <input
                  type="email"
                  value={collaboratorEmail}
                  onChange={(e) => setCollaboratorEmail(e.target.value)}
                  placeholder={t.common.status === 'Statut' ? 'Email du collaborateur' : 'Collaborator email'}
                  className="flex-1 px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700 text-sm"
                />
                <select
                  value={collaboratorPermissions}
                  onChange={(e) => setCollaboratorPermissions(e.target.value)}
                  className="px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700 text-sm"
                >
                  <option value="view">{t.common.status === 'Statut' ? 'Voir uniquement' : 'View only'}</option>
                  <option value="view,edit">{t.common.status === 'Statut' ? 'Voir et modifier' : 'View and Edit'}</option>
                  <option value="view,edit,delete">{t.common.status === 'Statut' ? 'Voir, modifier et supprimer' : 'View, Edit and Delete'}</option>
                  <option value="view,edit,delete,manage_collaborators">{t.common.status === 'Statut' ? 'Toutes les permissions' : 'All permissions'}</option>
                </select>
                <button
                  type="button"
                  onClick={handleAddCollaborator}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg text-sm font-medium transition"
                >
                  <UserPlusIcon className="w-4 h-4" />
                  {t.common.status === 'Statut' ? 'Ajouter' : 'Add'}
                </button>
              </div>
            </div>

            {/* Collaborators List */}
            {loadingCollaborators ? (
              <div className="text-center py-4 text-gray-500 dark:text-gray-400 text-sm">
                {t.common.status === 'Statut' ? 'Chargement...' : 'Loading...'}
              </div>
            ) : collaborators.length > 0 ? (
              <div className="space-y-2">
                {collaborators.map((collab) => (
                  <div
                    key={collab.id}
                    className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700"
                  >
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-900 dark:text-white">
                        {collab.user_name} ({collab.user_email})
                      </p>
                      <div className="flex items-center gap-2 mt-1">
                        <select
                          value={collab.permissions}
                          onChange={(e) => handleUpdateCollaboratorPermissions(collab.id, e.target.value)}
                          className="text-xs px-2 py-1 border rounded dark:bg-gray-800 dark:border-gray-700"
                        >
                          <option value="view">{t.common.status === 'Statut' ? 'Voir' : 'View'}</option>
                          <option value="view,edit">{t.common.status === 'Statut' ? 'Voir + Modifier' : 'View + Edit'}</option>
                          <option value="view,edit,delete">{t.common.status === 'Statut' ? 'Voir + Modifier + Supprimer' : 'View + Edit + Delete'}</option>
                          <option value="view,edit,delete,manage_collaborators">{t.common.status === 'Statut' ? 'Toutes' : 'All'}</option>
                        </select>
                        {!collab.is_active && (
                          <span className="text-xs text-gray-500 dark:text-gray-400">
                            ({t.common.status === 'Statut' ? 'Inactif' : 'Inactive'})
                          </span>
                        )}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemoveCollaborator(collab.id)}
                      className="ml-3 p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition"
                      title={t.common.status === 'Statut' ? 'Retirer' : 'Remove'}
                    >
                      <XMarkIcon className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500 dark:text-gray-400 text-sm">
                {t.common.status === 'Statut' ? 'Aucun collaborateur. Ajoutez-en un ci-dessus.' : 'No collaborators. Add one above.'}
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="mt-10 flex justify-end gap-3 border-t border-gray-200 dark:border-gray-700/60 pt-6">
          <Link
            to="/dashboard/agents"
            className="inline-flex items-center justify-center rounded-lg border border-gray-300 dark:border-gray-600 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700/40 transition"
          >
            {t.common.cancel}
          </Link>
          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center justify-center rounded-lg bg-gradient-to-r from-primary-600 to-primary-500 hover:from-primary-700 hover:to-primary-600 text-white px-5 py-2 text-sm font-medium shadow-md transition disabled:opacity-70"
          >
            {loading ? (t.common.status === 'Statut' ? 'Enregistrement...' : 'Saving...') : isEdit ? t.agentForm.editAgent : t.agentForm.createNewAgent}
          </button>
        </div>
      </form>
    </DashboardLayout>
  )
}
