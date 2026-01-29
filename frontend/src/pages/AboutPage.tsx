import { Link } from 'react-router-dom'
import { useLanguageStore } from '@/store/languageStore'
import { ArrowLeftIcon, BuildingOffice2Icon, MapPinIcon, SparklesIcon } from '@heroicons/react/24/outline'

const COMPANY = {
  name: 'Exatek (SA)',
  vat: 'BE 0831.113.519',
  address: 'Rue de la Colonne 1A, 1080 Molenbeek-Saint-Jean, Belgium',
}

const content = {
  en: {
    title: 'About Us',
    backToHome: 'Back to Home',
    tagline: 'AI voice agents in French. Ultra-low latency, simple integration.',
    intro: [
      'Weevoice is an AI-powered voice and conversation platform built for businesses that want to automate and enhance customer interactions in French and other languages.',
      'We combine state-of-the-art speech and language models with a simple dashboard, so you can create, configure, and deploy voice agents in minutes—without deep technical expertise.',
    ],
    whatWeOffer: 'What We Offer',
    offer: [
      'Voice and text agents powered by advanced AI',
      'Native French support with natural pronunciation',
      'Ultra-low latency for real-time conversations',
      'Integrations with telephony, CRMs, and webhooks',
      'Knowledge bases (RAG) to ground agents in your data',
      'Usage analytics, call logs, and support tools',
    ],
    company: 'Company',
    contact: 'Contact & Support',
  },
  fr: {
    title: 'À propos',
    backToHome: "Retour à l'accueil",
    tagline: 'Agents vocaux IA en français. Latence ultra-faible, intégration simple.',
    intro: [
      "Weevoice est une plateforme vocale et conversationnelle alimentée par l'IA, conçue pour les entreprises qui souhaitent automatiser et enrichir les interactions clients en français et dans d'autres langues.",
      "Nous combinons des modèles de parole et de langage de pointe avec un tableau de bord simple, pour que vous puissiez créer, configurer et déployer des agents vocaux en quelques minutes—sans expertise technique poussée.",
    ],
    whatWeOffer: 'Ce que nous proposons',
    offer: [
      "Agents vocaux et textuels alimentés par l'IA avancée",
      "Français natif avec prononciation naturelle",
      "Latence ultra-faible pour des conversations en temps réel",
      "Intégrations téléphonie, CRM et webhooks",
      "Bases de connaissances (RAG) pour ancrer les agents dans vos données",
      "Analytiques d'usage, historiques d'appels et outils de support",
    ],
    company: 'Société',
    contact: 'Contact & support',
  },
}

export default function AboutPage() {
  const { language } = useLanguageStore()
  const t = content[language]

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
          <p className="mt-4 text-xl text-indigo-600 dark:text-indigo-400 font-medium">
            {t.tagline}
          </p>
        </div>

        <article className="space-y-12">
          <section className="space-y-4">
            {t.intro.map((paragraph, i) => (
              <p
                key={i}
                className="text-lg text-gray-700 dark:text-gray-300 leading-relaxed"
              >
                {paragraph}
              </p>
            ))}
          </section>

          <section>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6 pb-2 border-b border-gray-200 dark:border-gray-700">
              {t.whatWeOffer}
            </h2>
            <ul className="space-y-3">
              {t.offer.map((item, i) => (
                <li
                  key={i}
                  className="flex items-start gap-3 text-gray-700 dark:text-gray-300"
                >
                  <SparklesIcon className="w-5 h-5 text-indigo-500 dark:text-indigo-400 flex-shrink-0 mt-0.5" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6 pb-2 border-b border-gray-200 dark:border-gray-700">
              {t.company}
            </h2>
            <div className="rounded-2xl bg-gray-100 dark:bg-gray-800/80 p-6 sm:p-8 space-y-4">
              <div className="flex items-start gap-3">
                <BuildingOffice2Icon className="w-5 h-5 text-indigo-500 dark:text-indigo-400 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-gray-900 dark:text-white">
                    {COMPANY.name}
                  </p>
                  <p className="text-gray-600 dark:text-gray-400">
                    VAT: {COMPANY.vat}
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <MapPinIcon className="w-5 h-5 text-indigo-500 dark:text-indigo-400 shrink-0 mt-0.5" />
                <p className="text-gray-600 dark:text-gray-400">
                  {COMPANY.address}
                </p>
              </div>
              <Link
                to="/support"
                className="inline-flex mt-4 text-indigo-600 dark:text-indigo-400 font-medium hover:underline"
              >
                {t.contact} →
              </Link>
            </div>
          </section>
        </article>
      </main>
    </div>
  )
}
