import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { 
  BookOpenIcon, 
  StarIcon, 
  MagnifyingGlassIcon, 
  XMarkIcon,
  FunnelIcon,
  PlusIcon,
  PencilIcon,
  TrashIcon,
  ArrowPathIcon,
  CheckIcon,
  MicrophoneIcon
} from '@heroicons/react/24/outline'
import { StarIcon as StarIconSolid } from '@heroicons/react/24/solid'
import DashboardLayout from '@/layouts/DashboardLayout'
import { librariesAPI, agentsAPI } from '@/lib/api'
import { useAuthStore } from '@/store/authStore'
import toast from 'react-hot-toast'
import { useTranslation } from '@/lib/translations'

interface AgentLibrary {
  id: number
  user_id: number | null
  is_public: boolean
  name: string
  description: string | null
  category: string
  tags: string[]
  icon: string | null
  language: string
  system_prompt: string
  greeting: string | null
  voice_id: string
  voice_gender: string
  agent_config: any
  tools_enabled: string[]
  model_name: string
  temperature: string
  max_tokens: number
  rag_enabled: boolean
  rag_config: any
  crm_enabled: boolean
  crm_config: any
  usage_count: number
  saved_count: number
  is_active: boolean
  created_at: string
  updated_at: string
  created_by_user_id: number | null
  can_edit: boolean
  can_delete: boolean
}

// Category labels will be translated using useTranslation hook

const CATEGORY_COLORS: Record<string, string> = {
  real_estate: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  customer_service: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  sales: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
  support: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
  marketing: 'bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-200',
  hr: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200',
  healthcare: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
  education: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  finance: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200',
  legal: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200',
  general: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200',
}

export default function LibrariesPage() {
  const t = useTranslation()
  const [activeTab, setActiveTab] = useState<'public' | 'my'>('public')
  const [libraries, setLibraries] = useState<AgentLibrary[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [categories, setCategories] = useState<string[]>([])
  const [savingLibraryId, setSavingLibraryId] = useState<number | null>(null)
  const [deletingLibraryId, setDeletingLibraryId] = useState<number | null>(null)
  const [useTemplateModal, setUseTemplateModal] = useState<AgentLibrary | null>(null)
  const [editModal, setEditModal] = useState<AgentLibrary | null>(null)
  const [agents, setAgents] = useState<any[]>([])
  const [loadingAgents, setLoadingAgents] = useState(false)
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null)
  const [editFormData, setEditFormData] = useState<Partial<AgentLibrary>>({})
  const [savingEdit, setSavingEdit] = useState(false)
  const [createModal, setCreateModal] = useState(false)
  const [createFormData, setCreateFormData] = useState<Partial<AgentLibrary>>({
    name: '',
    description: '',
    system_prompt: '',
    greeting: '',
    voice_id: 'Charon',
    voice_gender: 'male',
    language: 'fr-FR',
    category: 'general',
    is_public: true,
  })
  const [savingCreate, setSavingCreate] = useState(false)
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const isAdmin = user?.is_superuser || false

  const CATEGORY_LABELS: Record<string, string> = {
    real_estate: t.categories.realEstate,
    customer_service: t.categories.customerService,
    sales: t.categories.sales,
    support: t.categories.support,
    marketing: t.categories.marketing,
    hr: t.categories.hr,
    healthcare: t.categories.healthcare,
    education: t.categories.education,
    finance: t.categories.finance,
    legal: t.categories.legal,
    general: t.categories.general,
  }

  useEffect(() => {
    loadCategories()
  }, [])

  useEffect(() => {
    loadLibraries()
  }, [activeTab, selectedCategory, searchQuery])

  useEffect(() => {
    if (useTemplateModal) {
      loadAgents()
    }
  }, [useTemplateModal])

  const loadCategories = async () => {
    try {
      const response = await librariesAPI.listCategories()
      setCategories(response.data)
    } catch (error) {
      console.error('Failed to load categories:', error)
    }
  }

  const loadLibraries = async () => {
    try {
      setLoading(true)
      const params: any = {}
      if (selectedCategory !== 'all') {
        params.category = selectedCategory
      }
      if (searchQuery.trim()) {
        params.search = searchQuery.trim()
      }

      const response = activeTab === 'public'
        ? await librariesAPI.listPublic(params)
        : await librariesAPI.listMy(params)
      
      setLibraries(response.data)
    } catch (error) {
      console.error('Failed to load libraries:', error)
      toast.error('Failed to load libraries')
    } finally {
      setLoading(false)
    }
  }

  const handleSaveLibrary = async (libraryId: number) => {
    try {
      setSavingLibraryId(libraryId)
      await librariesAPI.save(libraryId)
      toast.success('Library saved to your collection')
      // Reload my libraries if on that tab
      if (activeTab === 'my') {
        loadLibraries()
      }
    } catch (error: any) {
      console.error('Failed to save library:', error)
      toast.error(error?.response?.data?.detail || 'Failed to save library')
    } finally {
      setSavingLibraryId(null)
    }
  }

  const handleDeleteLibrary = async (libraryId: number) => {
    if (!confirm('Are you sure you want to delete this library?')) return
    
    try {
      setDeletingLibraryId(libraryId)
      await librariesAPI.delete(libraryId)
      toast.success('Library deleted successfully')
      loadLibraries()
    } catch (error: any) {
      console.error('Failed to delete library:', error)
      toast.error(error?.response?.data?.detail || 'Failed to delete library')
    } finally {
      setDeletingLibraryId(null)
    }
  }

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearchQuery(searchInput)
    }, 500)
    
    return () => clearTimeout(timer)
  }, [searchInput])

  const handleSearchClear = () => {
    setSearchInput('')
    setSearchQuery('')
  }

  const loadAgents = async () => {
    try {
      setLoadingAgents(true)
      const response = await agentsAPI.list()
      setAgents(response.data)
    } catch (error) {
      console.error('Failed to load agents:', error)
      toast.error('Failed to load agents')
    } finally {
      setLoadingAgents(false)
    }
  }

  const handleUseTemplate = (library: AgentLibrary) => {
    setUseTemplateModal(library)
    setSelectedAgentId(null)
  }

  const handleApplyToAgent = async () => {
    if (!useTemplateModal) return

    if (!selectedAgentId) {
      // Create new agent
      navigate(`/dashboard/agents/new?library=${useTemplateModal.id}`)
      setUseTemplateModal(null)
      return
    }

    // Apply template to existing agent
    try {
      const agent = agents.find(a => a.id === selectedAgentId)
      if (!agent) return

      // Update agent with library's system prompt and settings
      await agentsAPI.update(selectedAgentId, {
        system_prompt: useTemplateModal.system_prompt,
        greeting: useTemplateModal.greeting || agent.greeting,
        voice_id: useTemplateModal.voice_id,
        voice_gender: useTemplateModal.voice_gender,
        language: useTemplateModal.language,
      })

      // Increment usage count on the library
      try {
        await librariesAPI.update(useTemplateModal.id, {
          usage_count: (useTemplateModal.usage_count || 0) + 1
        })
      } catch (e) {
        // Ignore if update fails - not critical
        console.log('Could not update library usage count:', e)
      }

      toast.success(`Template applied to ${agent.name}`)
      setUseTemplateModal(null)
      navigate(`/dashboard/agents/${selectedAgentId}/edit`)
    } catch (error: any) {
      console.error('Failed to apply template:', error)
      toast.error(error?.response?.data?.detail || 'Failed to apply template')
    }
  }

  const handleEditLibrary = (library: AgentLibrary) => {
    setEditModal(library)
    setEditFormData({
      name: library.name,
      description: library.description || '',
      system_prompt: library.system_prompt,
      greeting: library.greeting || '',
      voice_id: library.voice_id,
      voice_gender: library.voice_gender,
      language: library.language,
    })
  }

  const handleSaveEdit = async () => {
    if (!editModal) return

    try {
      setSavingEdit(true)
      await librariesAPI.update(editModal.id, editFormData)
      toast.success('Library updated successfully')
      setEditModal(null)
      loadLibraries()
    } catch (error: any) {
      console.error('Failed to update library:', error)
      toast.error(error?.response?.data?.detail || 'Failed to update library')
    } finally {
      setSavingEdit(false)
    }
  }

  const handleCreateLibrary = async () => {
    if (!createFormData.name || !createFormData.system_prompt) {
      toast.error('Name and System Prompt are required')
      return
    }

    try {
      setSavingCreate(true)
      await librariesAPI.create({
        ...createFormData,
        is_public: true,
      } as any)
      toast.success('Public library created successfully')
      setCreateModal(false)
      setCreateFormData({
        name: '',
        description: '',
        system_prompt: '',
        greeting: '',
        voice_id: 'Charon',
        voice_gender: 'male',
        language: 'fr-FR',
        category: 'general',
        is_public: true,
      })
      loadLibraries()
    } catch (error: any) {
      console.error('Failed to create library:', error)
      toast.error(error?.response?.data?.detail || 'Failed to create library')
    } finally {
      setSavingCreate(false)
    }
  }

  return (
    <DashboardLayout>
      <div className="mb-8">
        {/* Header */}
        <div className="mb-6 flex justify-between items-start">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white mb-1">
              {t.libraries.title}
            </h1>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              {t.libraries.subtitle}
            </p>
          </div>
          {isAdmin && activeTab === 'public' && (
            <button
              onClick={() => setCreateModal(true)}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
            >
              <PlusIcon className="h-5 w-5" />
              {t.libraries.createPublicLibrary}
            </button>
          )}
        </div>

        {/* Tabs */}
        <div className="flex gap-2 bg-gray-100 dark:bg-gray-800 p-1 rounded-lg border border-gray-200 dark:border-gray-700 w-fit mb-6">
          <button
            onClick={() => setActiveTab('public')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'public'
                ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
            }`}
          >
            <BookOpenIcon className="h-4 w-4 inline mr-2" />
            {t.libraries.publicLibraries}
          </button>
          <button
            onClick={() => setActiveTab('my')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'my'
                ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
            }`}
          >
            <StarIconSolid className="h-4 w-4 inline mr-2" />
            {t.libraries.myLibraries}
          </button>
        </div>

        {/* Search and Filters */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4 shadow-sm mb-6">
          <div className="flex flex-col sm:flex-row gap-4">
            {/* Search */}
            <div className="flex-1">
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <MagnifyingGlassIcon className="h-5 w-5 text-gray-400" />
                </div>
                <input
                  type="text"
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  placeholder={t.libraries.searchPlaceholder}
                  className="w-full pl-10 pr-10 py-2.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                {searchInput && (
                  <button
                    onClick={handleSearchClear}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center"
                  >
                    <XMarkIcon className="h-5 w-5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300" />
                  </button>
                )}
              </div>
            </div>

            {/* Category Filter */}
            <div className="sm:w-64">
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <FunnelIcon className="h-5 w-5 text-gray-400" />
                </div>
                <select
                  value={selectedCategory}
                  onChange={(e) => setSelectedCategory(e.target.value)}
                  className="w-full pl-10 pr-8 py-2.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent appearance-none cursor-pointer"
                >
                  <option value="all">{t.libraries.allCategories}</option>
                  {categories.map((cat) => (
                    <option key={cat} value={cat}>
                      {CATEGORY_LABELS[cat] || cat}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* Libraries Grid */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3].map((i) => (
              <div key={i} className="card animate-pulse">
                <div className="h-48 bg-gray-200 dark:bg-gray-700 rounded"></div>
              </div>
            ))}
          </div>
        ) : libraries.length === 0 ? (
          <div className="card text-center py-12">
            <BookOpenIcon className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-semibold text-gray-900 dark:text-white">
              No libraries found
            </h3>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              {activeTab === 'public'
                ? 'No public libraries match your search criteria.'
                : "You haven't saved any libraries yet. Browse public libraries to get started."}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {libraries.map((library) => (
              <div
                key={library.id}
                className="card hover:shadow-lg transition-shadow"
              >
                {/* Header */}
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-start gap-3 flex-1">
                    {library.icon && (
                      <div className="text-3xl flex-shrink-0">{library.icon}</div>
                    )}
                    <div className="flex-1 min-w-0">
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">
                        {library.name}
                      </h3>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${CATEGORY_COLORS[library.category] || CATEGORY_COLORS.general}`}>
                          {CATEGORY_LABELS[library.category] || library.category}
                        </span>
                        {library.is_public && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                            Public
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Description */}
                {library.description && (
                  <p className="text-sm text-gray-600 dark:text-gray-300 mb-4 line-clamp-2">
                    {library.description}
                  </p>
                )}

                {/* Tags */}
                {library.tags && library.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-4">
                    {library.tags.slice(0, 3).map((tag, idx) => (
                      <span
                        key={idx}
                        className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300"
                      >
                        {tag}
                      </span>
                    ))}
                    {library.tags.length > 3 && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium text-gray-500 dark:text-gray-400">
                        +{library.tags.length - 3}
                      </span>
                    )}
                  </div>
                )}

                {/* Stats */}
                <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400 mb-4">
                  <span>👥 {library.usage_count || 0} uses</span>
                  {library.is_public && (
                    <span>⭐ {library.saved_count || 0} saved</span>
                  )}
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 pt-4 border-t border-gray-200 dark:border-gray-700">
                  {activeTab === 'public' ? (
                    <>
                      {!isAdmin ? (
                        <button
                          onClick={() => handleSaveLibrary(library.id)}
                          disabled={savingLibraryId === library.id}
                          className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white rounded-md text-sm font-medium transition-colors flex items-center justify-center gap-2"
                        >
                          {savingLibraryId === library.id ? (
                            <>
                              <ArrowPathIcon className="h-4 w-4 animate-spin" />
                              Saving...
                            </>
                          ) : (
                            <>
                              <StarIcon className="h-4 w-4" />
                              Save to My Libraries
                            </>
                          )}
                        </button>
                      ) : (
                        <>
                          <button
                            onClick={() => handleUseTemplate(library)}
                            className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium transition-colors flex items-center justify-center gap-2"
                          >
                            <PlusIcon className="h-4 w-4" />
                            Use Template
                          </button>
                          {library.can_edit && (
                            <button
                              onClick={() => handleEditLibrary(library)}
                              className="px-3 py-2 bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 rounded-md text-sm font-medium transition-colors"
                              title="Edit library"
                            >
                              <PencilIcon className="h-4 w-4" />
                            </button>
                          )}
                          {library.can_delete && (
                            <button
                              onClick={() => handleDeleteLibrary(library.id)}
                              disabled={deletingLibraryId === library.id}
                              className="px-3 py-2 bg-red-600 hover:bg-red-700 disabled:bg-gray-400 text-white rounded-md text-sm font-medium transition-colors"
                              title="Delete library"
                            >
                              {deletingLibraryId === library.id ? (
                                <ArrowPathIcon className="h-4 w-4 animate-spin" />
                              ) : (
                                <TrashIcon className="h-4 w-4" />
                              )}
                            </button>
                          )}
                        </>
                      )}
                    </>
                  ) : (
                    <>
                      <button
                        onClick={() => handleUseTemplate(library)}
                        className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium transition-colors flex items-center justify-center gap-2"
                      >
                        <PlusIcon className="h-4 w-4" />
                        Use Template
                      </button>
                      {library.can_edit && (
                        <button
                          onClick={() => handleEditLibrary(library)}
                          className="px-3 py-2 bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 rounded-md text-sm font-medium transition-colors"
                          title="Edit library"
                        >
                          <PencilIcon className="h-4 w-4" />
                        </button>
                      )}
                      {library.can_delete && (
                        <button
                          onClick={() => handleDeleteLibrary(library.id)}
                          disabled={deletingLibraryId === library.id}
                          className="px-3 py-2 bg-red-600 hover:bg-red-700 disabled:bg-gray-400 text-white rounded-md text-sm font-medium transition-colors"
                          title="Delete library"
                        >
                          {deletingLibraryId === library.id ? (
                            <ArrowPathIcon className="h-4 w-4 animate-spin" />
                          ) : (
                            <TrashIcon className="h-4 w-4" />
                          )}
                        </button>
                      )}
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Use Template Modal */}
      {useTemplateModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-screen items-center justify-center p-4">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={() => setUseTemplateModal(null)} />
            <div className="relative bg-white dark:bg-gray-800 rounded-lg max-w-md w-full p-6 shadow-xl">
              <div className="mb-4">
                <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                  Use Template: {useTemplateModal.name}
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Choose to create a new agent or apply this template to an existing agent
                </p>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Select Option
                  </label>
                  <div className="space-y-2">
                    <label className="flex items-center p-3 border border-gray-300 dark:border-gray-600 rounded-lg cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700">
                      <input
                        type="radio"
                        name="templateOption"
                        value="new"
                        checked={selectedAgentId === null}
                        onChange={() => setSelectedAgentId(null)}
                        className="mr-3"
                      />
                      <div>
                        <div className="font-medium text-gray-900 dark:text-white">Create New Agent</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">Create a new agent with this template</div>
                      </div>
                    </label>
                    <label className="flex items-center p-3 border border-gray-300 dark:border-gray-600 rounded-lg cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700">
                      <input
                        type="radio"
                        name="templateOption"
                        value="existing"
                        checked={selectedAgentId !== null}
                        onChange={() => {
                          if (agents.length > 0 && !selectedAgentId) {
                            setSelectedAgentId(agents[0].id)
                          }
                        }}
                        className="mr-3"
                      />
                      <div className="flex-1">
                        <div className="font-medium text-gray-900 dark:text-white">Apply to Existing Agent</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">Update an existing agent's system prompt</div>
                      </div>
                    </label>
                  </div>
                </div>

                {selectedAgentId !== null && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Select Agent
                    </label>
                    {loadingAgents ? (
                      <div className="p-3 border border-gray-300 dark:border-gray-600 rounded-lg">
                        <div className="animate-pulse text-sm text-gray-500">Loading agents...</div>
                      </div>
                    ) : agents.length === 0 ? (
                      <div className="p-3 border border-gray-300 dark:border-gray-600 rounded-lg text-sm text-gray-500">
                        No agents available. Create a new agent instead.
                      </div>
                    ) : (
                      <select
                        value={selectedAgentId || ''}
                        onChange={(e) => setSelectedAgentId(Number(e.target.value))}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        {agents.map((agent) => (
                          <option key={agent.id} value={agent.id}>
                            {agent.name}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                )}

                <div className="flex items-center gap-2 pt-4 border-t border-gray-200 dark:border-gray-700">
                  <button
                    onClick={() => setUseTemplateModal(null)}
                    className="flex-1 px-4 py-2 bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 rounded-md text-sm font-medium transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleApplyToAgent}
                    disabled={selectedAgentId !== null && (!selectedAgentId || agents.length === 0)}
                    className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white rounded-md text-sm font-medium transition-colors flex items-center justify-center gap-2"
                  >
                    {selectedAgentId === null ? (
                      <>
                        <PlusIcon className="h-4 w-4" />
                        Create New Agent
                      </>
                    ) : (
                      <>
                        <CheckIcon className="h-4 w-4" />
                        Apply to Agent
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Edit Library Modal */}
      {editModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-screen items-center justify-center p-4">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={() => setEditModal(null)} />
            <div className="relative bg-white dark:bg-gray-800 rounded-lg max-w-2xl w-full p-6 shadow-xl max-h-[90vh] overflow-y-auto">
              <div className="mb-6">
                <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                  Edit Library: {editModal.name}
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Update your library template
                </p>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Name *
                  </label>
                  <input
                    type="text"
                    value={editFormData.name || ''}
                    onChange={(e) => setEditFormData({ ...editFormData, name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Description
                  </label>
                  <textarea
                    value={editFormData.description || ''}
                    onChange={(e) => setEditFormData({ ...editFormData, description: e.target.value })}
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    System Prompt *
                  </label>
                  <textarea
                    value={editFormData.system_prompt || ''}
                    onChange={(e) => setEditFormData({ ...editFormData, system_prompt: e.target.value })}
                    rows={10}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Greeting
                  </label>
                  <textarea
                    value={editFormData.greeting || ''}
                    onChange={(e) => setEditFormData({ ...editFormData, greeting: e.target.value })}
                    rows={2}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Voice ID
                    </label>
                    <select
                      value={editFormData.voice_id || 'Charon'}
                      onChange={(e) => setEditFormData({ ...editFormData, voice_id: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="Charon">Charon</option>
                      <option value="Kore">Kore</option>
                      <option value="Puck">Puck</option>
                      <option value="Fenrir">Fenrir</option>
                      <option value="Aoede">Aoede</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Voice Gender
                    </label>
                    <select
                      value={editFormData.voice_gender || 'male'}
                      onChange={(e) => setEditFormData({ ...editFormData, voice_gender: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="male">Male</option>
                      <option value="female">Female</option>
                      <option value="neutral">Neutral</option>
                    </select>
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-4 border-t border-gray-200 dark:border-gray-700">
                  <button
                    onClick={() => setEditModal(null)}
                    className="flex-1 px-4 py-2 bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 rounded-md text-sm font-medium transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSaveEdit}
                    disabled={savingEdit || !editFormData.name || !editFormData.system_prompt}
                    className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white rounded-md text-sm font-medium transition-colors flex items-center justify-center gap-2"
                  >
                    {savingEdit ? (
                      <>
                        <ArrowPathIcon className="h-4 w-4 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      <>
                        <CheckIcon className="h-4 w-4" />
                        Save Changes
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create Library Modal */}
      {createModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-screen items-center justify-center p-4">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={() => setCreateModal(false)} />
            <div className="relative bg-white dark:bg-gray-800 rounded-lg max-w-2xl w-full p-6 shadow-xl max-h-[90vh] overflow-y-auto">
              <div className="mb-6">
                <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                  Create Public Library
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Create a new public library template for all users
                </p>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Name *
                  </label>
                  <input
                    type="text"
                    value={createFormData.name || ''}
                    onChange={(e) => setCreateFormData({ ...createFormData, name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Category
                  </label>
                  <select
                    value={createFormData.category || 'general'}
                    onChange={(e) => setCreateFormData({ ...createFormData, category: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {categories.map((cat) => (
                      <option key={cat} value={cat}>
                        {CATEGORY_LABELS[cat] || cat}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Description
                  </label>
                  <textarea
                    value={createFormData.description || ''}
                    onChange={(e) => setCreateFormData({ ...createFormData, description: e.target.value })}
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    System Prompt *
                  </label>
                  <textarea
                    value={createFormData.system_prompt || ''}
                    onChange={(e) => setCreateFormData({ ...createFormData, system_prompt: e.target.value })}
                    rows={10}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Greeting
                  </label>
                  <textarea
                    value={createFormData.greeting || ''}
                    onChange={(e) => setCreateFormData({ ...createFormData, greeting: e.target.value })}
                    rows={2}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Language
                    </label>
                    <select
                      value={createFormData.language || 'fr-FR'}
                      onChange={(e) => setCreateFormData({ ...createFormData, language: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="fr-FR">French</option>
                      <option value="en-US">English</option>
                      <option value="es-ES">Spanish</option>
                      <option value="de-DE">German</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Voice ID
                    </label>
                    <select
                      value={createFormData.voice_id || 'Charon'}
                      onChange={(e) => setCreateFormData({ ...createFormData, voice_id: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="Charon">Charon</option>
                      <option value="Kore">Kore</option>
                      <option value="Puck">Puck</option>
                      <option value="Fenrir">Fenrir</option>
                      <option value="Aoede">Aoede</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Voice Gender
                    </label>
                    <select
                      value={createFormData.voice_gender || 'male'}
                      onChange={(e) => setCreateFormData({ ...createFormData, voice_gender: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="male">Male</option>
                      <option value="female">Female</option>
                      <option value="neutral">Neutral</option>
                    </select>
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-4 border-t border-gray-200 dark:border-gray-700">
                  <button
                    onClick={() => {
                      setCreateModal(false)
                      setCreateFormData({
                        name: '',
                        description: '',
                        system_prompt: '',
                        greeting: '',
                        voice_id: 'Charon',
                        voice_gender: 'male',
                        language: 'fr-FR',
                        category: 'other',
                        is_public: true,
                      })
                    }}
                    className="flex-1 px-4 py-2 bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 rounded-md text-sm font-medium transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleCreateLibrary}
                    disabled={savingCreate || !createFormData.name || !createFormData.system_prompt}
                    className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white rounded-md text-sm font-medium transition-colors flex items-center justify-center gap-2"
                  >
                    {savingCreate ? (
                      <>
                        <ArrowPathIcon className="h-4 w-4 animate-spin" />
                        Creating...
                      </>
                    ) : (
                      <>
                        <CheckIcon className="h-4 w-4" />
                        Create Library
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  )
}

