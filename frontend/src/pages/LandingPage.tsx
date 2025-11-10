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
  SparklesIcon
} from '@heroicons/react/24/outline'
import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'

const features = [
  {
    name: 'Latence Ultra-Faible',
    description: 'Conversations en temps réel avec moins de 300ms de latence grâce à Gemini 2.5.',
    icon: ClockIcon,
    gradient: 'from-blue-500 to-cyan-500'
  },
  {
    name: 'Français Natif',
    description: 'Agents vocaux optimisés pour le français avec une prononciation naturelle.',
    icon: GlobeAltIcon,
    gradient: 'from-green-500 to-emerald-500'
  },
  {
    name: 'IA Avancée',
    description: 'Alimenté par LangChain et Google Gemini pour des conversations intelligentes.',
    icon: CpuChipIcon,
    gradient: 'from-purple-500 to-pink-500'
  },
  {
    name: 'Backoffice Complet',
    description: 'Revoyez les appels, transcriptions et analyses dans un tableau de bord intuitif.',
    icon: ChartBarIcon,
    gradient: 'from-orange-500 to-red-500'
  },
  {
    name: 'Intégration CRM',
    description: 'Synchronisez automatiquement vos appels avec votre CRM (HubSpot, Salesforce).',
    icon: PhoneIcon,
    gradient: 'from-indigo-500 to-purple-500'
  },
  {
    name: 'API Simple',
    description: 'Intégrez facilement avec des API keys et des webhooks.',
    icon: MicrophoneIcon,
    gradient: 'from-pink-500 to-rose-500'
  },
]

const stats = [
  { label: 'Latence Moyenne', value: '< 300ms' },
  { label: 'Disponibilité', value: '99.9%' },
  { label: 'Langues', value: '10+' },
  { label: 'Clients', value: '1000+' },
]

interface PublicAgent {
  id: number
  name: string
  description: string | null
  language: string
  rag_enabled: boolean
  phone_number?: string | null
}

export default function LandingPage() {
  const { isAuthenticated, user, logout } = useAuthStore()
  const { theme, setTheme } = useThemeStore()
  const navigate = useNavigate()
  const [publicAgents, setPublicAgents] = useState<PublicAgent[]>([])
  const [loadingAgents, setLoadingAgents] = useState(true)

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
            <Link
              to="/demo"
              className="hidden sm:inline-flex text-gray-700 dark:text-gray-300 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors font-medium"
            >
              Démo
            </Link>

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
                            Tableau de bord
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
                            Déconnexion
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
                Commencer
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
              Agents Vocaux{' '}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600">
                Intelligents
              </span>
              <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-purple-600 to-pink-600">
                en Français
              </span>
            </h1>
            <p className="text-xl text-gray-600 dark:text-gray-300 mb-10 max-w-3xl mx-auto leading-relaxed">
              Créez des agents vocaux ultra-réactifs avec l'IA de pointe. 
              Latence minimale, conversations naturelles, intégration complète.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link 
                to={isAuthenticated ? "/dashboard" : "/register"} 
                className="inline-flex items-center gap-2 px-8 py-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white text-lg font-semibold rounded-xl shadow-lg hover:shadow-xl transition-all duration-200"
              >
                <RocketLaunchIcon className="w-6 h-6" />
                {isAuthenticated ? "Tableau de bord" : "Commencer Gratuitement"}
              </Link>
              <Link 
                to="/demo" 
                className="inline-flex items-center gap-2 px-8 py-4 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-900 dark:text-white text-lg font-semibold rounded-xl shadow-md hover:shadow-lg border-2 border-gray-200 dark:border-gray-700 transition-all duration-200"
              >
                <PhoneIcon className="w-6 h-6" />
                Essayer la Démo
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
              Fonctionnalités Puissantes
            </h2>
            <p className="text-xl text-gray-600 dark:text-gray-300 max-w-2xl mx-auto">
              Tout ce dont vous avez besoin pour créer des agents vocaux exceptionnels
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
      {publicAgents.length > 0 && (
        <section className="py-20 px-6">
          <div className="max-w-7xl mx-auto">
            <div className="text-center mb-16">
              <div className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-indigo-500/10 to-purple-600/10 rounded-full mb-4">
                <SparklesIcon className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                <span className="text-sm font-semibold text-indigo-600 dark:text-indigo-400">
                  Essayez Maintenant
                </span>
              </div>
              <h2 className="text-4xl sm:text-5xl font-bold text-gray-900 dark:text-white mb-4">
                Agents Publics Disponibles
              </h2>
              <p className="text-xl text-gray-600 dark:text-gray-300 max-w-2xl mx-auto">
                Testez nos agents vocaux intelligents - aucune inscription requise
              </p>
            </div>

            {loadingAgents ? (
              <div className="flex justify-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {publicAgents.map((agent) => (
                  <div
                    key={agent.id}
                    className="group relative bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700 hover:border-indigo-500 dark:hover:border-indigo-400 hover:shadow-xl transition-all duration-200"
                  >
                    <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-purple-600/5 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-200"></div>
                    <div className="relative">
                      {/* Agent Icon */}
                      <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center mb-4 shadow-md">
                        <MicrophoneIcon className="w-7 h-7 text-white" />
                      </div>

                      {/* Agent Info */}
                      <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                        {agent.name}
                      </h3>
                      <p className="text-gray-600 dark:text-gray-300 text-sm mb-4 line-clamp-2">
                        {agent.description || 'Agent vocal intelligent prêt à vous aider'}
                      </p>

                      {/* Agent Features */}
                      <div className="flex flex-wrap gap-2 mb-4">
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-xs font-medium rounded-full">
                          <GlobeAltIcon className="w-3 h-3" />
                          {agent.language === 'fr-FR' ? 'Français' : agent.language === 'en-US' ? 'English' : agent.language}
                        </span>
                        {agent.rag_enabled && (
                          <span className="inline-flex items-center gap-1 px-2 py-1 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 text-xs font-medium rounded-full">
                            <SparklesIcon className="w-3 h-3" />
                            Knowledge Base
                          </span>
                        )}
                      </div>

                      {/* Try Button */}
                      <div className="flex flex-col gap-2">
                        <Link
                          to={`/agent/${agent.id}`}
                          className="inline-flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-semibold rounded-lg shadow-md hover:shadow-lg transition-all duration-200"
                        >
                          <MicrophoneIcon className="w-5 h-5" />
                          Essayer Maintenant
                        </Link>
                        {agent.phone_number && (
                          <a
                            href={`tel:${agent.phone_number}`}
                            className="inline-flex items-center justify-center gap-2 px-4 py-3 border border-indigo-200 dark:border-indigo-500/40 text-indigo-600 dark:text-indigo-300 font-semibold rounded-lg hover:bg-indigo-50 dark:hover:bg-indigo-900/30 transition-all duration-200"
                          >
                            <PhoneIcon className="w-5 h-5" />
                            {agent.language?.startsWith('fr') ? 'Appeler' : 'Call'} {agent.phone_number}
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Call to action if no agents */}
            {!loadingAgents && publicAgents.length === 0 && (
              <div className="text-center py-12">
                <MicrophoneIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-600 dark:text-gray-400 mb-6">
                  Aucun agent public disponible pour le moment
                </p>
                {!isAuthenticated && (
                  <Link
                    to="/register"
                    className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-semibold rounded-lg shadow-md transition-all duration-200"
                  >
                    Créer Votre Premier Agent
                  </Link>
                )}
              </div>
            )}
          </div>
        </section>
      )}

      {/* Benefits Section */}
      <section className="py-20 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div>
              <h2 className="text-4xl font-bold text-gray-900 dark:text-white mb-6">
                Pourquoi Choisir VoiceAgent ?
              </h2>
              <div className="space-y-4">
                {[
                  'Configuration en moins de 5 minutes',
                  'Aucune expertise technique requise',
                  'Scaling automatique selon vos besoins',
                  'Support client 24/7 en français',
                  'Sécurité et conformité RGPD',
                  'Intégrations illimitées'
                ].map((benefit, index) => (
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
                  Sécurité & Conformité
                </h3>
                <p className="text-gray-600 dark:text-gray-300 mb-6">
                  Vos données sont cryptées de bout en bout. Nous sommes conformes aux normes RGPD 
                  et hébergeons vos données en Europe.
                </p>
                <div className="flex gap-4">
                  <div className="flex-1 bg-gray-50 dark:bg-gray-900 rounded-lg p-4 text-center border border-gray-200 dark:border-gray-700">
                    <div className="text-2xl font-bold text-indigo-600 mb-1">256-bit</div>
                    <div className="text-xs text-gray-600 dark:text-gray-400">Cryptage SSL</div>
                  </div>
                  <div className="flex-1 bg-gray-50 dark:bg-gray-900 rounded-lg p-4 text-center border border-gray-200 dark:border-gray-700">
                    <div className="text-2xl font-bold text-green-600 mb-1">RGPD</div>
                    <div className="text-xs text-gray-600 dark:text-gray-400">Conforme</div>
                  </div>
                  <div className="flex-1 bg-gray-50 dark:bg-gray-900 rounded-lg p-4 text-center border border-gray-200 dark:border-gray-700">
                    <div className="text-2xl font-bold text-purple-600 mb-1">99.9%</div>
                    <div className="text-xs text-gray-600 dark:text-gray-400">Uptime</div>
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
                Prêt à Transformer Votre Service Client ?
              </h2>
              <p className="text-xl text-indigo-100 mb-8 max-w-2xl mx-auto">
                Rejoignez plus de 1000 entreprises qui utilisent déjà VoiceAgent pour automatiser leurs conversations.
              </p>
              <Link 
                to={isAuthenticated ? "/dashboard" : "/register"}
                className="inline-flex items-center gap-2 px-8 py-4 bg-white hover:bg-gray-100 text-indigo-600 text-lg font-bold rounded-xl shadow-xl transition-all duration-200"
              >
                <RocketLaunchIcon className="w-6 h-6" />
                Commencer Maintenant
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
              <p>&copy; 2025 VoiceAgent SaaS. Tous droits réservés.</p>
            </div>
            <div className="flex gap-6">
              <Link to="/demo" className="text-gray-600 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors">
                Démo
              </Link>
              <a href="#" className="text-gray-600 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors">
                Documentation
              </a>
              <Link to="/support" className="text-gray-600 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors">
                Support
              </Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
