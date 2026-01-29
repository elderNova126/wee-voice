import { Link } from 'react-router-dom'
import { useLanguageStore } from '@/store/languageStore'
import { API_URL } from '@/lib/api'
import {
  ArrowLeftIcon,
  BookOpenIcon,
  CommandLineIcon,
  PlayIcon,
  ChatBubbleLeftRightIcon,
  ArrowTopRightOnSquareIcon,
} from '@heroicons/react/24/outline'

const content = {
  en: {
    title: 'Documentation',
    backToHome: 'Back to Home',
    subtitle: 'API reference, getting started, and resources.',
    apiReference: 'API Reference',
    apiDescription:
      'Interactive API documentation (OpenAPI/Swagger) for the Weevoice backend. Use it to explore endpoints, authenticate, and try requests.',
    openApiDocs: 'Open API docs',
    gettingStarted: 'Getting Started',
    getStartedItems: [
      { label: 'Try the demo', href: '/demo', description: 'Test a voice or text agent in your browser.' },
      { label: 'Create an account', href: '/register', description: 'Register to build and deploy your own agents.' },
      { label: 'Contact support', href: '/support', description: 'Get help with setup, billing, or technical questions.' },
    ],
    resources: 'Resources',
    resourcesItems: [
      { label: 'Support', href: '/support' },
      { label: 'Privacy Policy', href: '/privacy' },
      { label: 'Terms of Service', href: '/terms' },
    ],
  },
  fr: {
    title: 'Documentation',
    backToHome: "Retour à l'accueil",
    subtitle: "Référence API, prise en main et ressources.",
    apiReference: 'Référence API',
    apiDescription:
      "Documentation API interactive (OpenAPI/Swagger) du backend Weevoice. Utilisez-la pour explorer les endpoints, vous authentifier et tester des requêtes.",
    openApiDocs: 'Ouvrir la doc API',
    gettingStarted: 'Prise en main',
    getStartedItems: [
      { label: 'Essayer la démo', href: '/demo', description: 'Tester un agent vocal ou textuel dans votre navigateur.' },
      { label: 'Créer un compte', href: '/register', description: 'S\'inscrire pour créer et déployer vos propres agents.' },
      { label: 'Contacter le support', href: '/support', description: 'Obtenir de l\'aide pour la configuration, la facturation ou les questions techniques.' },
    ],
    resources: 'Ressources',
    resourcesItems: [
      { label: 'Support', href: '/support' },
      { label: 'Politique de confidentialité', href: '/privacy' },
      { label: "Conditions d'utilisation", href: '/terms' },
    ],
  },
}

export default function DocumentationPage() {
  const { language } = useLanguageStore()
  const t = content[language]
  const apiDocsUrl = `${API_URL}/api/docs`

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors duration-200">
      <header className="sticky top-0 z-40 bg-white/90 dark:bg-gray-900/90 backdrop-blur-lg border-b border-gray-200 dark:border-gray-700 shadow-sm">
        <nav className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link
            to="/"
            className="flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors"
          >
            <ArrowLeftIcon className="w-5 h-5" />
            <span className="font-medium">{t.backToHome}</span>
          </Link>
          <Link to="/" className="flex items-center">
            <img
              src="/weevoice_logo.svg"
              alt="Weevoice"
              className="h-8 w-auto object-contain dark:invert dark:opacity-95"
            />
          </Link>
          <div className="w-24" aria-hidden="true" />
        </nav>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-12 sm:py-16">
        <div className="mb-12">
          <h1 className="text-4xl sm:text-5xl font-bold text-gray-900 dark:text-white tracking-tight">
            {t.title}
          </h1>
          <p className="mt-4 text-xl text-gray-600 dark:text-gray-400">
            {t.subtitle}
          </p>
        </div>

        <article className="space-y-12">
          {/* API Reference */}
          <section>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-5 pb-2 border-b border-gray-200 dark:border-gray-700 flex items-center gap-2">
              <CommandLineIcon className="w-6 h-6 text-indigo-500 dark:text-indigo-400" />
              {t.apiReference}
            </h2>
            <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-6">
              {t.apiDescription}
            </p>
            <a
              href={apiDocsUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-5 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-semibold rounded-xl shadow-md hover:shadow-lg transition-all duration-200"
            >
              <BookOpenIcon className="w-5 h-5" />
              {t.openApiDocs}
              <ArrowTopRightOnSquareIcon className="w-4 h-4" />
            </a>
          </section>

          {/* Getting Started */}
          <section>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-5 pb-2 border-b border-gray-200 dark:border-gray-700 flex items-center gap-2">
              <PlayIcon className="w-6 h-6 text-indigo-500 dark:text-indigo-400" />
              {t.gettingStarted}
            </h2>
            <ul className="space-y-4">
              {t.getStartedItems.map((item) => (
                <li key={item.href}>
                  <Link
                    to={item.href}
                    className="block p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/80 hover:border-indigo-300 dark:hover:border-indigo-600 hover:shadow-md transition-all duration-200 group"
                  >
                    <span className="font-semibold text-gray-900 dark:text-white group-hover:text-indigo-600 dark:group-hover:text-indigo-400">
                      {item.label}
                    </span>
                    <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                      {item.description}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          </section>

          {/* Resources */}
          <section>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-5 pb-2 border-b border-gray-200 dark:border-gray-700 flex items-center gap-2">
              <ChatBubbleLeftRightIcon className="w-6 h-6 text-indigo-500 dark:text-indigo-400" />
              {t.resources}
            </h2>
            <nav className="flex flex-wrap gap-3">
              {t.resourcesItems.map((item) => (
                <Link
                  key={item.href}
                  to={item.href}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-indigo-50 dark:hover:bg-indigo-900/30 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors"
                >
                  {item.label}
                  <ArrowTopRightOnSquareIcon className="w-4 h-4 opacity-70" />
                </Link>
              ))}
            </nav>
          </section>
        </article>
      </main>
    </div>
  )
}
