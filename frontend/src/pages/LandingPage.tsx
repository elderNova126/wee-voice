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
  ChatBubbleLeftRightIcon
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

            {/* Language Switcher */}
            <div className="hidden sm:block">
              <LanguageSwitcher />
            </div>

            {/* Theme Dropdown */}
            <Menu as="div" className="relative">
              <Menu.Button className="p-2 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
                <ThemeIcon className="w-5 h-5" />
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
                <Menu.Items className="absolute right-0 mt-2 w-48 origin-top-right bg-white dark:bg-gray-800 rounded-xl shadow-lg ring-1 ring-black ring-opacity-5 divide-y divide-gray-100 dark:divide-gray-700 focus:outline-none overflow-hidden">
                  <div className="p-1">
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
                </Menu.Items>
              </Transition>
            </Menu>

            {/* User Menu or Login Button */}
            {isAuthenticated && user ? (
              <Menu as="div" className="relative">
                <Menu.Button className="flex items-center gap-2 p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-semibold text-sm">
                    {user.full_name?.charAt(0).toUpperCase()}
                  </div>
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
                    {/* User Info */}
                    <div className="px-4 py-3">
                      <p className="text-sm font-semibold text-gray-900 dark:text-white truncate">{user.full_name}</p>
                      <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{user.email}</p>
                    </div>
                    {/* Dashboard Link */}
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
                    {/* Logout */}
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
                  </Menu.Items>
                </Transition>
              </Menu>
            ) : (
              <Link
                to="/login"
                className="inline-flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-medium rounded-lg shadow-md transition-all duration-200"
              >
                {t.landing.commencer}
              </Link>
            )}
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
              <p className="text-xl text-gray-600 dark:text-gray-300 max-w-2xl mx-auto">
                {t.landing.agentsPublicsDesc}
              </p>
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
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {publicAgents.map((agent) => {
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
            )}

            {/* Call to action if no agents */}
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
        <div className="max-w-7xl mx-auto">
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
        </div>
      </footer>
    </div>
  )
}
