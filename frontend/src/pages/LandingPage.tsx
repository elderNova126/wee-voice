import { Link } from 'react-router-dom'
import { Menu, Transition } from '@headlessui/react'
import { Fragment, useState, useEffect } from 'react'
import {
  MicrophoneIcon,
  ClockIcon,
  GlobeAltIcon,
  ChartBarIcon,
  PhoneIcon,
  CpuChipIcon,
  CheckIcon,
  RocketLaunchIcon,
  ShieldCheckIcon,
  SunIcon,
  MoonIcon,
  ComputerDesktopIcon,
  ChevronDownIcon,
  UserCircleIcon,
  ArrowRightOnRectangleIcon,
  SparklesIcon,
  ChatBubbleLeftRightIcon,
  MagnifyingGlassIcon,
  FunnelIcon,
  XMarkIcon,
  ChevronLeftIcon,
  ChevronRightIcon
} from '@heroicons/react/24/outline'
import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useTranslation } from '../lib/translations'
import LanguageSwitcher from '../components/LanguageSwitcher'

export default function LandingPage() {
  const t = useTranslation()
  const { isAuthenticated, user, logout } = useAuthStore()
  const { theme, setTheme } = useThemeStore()
  const navigate = useNavigate()
  const [publicAgents, setPublicAgents] = useState<PublicAgent[]>([])
  const [loadingAgents, setLoadingAgents] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedLanguage, setSelectedLanguage] = useState<string>('all')
  const [selectedInteractionMode, setSelectedInteractionMode] = useState<string>('all')
  const [selectedRagEnabled, setSelectedRagEnabled] = useState<string>('all')
  const [currentPage, setCurrentPage] = useState(1)
  const [agentsPerPage] = useState(9) // 3 columns x 3 rows
  const [showFilters, setShowFilters] = useState(false)

  const features = [
    {
      name: t.landing.latenceUltraFaible,
      description: t.landing.latenceDesc,
      icon: ClockIcon,
      gradient: 'from-blue-500 to-cyan-500'
    },
    {
      name: t.landing.francaisNatif,
      description: t.landing.francaisDesc,
      icon: GlobeAltIcon,
      gradient: 'from-green-500 to-emerald-500'
    },
    {
      name: t.landing.iaAvancee,
      description: t.landing.iaDesc,
      icon: CpuChipIcon,
      gradient: 'from-purple-500 to-pink-500'
    },
    {
      name: t.landing.backofficeComplet,
      description: t.landing.backofficeDesc,
      icon: ChartBarIcon,
      gradient: 'from-orange-500 to-red-500'
    },
    {
      name: t.landing.integrationCRM,
      description: t.landing.crmDesc,
      icon: PhoneIcon,
      gradient: 'from-indigo-500 to-purple-500'
    },
    {
      name: t.landing.apiSimple,
      description: t.landing.apiDesc,
      icon: MicrophoneIcon,
      gradient: 'from-pink-500 to-rose-500'
    },
  ]

  const stats = [
    { label: t.landing.latenceMoyenne, value: '< 300ms' },
    { label: t.landing.disponibilite, value: '99.9%' },
    { label: t.landing.langues, value: '10+' },
    { label: t.landing.clients, value: '1000+' },
  ]

interface PublicAgent {
  id: number
  name: string
  description: string | null
  language: string
  rag_enabled: boolean
  phone_number?: string | null
  interaction_mode?: string
}

  useEffect(() => {
    loadPublicAgents()
  }, [])

  // Reset to first page when filters change
  useEffect(() => {
    setCurrentPage(1)
  }, [searchQuery, selectedLanguage, selectedInteractionMode, selectedRagEnabled])

  const loadPublicAgents = async () => {
    try {
      setLoadingAgents(true)
      const response = await api.get('/agents/public/list')
      setPublicAgents(response.data)
    } catch (error) {
      console.error('Error loading public agents:', error)
    } finally {
      setLoadingAgents(false)
    }
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  // Filter and search logic
  const filteredAgents = publicAgents.filter((agent) => {
    // Search filter
    const matchesSearch = 
      !searchQuery ||
      agent.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (agent.description && agent.description.toLowerCase().includes(searchQuery.toLowerCase()))

    // Language filter
    const matchesLanguage = 
      selectedLanguage === 'all' || agent.language === selectedLanguage

    // Interaction mode filter
    const matchesInteractionMode = 
      selectedInteractionMode === 'all' || agent.interaction_mode === selectedInteractionMode

    // RAG enabled filter
    const matchesRag = 
      selectedRagEnabled === 'all' ||
      (selectedRagEnabled === 'yes' && agent.rag_enabled) ||
      (selectedRagEnabled === 'no' && !agent.rag_enabled)

    return matchesSearch && matchesLanguage && matchesInteractionMode && matchesRag
  })

  // Pagination
  const totalPages = Math.ceil(filteredAgents.length / agentsPerPage)
  const indexOfLastAgent = currentPage * agentsPerPage
  const indexOfFirstAgent = indexOfLastAgent - agentsPerPage
  const currentAgents = filteredAgents.slice(indexOfFirstAgent, indexOfLastAgent)

  // Get unique languages from agents
  const availableLanguages = Array.from(
    new Set(publicAgents.map(agent => agent.language))
  ).sort()

  // Clear all filters
  const clearFilters = () => {
    setSearchQuery('')
    setSelectedLanguage('all')
    setSelectedInteractionMode('all')
    setSelectedRagEnabled('all')
    setCurrentPage(1)
  }

  // Check if any filters are active
  const hasActiveFilters = 
    searchQuery !== '' ||
    selectedLanguage !== 'all' ||
    selectedInteractionMode !== 'all' ||
    selectedRagEnabled !== 'all'

  const themeOptions = [
    { name: 'Light', value: 'light' as const, icon: SunIcon },
    { name: 'Dark', value: 'dark' as const, icon: MoonIcon },
    { name: 'System', value: 'system' as const, icon: ComputerDesktopIcon },
  ]

  const ThemeIcon = themeOptions.find(opt => opt.value === theme)?.icon || SunIcon

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors duration-200">
      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-white/90 dark:bg-gray-900/90 backdrop-blur-lg border-b border-gray-200 dark:border-gray-700 shadow-sm">
        <nav className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center">
              <MicrophoneIcon className="w-6 h-6 text-white" />
            </div>
            <span className="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
              VoiceAgent
            </span>
          </Link>
          <div className="flex items-center gap-3">
            {/* Public Agents Button - Highlighted */}
            <a
              href="#public-agents"
              className="hidden sm:inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-semibold rounded-lg shadow-md hover:shadow-lg transition-all duration-200"
            >
              <MicrophoneIcon className="w-4 h-4" />
              {t.landing.agentsPublics}
            </a>
            
            {/* Demo Button - Highlighted */}
            <Link
              to="/demo"
              className="hidden sm:inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-semibold rounded-lg shadow-md hover:shadow-lg transition-all duration-200"
            >
              <PhoneIcon className="w-4 h-4" />
              {t.landing.demo}
            </Link>

            {/* Profile Menu */}
            <Menu as="div" className="relative">
              <Menu.Button className="flex items-center gap-2 p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
                {isAuthenticated && user ? (
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-semibold text-sm">
                    {user.full_name?.charAt(0).toUpperCase()}
                  </div>
                ) : (
                  <UserCircleIcon className="w-8 h-8 text-gray-700 dark:text-gray-300" />
                )}
                <ChevronDownIcon className="w-4 h-4 text-gray-700 dark:text-gray-300 hidden sm:block" />
              </Menu.Button>
              <Transition
                as={Fragment}
                enter="transition ease-out duration-100"
                enterFrom="transform opacity-0 scale-95"
                enterTo="transform opacity-100 scale-100"
                leave="transition ease-in duration-75"
                leaveFrom="transform opacity-100 scale-100"
                leaveTo="transform opacity-0 scale-95"
              >
                <Menu.Items className="absolute right-0 mt-2 w-56 origin-top-right bg-white dark:bg-gray-800 rounded-xl shadow-lg ring-1 ring-black ring-opacity-5 divide-y divide-gray-100 dark:divide-gray-700 focus:outline-none overflow-hidden">
                  {/* User Info (only if authenticated) */}
                  {isAuthenticated && user && (
                    <div className="px-4 py-3">
                      <p className="text-sm font-semibold text-gray-900 dark:text-white truncate">{user.full_name}</p>
                      <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{user.email}</p>
                    </div>
                  )}
                  
                  {/* Login/Register (only if not authenticated) */}
                  {!isAuthenticated && (
                    <div className="p-1">
                      <Menu.Item>
                        {({ active }) => (
                          <Link
                            to="/login"
                            className={`${
                              active ? 'bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400' : 'text-gray-700 dark:text-gray-300'
                            } group flex items-center px-4 py-2.5 text-sm font-medium rounded-lg transition-colors`}
                          >
                            <ArrowRightOnRectangleIcon className="mr-3 h-5 w-5" />
                            {t.landing.commencer}
                          </Link>
                        )}
                      </Menu.Item>
                    </div>
                  )}

                  {/* Dashboard Link (only if authenticated) */}
                  {isAuthenticated && (
                    <div className="p-1">
                      <Menu.Item>
                        {({ active }) => (
                          <Link
                            to="/dashboard"
                            className={`${
                              active ? 'bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400' : 'text-gray-700 dark:text-gray-300'
                            } group flex items-center px-4 py-2.5 text-sm font-medium rounded-lg transition-colors`}
                          >
                            <UserCircleIcon className="mr-3 h-5 w-5" />
                            {t.landing.tableauDeBord}
                          </Link>
                        )}
                      </Menu.Item>
                    </div>
                  )}

                  {/* Language Settings */}
                  <div className="p-1">
                    <div className="px-4 py-2.5">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider flex items-center gap-2">
                          <GlobeAltIcon className="w-4 h-4" />
                          {t.settings.language}
                        </span>
                      </div>
                      <LanguageSwitcher />
                    </div>
                  </div>

                  {/* Theme Settings */}
                  <div className="p-1">
                    <div className="px-4 py-2.5 pb-1">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider flex items-center gap-2">
                          <ThemeIcon className="w-4 h-4" />
                          {t.settings.theme}
                        </span>
                      </div>
                    </div>
                    {themeOptions.map((option) => (
                      <Menu.Item key={option.value}>
                        {({ active }) => (
                          <button
                            onClick={() => setTheme(option.value)}
                            className={`${
                              active ? 'bg-indigo-50 dark:bg-indigo-900/20' : ''
                            } ${
                              theme === option.value ? 'text-indigo-600 dark:text-indigo-400' : 'text-gray-700 dark:text-gray-300'
                            } group flex items-center w-full px-4 py-2.5 text-sm font-medium rounded-lg transition-colors`}
                          >
                            <option.icon className="mr-3 h-5 w-5" />
                            {option.name}
                            {theme === option.value && (
                              <span className="ml-auto text-indigo-600 dark:text-indigo-400">✓</span>
                            )}
                          </button>
                        )}
                      </Menu.Item>
                    ))}
                  </div>

                  {/* Logout (only if authenticated) */}
                  {isAuthenticated && (
                    <div className="p-1">
                      <Menu.Item>
                        {({ active }) => (
                          <button
                            onClick={handleLogout}
                            className={`${
                              active ? 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400' : 'text-red-600 dark:text-red-400'
                            } group flex items-center w-full px-4 py-2.5 text-sm font-medium rounded-lg transition-colors`}
                          >
                            <ArrowRightOnRectangleIcon className="mr-3 h-5 w-5" />
                            {t.landing.deconnexion}
                          </button>
                        )}
                      </Menu.Item>
                    </div>
                  )}
                </Menu.Items>
              </Transition>
            </Menu>
          </div>
        </nav>
      </header>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-12">
            <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold text-gray-900 dark:text-white mb-6 leading-tight">
              {t.landing.agentsVocaux}{' '}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600">
                {t.landing.intelligents}
              </span>
              <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-purple-600 to-pink-600">
                {t.landing.enFrancais}
              </span>
            </h1>
            <p className="text-xl text-gray-600 dark:text-gray-300 mb-10 max-w-3xl mx-auto leading-relaxed">
              {t.landing.heroDescription}
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link 
                to={isAuthenticated ? "/dashboard" : "/register"} 
                className="inline-flex items-center gap-2 px-8 py-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white text-lg font-semibold rounded-xl shadow-lg hover:shadow-xl transition-all duration-200"
              >
                <RocketLaunchIcon className="w-6 h-6" />
                {isAuthenticated ? t.landing.tableauDeBord : t.landing.commencerGratuitement}
              </Link>
              <Link 
                to="/demo" 
                className="inline-flex items-center gap-2 px-8 py-4 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-900 dark:text-white text-lg font-semibold rounded-xl shadow-md hover:shadow-lg border-2 border-gray-200 dark:border-gray-700 transition-all duration-200"
              >
                <PhoneIcon className="w-6 h-6" />
                {t.landing.essayerDemo}
              </Link>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mt-16">
            {stats.map((stat) => (
              <div key={stat.label} className="text-center">
                <div className="text-3xl sm:text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600 mb-2">
                  {stat.value}
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400 font-medium">
                  {stat.label}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Public Agents Section */}
      <section id="public-agents" className="py-20 px-6 scroll-mt-40">
        <div className="max-w-7xl mx-auto">
            <div className="text-center mb-16">
              <div className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-indigo-500/10 to-purple-600/10 rounded-full mb-4">
                <SparklesIcon className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                <span className="text-sm font-semibold text-indigo-600 dark:text-indigo-400">
                  {t.landing.essayezMaintenant}
                </span>
              </div>
              <h2 className="text-4xl sm:text-5xl font-bold text-gray-900 dark:text-white mb-4">
                {t.landing.agentsPublicsDisponibles}
              </h2>
              {/* <p className="text-xl text-gray-600 dark:text-gray-300 max-w-2xl mx-auto">
                {t.landing.agentsPublicsDesc}
              </p> */}
            </div>

            {/* Search and Filter Bar */}
            <div className="mb-8 space-y-4">
              {/* Search Bar and Filter Button in One Line */}
              <div className="flex items-center gap-4">
                {/* Search Bar */}
                <div className="relative flex-1">
                  <MagnifyingGlassIcon className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder={t.common.status === 'Statut' ? 'Rechercher par nom ou description...' : 'Search by name or description...'}
                    className="w-full pl-12 pr-4 py-3 bg-white dark:bg-gray-800 border-2 border-gray-200 dark:border-gray-700 rounded-xl text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all"
                  />
                  {searchQuery && (
                    <button
                      onClick={() => setSearchQuery('')}
                      className="absolute right-4 top-1/2 transform -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                    >
                      <XMarkIcon className="w-5 h-5" />
                    </button>
                  )}
                </div>

                {/* Filter Toggle Button */}
                <button
                  onClick={() => setShowFilters(!showFilters)}
                  className={`inline-flex items-center gap-2 px-4 py-3 rounded-xl font-medium transition-all whitespace-nowrap ${
                    showFilters || hasActiveFilters
                      ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-md'
                      : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                  }`}
                >
                  <FunnelIcon className="w-5 h-5" />
                  {t.common.status === 'Statut' ? 'Filtres' : 'Filters'}
                  {hasActiveFilters && (
                    <span className="ml-1 px-2 py-0.5 bg-white/20 dark:bg-white/10 rounded-full text-xs">
                      {[searchQuery, selectedLanguage, selectedInteractionMode, selectedRagEnabled].filter(f => f !== 'all' && f !== '').length}
                    </span>
                  )}
                </button>

                {/* Clear Filters Button */}
                {hasActiveFilters && (
                  <button
                    onClick={clearFilters}
                    className="inline-flex items-center gap-2 px-4 py-3 text-sm text-gray-600 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors whitespace-nowrap"
                  >
                    <XMarkIcon className="w-4 h-4" />
                    {t.common.status === 'Statut' ? 'Effacer' : 'Clear'}
                  </button>
                )}
              </div>

              {/* Results count and info */}
              <div className="flex items-center justify-between">
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  {filteredAgents.length} {t.common.status === 'Statut' ? 'agent(s) trouvé(s)' : 'agent(s) found'}
                </div>
              </div>

              {/* Filter Panel */}
              {showFilters && (
                <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border-2 border-gray-200 dark:border-gray-700 shadow-lg">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {/* Language Filter */}
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                        {t.common.status === 'Statut' ? 'Langue' : 'Language'}
                      </label>
                      <select
                        value={selectedLanguage}
                        onChange={(e) => setSelectedLanguage(e.target.value)}
                        className="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-900 border-2 border-gray-200 dark:border-gray-700 rounded-lg text-gray-900 dark:text-white focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all"
                      >
                        <option value="all">{t.common.status === 'Statut' ? 'Toutes les langues' : 'All Languages'}</option>
                        {availableLanguages.map((lang) => (
                          <option key={lang} value={lang}>
                            {lang === 'fr-FR' ? '🇫🇷 Français' : lang === 'en-US' ? '🇬🇧 English' : lang}
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* Interaction Mode Filter */}
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                        {t.common.status === 'Statut' ? 'Mode d\'interaction' : 'Interaction Mode'}
                      </label>
                      <select
                        value={selectedInteractionMode}
                        onChange={(e) => setSelectedInteractionMode(e.target.value)}
                        className="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-900 border-2 border-gray-200 dark:border-gray-700 rounded-lg text-gray-900 dark:text-white focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all"
                      >
                        <option value="all">{t.common.status === 'Statut' ? 'Tous les modes' : 'All Modes'}</option>
                        <option value="voice">{t.common.status === 'Statut' ? '🎤 Voix' : '🎤 Voice'}</option>
                        <option value="text">{t.common.status === 'Statut' ? '💬 Texte' : '💬 Text'}</option>
                        <option value="both">{t.common.status === 'Statut' ? '🎤💬 Voix & Texte' : '🎤💬 Voice & Text'}</option>
                      </select>
                    </div>

                    {/* RAG Enabled Filter */}
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                        {t.common.status === 'Statut' ? 'Base de connaissances' : 'Knowledge Base'}
                      </label>
                      <select
                        value={selectedRagEnabled}
                        onChange={(e) => setSelectedRagEnabled(e.target.value)}
                        className="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-900 border-2 border-gray-200 dark:border-gray-700 rounded-lg text-gray-900 dark:text-white focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all"
                      >
                        <option value="all">{t.common.status === 'Statut' ? 'Tous' : 'All'}</option>
                        <option value="yes">{t.common.status === 'Statut' ? '✓ Avec base de connaissances' : '✓ With Knowledge Base'}</option>
                        <option value="no">{t.common.status === 'Statut' ? '✗ Sans base de connaissances' : '✗ Without Knowledge Base'}</option>
                      </select>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {loadingAgents ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {[...Array(3)].map((_, index) => (
                  <div
                    key={`agent-skeleton-${index}`}
                    className="relative bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700 overflow-hidden animate-pulse"
                  >
                    <div className="relative space-y-4">
                      <div className="w-14 h-14 rounded-xl bg-gray-200 dark:bg-gray-700"></div>
                      <div className="h-5 w-3/4 rounded bg-gray-200 dark:bg-gray-700"></div>
                      <div className="space-y-2">
                        <div className="h-3 w-full rounded bg-gray-200 dark:bg-gray-700"></div>
                        <div className="h-3 w-5/6 rounded bg-gray-200 dark:bg-gray-700"></div>
                      </div>
                      <div className="flex gap-2">
                        <div className="h-6 w-20 rounded-full bg-gray-200 dark:bg-gray-700"></div>
                        <div className="h-6 w-24 rounded-full bg-gray-200 dark:bg-gray-700"></div>
                      </div>
                      <div className="space-y-2 pt-4">
                        <div className="h-11 w-full rounded-lg bg-gray-200 dark:bg-gray-700"></div>
                        <div className="h-11 w-full rounded-lg bg-gray-200 dark:bg-gray-700"></div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : filteredAgents.length === 0 ? (
              <div className="text-center py-12">
                <MagnifyingGlassIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-600 dark:text-gray-400 mb-6 text-lg">
                  {t.common.status === 'Statut' 
                    ? 'Aucun agent ne correspond à vos critères de recherche.' 
                    : 'No agents match your search criteria.'}
                </p>
                {hasActiveFilters && (
                  <button
                    onClick={clearFilters}
                    className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-semibold rounded-lg shadow-md transition-all duration-200"
                  >
                    <XMarkIcon className="w-5 h-5" />
                    {t.common.status === 'Statut' ? 'Effacer les filtres' : 'Clear filters'}
                  </button>
                )}
              </div>
            ) : (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {currentAgents.map((agent) => {
                  // Get interaction mode icon and color
                  const getInteractionIcon = () => {
                    if (agent.interaction_mode === 'text') {
                      return <ChatBubbleLeftRightIcon className="w-7 h-7 text-white" />
                    } else if (agent.interaction_mode === 'both') {
                      return (
                        <div className="flex items-center gap-1">
                          <MicrophoneIcon className="w-5 h-5 text-white" />
                          <ChatBubbleLeftRightIcon className="w-5 h-5 text-white" />
                        </div>
                      )
                    }
                    return <MicrophoneIcon className="w-7 h-7 text-white" />
                  }

                  const getInteractionGradient = () => {
                    if (agent.interaction_mode === 'text') {
                      return 'from-purple-600 to-pink-600'
                    } else if (agent.interaction_mode === 'both') {
                      return 'from-blue-600 via-purple-600 to-pink-600'
                    }
                    return 'from-indigo-600 to-purple-600'
                  }

                  const getInteractionLabel = () => {
                    if (agent.interaction_mode === 'text') {
                      return t.common.status === 'Statut' ? 'Chat texte' : 'Text Chat'
                    } else if (agent.interaction_mode === 'both') {
                      return t.common.status === 'Statut' ? 'Voix & Texte' : 'Voice & Text'
                    }
                    return t.common.status === 'Statut' ? 'Voix' : 'Voice'
                  }

                  return (
                    <div
                      key={agent.id}
                      className="group relative bg-white dark:bg-gray-800 rounded-2xl p-6 border-2 border-gray-200 dark:border-gray-700 hover:border-indigo-500 dark:hover:border-indigo-400 hover:shadow-2xl transition-all duration-300 transform hover:-translate-y-1"
                    >
                      {/* Gradient Top Border */}
                      <div className={`absolute top-0 left-0 right-0 h-1 bg-gradient-to-r ${getInteractionGradient()}`}></div>
                      
                      <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-purple-600/5 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-200"></div>
                      <div className="relative">
                        {/* Agent Icon */}
                        <div className={`w-16 h-16 rounded-2xl bg-gradient-to-br ${getInteractionGradient()} flex items-center justify-center mb-4 shadow-lg`}>
                          {getInteractionIcon()}
                        </div>

                        {/* Agent Info */}
                        <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                          {agent.name}
                        </h3>
                        <p className="text-gray-600 dark:text-gray-300 text-sm mb-4 line-clamp-2 min-h-[2.5rem]">
                          {agent.description || (t.common.status === 'Statut' ? 'Agent intelligent prêt à vous aider' : 'Intelligent agent ready to help you')}
                        </p>

                        {/* Agent Features */}
                        <div className="flex flex-wrap gap-2 mb-4">
                          <span className="inline-flex items-center gap-1 px-3 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-xs font-semibold rounded-full border border-blue-200 dark:border-blue-800">
                            <GlobeAltIcon className="w-3.5 h-3.5" />
                            {agent.language === 'fr-FR' ? '🇫🇷 Français' : agent.language === 'en-US' ? '🇬🇧 English' : agent.language}
                          </span>
                          <span className={`inline-flex items-center gap-1 px-3 py-1 text-xs font-semibold rounded-full border ${
                            agent.interaction_mode === 'text'
                              ? 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800'
                              : agent.interaction_mode === 'both'
                              ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800'
                              : 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 border-indigo-200 dark:border-indigo-800'
                          }`}>
                            {agent.interaction_mode === 'text' ? '💬' : agent.interaction_mode === 'both' ? '🎤💬' : '🎤'}
                            {getInteractionLabel()}
                          </span>
                          {agent.rag_enabled && (
                            <span className="inline-flex items-center gap-1 px-3 py-1 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 text-xs font-semibold rounded-full border border-purple-200 dark:border-purple-800">
                              <SparklesIcon className="w-3.5 h-3.5" />
                              {t.common.status === 'Statut' ? 'Base de connaissances' : 'Knowledge Base'}
                            </span>
                          )}
                        </div>

                        {/* Try Button */}
                        <div className="flex flex-col gap-2">
                          <Link
                            to={`/agent/${agent.id}`}
                            className={`inline-flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r ${getInteractionGradient()} hover:opacity-90 text-white font-bold rounded-xl shadow-lg hover:shadow-xl transition-all duration-200 transform hover:scale-105`}
                          >
                            {agent.interaction_mode === 'text' ? (
                              <ChatBubbleLeftRightIcon className="w-5 h-5" />
                            ) : agent.interaction_mode === 'both' ? (
                              <div className="flex items-center gap-1">
                                <MicrophoneIcon className="w-4 h-4" />
                                <ChatBubbleLeftRightIcon className="w-4 h-4" />
                              </div>
                            ) : (
                              <MicrophoneIcon className="w-5 h-5" />
                            )}
                            {t.landing.essayerMaintenant}
                          </Link>
                          {agent.phone_number && (
                            <a
                              href={`tel:${agent.phone_number}`}
                              className="inline-flex items-center justify-center gap-2 px-4 py-3 border-2 border-emerald-200 dark:border-emerald-500/40 text-emerald-600 dark:text-emerald-400 font-semibold rounded-xl hover:bg-emerald-50 dark:hover:bg-emerald-900/30 transition-all duration-200"
                            >
                              <PhoneIcon className="w-5 h-5" />
                              {t.landing.appeler} {agent.phone_number}
                            </a>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="mt-12 flex items-center justify-center gap-2">
                    <button
                      onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                      disabled={currentPage === 1}
                      className="px-4 py-2 rounded-lg bg-white dark:bg-gray-800 border-2 border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 font-medium hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2"
                    >
                      <ChevronLeftIcon className="w-5 h-5" />
                      {t.common.status === 'Statut' ? 'Précédent' : 'Previous'}
                    </button>

                    {/* Page Numbers */}
                    <div className="flex items-center gap-2">
                      {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => {
                        // Show first page, last page, current page, and pages around current
                        if (
                          page === 1 ||
                          page === totalPages ||
                          (page >= currentPage - 1 && page <= currentPage + 1)
                        ) {
                          return (
                            <button
                              key={page}
                              onClick={() => setCurrentPage(page)}
                              className={`px-4 py-2 rounded-lg font-medium transition-all ${
                                currentPage === page
                                  ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-md'
                                  : 'bg-white dark:bg-gray-800 border-2 border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
                              }`}
                            >
                              {page}
                            </button>
                          )
                        } else if (page === currentPage - 2 || page === currentPage + 2) {
                          return <span key={page} className="px-2 text-gray-400">...</span>
                        }
                        return null
                      })}
                    </div>

                    <button
                      onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                      disabled={currentPage === totalPages}
                      className="px-4 py-2 rounded-lg bg-white dark:bg-gray-800 border-2 border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 font-medium hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2"
                    >
                      {t.common.status === 'Statut' ? 'Suivant' : 'Next'}
                      <ChevronRightIcon className="w-5 h-5" />
                    </button>
                  </div>
                )}

                {/* Results info */}
                {filteredAgents.length > 0 && (
                  <div className="mt-6 text-center text-sm text-gray-600 dark:text-gray-400">
                    {t.common.status === 'Statut' 
                      ? `Affichage de ${indexOfFirstAgent + 1} à ${Math.min(indexOfLastAgent, filteredAgents.length)} sur ${filteredAgents.length} agent(s)`
                      : `Showing ${indexOfFirstAgent + 1} to ${Math.min(indexOfLastAgent, filteredAgents.length)} of ${filteredAgents.length} agent(s)`}
                  </div>
                )}
              </>
            )}

            {/* Call to action if no agents at all */}
            {!loadingAgents && publicAgents.length === 0 && (
              <div className="text-center py-12">
                <MicrophoneIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-600 dark:text-gray-400 mb-6">
                  {t.landing.aucunAgentPublic}
                </p>
                {!isAuthenticated && (
                  <Link
                    to="/register"
                    className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-semibold rounded-lg shadow-md transition-all duration-200"
                  >
                    {t.landing.creerPremierAgent}
                  </Link>
                )}
              </div>
            )}
        </div>
      </section>
      
      {/* Features Section */}
      <section className="py-20 px-6 bg-white dark:bg-gray-800">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl sm:text-5xl font-bold text-gray-900 dark:text-white mb-4">
              {t.landing.fonctionnalitesPuissantes}
            </h2>
            <p className="text-xl text-gray-600 dark:text-gray-300 max-w-2xl mx-auto">
              {t.landing.fonctionnalitesDesc}
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {features.map((feature) => (
              <div
                key={feature.name}
                className="group relative bg-gray-50 dark:bg-gray-900 rounded-xl p-6 hover:shadow-xl transition-all duration-200 border border-gray-200 dark:border-gray-700"
              >
                <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/10 to-purple-600/10 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-200"></div>
                <div className="relative">
                  <div className={`w-12 h-12 rounded-lg bg-gradient-to-br ${feature.gradient} flex items-center justify-center mb-4 shadow-md`}>
                    <feature.icon className="w-6 h-6 text-white" />
                  </div>
                  <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                    {feature.name}
                  </h3>
                  <p className="text-gray-600 dark:text-gray-300 leading-relaxed">
                    {feature.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>



      {/* Benefits Section */}
      <section className="py-20 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div>
              <h2 className="text-4xl font-bold text-gray-900 dark:text-white mb-6">
                {t.landing.pourquoiChoisir}
              </h2>
              <div className="space-y-4">
                {(t.common.status === 'Statut' ? [
                  t.landing.config5Minutes,
                  t.landing.aucuneExpertise,
                  t.landing.scalingAutomatique,
                  t.landing.support247,
                  t.landing.securiteRGPD,
                  t.landing.integrationsIllimitees
                ] : [
                  '5-Minute Setup',
                  'No technical expertise required',
                  'Automatic Scaling',
                  '24/7 Support',
                  'Security & GDPR',
                  'Unlimited Integrations'
                ]).map((benefit, index) => (
                  <div key={index} className="flex items-center gap-3">
                    <div className="flex-shrink-0 w-6 h-6 rounded-full bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center">
                      <CheckIcon className="w-4 h-4 text-white" />
                    </div>
                    <span className="text-lg text-gray-700 dark:text-gray-300">{benefit}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="relative">
              <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/20 to-purple-600/20 rounded-2xl blur-3xl"></div>
              <div className="relative bg-white dark:bg-gray-800 rounded-2xl shadow-2xl p-8 border border-gray-200 dark:border-gray-700">
                <ShieldCheckIcon className="w-16 h-16 text-indigo-600 mb-4" />
                <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                  {t.landing.securiteConformite}
                </h3>
                <p className="text-gray-600 dark:text-gray-300 mb-6">
                  {t.landing.securiteDesc}
                </p>
                <div className="flex gap-4">
                  <div className="flex-1 bg-gray-50 dark:bg-gray-900 rounded-lg p-4 text-center border border-gray-200 dark:border-gray-700">
                    <div className="text-2xl font-bold text-indigo-600 mb-1">256-bit</div>
                    <div className="text-xs text-gray-600 dark:text-gray-400">{t.landing.cryptageSSL}</div>
                  </div>
                  <div className="flex-1 bg-gray-50 dark:bg-gray-900 rounded-lg p-4 text-center border border-gray-200 dark:border-gray-700">
                    <div className="text-2xl font-bold text-green-600 mb-1">RGPD</div>
                    <div className="text-xs text-gray-600 dark:text-gray-400">{t.landing.conforme}</div>
                  </div>
                  <div className="flex-1 bg-gray-50 dark:bg-gray-900 rounded-lg p-4 text-center border border-gray-200 dark:border-gray-700">
                    <div className="text-2xl font-bold text-purple-600 mb-1">99.9%</div>
                    <div className="text-xs text-gray-600 dark:text-gray-400">{t.landing.uptime}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="relative overflow-hidden bg-gradient-to-r from-indigo-600 to-purple-600 rounded-2xl shadow-2xl p-12 text-center">
            <div className="absolute inset-0 bg-black/10"></div>
            <div className="relative">
              <h2 className="text-4xl sm:text-5xl font-bold text-white mb-6">
                {t.landing.pretTransformer} {t.landing.pretDesc}
              </h2>
              <p className="text-xl text-indigo-100 mb-8 max-w-2xl mx-auto">
                {t.common.status === 'Statut' ? 'Rejoignez plus de 1000 entreprises qui utilisent déjà VoiceAgent pour automatiser leurs conversations.' : 'Join over 1000 companies already using VoiceAgent to automate their conversations.'}
              </p>
              <Link 
                to={isAuthenticated ? "/dashboard" : "/register"}
                className="inline-flex items-center gap-2 px-8 py-4 bg-white hover:bg-gray-100 text-indigo-600 text-lg font-bold rounded-xl shadow-xl transition-all duration-200"
              >
                <RocketLaunchIcon className="w-6 h-6" />
                {t.landing.commencerMaintenant}
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-6 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
        <div className="max-w-7xl mx-auto space-y-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center">
                <MicrophoneIcon className="w-5 h-5 text-white" />
              </div>
              <span className="text-lg font-bold text-gray-900 dark:text-white">VoiceAgent</span>
            </div>
            <div className="text-center text-gray-600 dark:text-gray-400">
              <p>&copy; 2025 VoiceAgent SaaS. {t.landing.tousDroitsReserves}</p>
            </div>
            <div className="flex gap-6">
              <Link to="/demo" className="text-gray-600 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors">
                {t.landing.demo}
              </Link>
              <a href="#" className="text-gray-600 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors">
                {t.landing.documentation}
              </a>
              <Link to="/support" className="text-gray-600 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors">
                {t.landing.support}
              </Link>
            </div>
          </div>
          <div className="text-center text-sm text-gray-500 dark:text-gray-400 border-t border-gray-200 dark:border-gray-700 pt-6">
            <p className="font-medium text-gray-700 dark:text-gray-300">Exatek (SA)</p>
            <p>VAT: BE 0831.113.519</p>
            <p>Rue de la Colonne 1A, 1080 Molenbeek-Saint-Jean</p>
          </div>
        </div>
      </footer>
    </div>
  )
}
