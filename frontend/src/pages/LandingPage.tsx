import { Link } from 'react-router-dom'
import {
  MicrophoneIcon,
  ClockIcon,
  GlobeAltIcon,
  ChartBarIcon,
  PhoneIcon,
  CpuChipIcon,
} from '@heroicons/react/24/outline'
import { useAuthStore } from '../store/authStore'

const features = [
  {
    name: 'Latence Ultra-Faible',
    description: 'Conversations en temps réel avec moins de 300ms de latence grâce à Gemini 2.5.',
    icon: ClockIcon,
  },
  {
    name: 'Français Natif',
    description: 'Agents vocaux optimisés pour le français avec une prononciation naturelle.',
    icon: GlobeAltIcon,
  },
  {
    name: 'IA Avancée',
    description: 'Alimenté par LangChain et Google Gemini pour des conversations intelligentes.',
    icon: CpuChipIcon,
  },
  {
    name: 'Backoffice Complet',
    description: 'Revoyez les appels, transcriptions et analyses dans un tableau de bord intuitif.',
    icon: ChartBarIcon,
  },
  {
    name: 'Intégration CRM',
    description: 'Synchronisez automatiquement vos appels avec votre CRM (HubSpot, Salesforce).',
    icon: PhoneIcon,
  },
  {
    name: 'API Simple',
    description: 'Intégrez facilement avec des API keys et des webhooks.',
    icon: MicrophoneIcon,
  },
]

export default function LandingPage() {
  const { isAuthenticated } = useAuthStore()

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900">
      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-white/80 dark:bg-gray-900/80 backdrop-blur-md border-b border-gray-200 dark:border-gray-700">
        <nav className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <MicrophoneIcon className="w-8 h-8 text-primary-600" />
            <span className="text-2xl font-bold text-gray-900 dark:text-white">VoiceAgent</span>
          </div>
          <div className="flex items-center space-x-4">
            <Link
              to="/demo"
              className="text-gray-700 dark:text-gray-300 hover:text-primary-600 transition-colors"
            >
              Démo
            </Link>
            <Link
              to={isAuthenticated ? "/dashboard" : "/login"}
              className="btn-primary"
            >
              {isAuthenticated ? "Tableau de bord" : "Commencer"}
            </Link>
          </div>
        </nav>
      </header>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-7xl mx-auto text-center">
          <h1 className="text-6xl font-bold text-gray-900 dark:text-white mb-6">
            Agents Vocaux Intelligents
            <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary-600 to-purple-600">
              en Français
            </span>
          </h1>
          <p className="text-xl text-gray-600 dark:text-gray-300 mb-8 max-w-3xl mx-auto">
            Créez des agents vocaux ultra-réactifs avec l'IA de pointe. Latence minimale, 
            conversations naturelles, intégration CRM complète.
          </p>
          <div className="flex items-center justify-center space-x-4">
            <Link to="/demo" className="btn-primary text-lg px-8 py-3">
              Essayer la Démo
            </Link>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 px-6 bg-white/50 dark:bg-gray-800/50">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-4xl font-bold text-center text-gray-900 dark:text-white mb-16">
            Fonctionnalités Clés
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {features.map((feature) => (
              <div
                key={feature.name}
                className="card hover:shadow-lg transition-shadow"
              >
                <feature.icon className="w-12 h-12 text-primary-600 mb-4" />
                <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                  {feature.name}
                </h3>
                <p className="text-gray-600 dark:text-gray-300">
                  {feature.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-4xl font-bold text-gray-900 dark:text-white mb-6">
            Prêt à commencer ?
          </h2>
          <p className="text-xl text-gray-600 dark:text-gray-300 mb-8">
            Créez votre premier agent vocal en quelques minutes.
          </p>
          <Link to={isAuthenticated ? "/dashboard" : "/login"} className="btn-primary text-lg px-8 py-3">
            {isAuthenticated ? "Tableau de bord" : "Commencer"}
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-6 border-t border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto text-center text-gray-600 dark:text-gray-400">
          <p>&copy; 2025 VoiceAgent SaaS. Tous droits réservés.</p>
        </div>
      </footer>
    </div>
  )
}

