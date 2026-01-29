import { Link } from 'react-router-dom'
import { useLanguageStore } from '@/store/languageStore'
import { ArrowLeftIcon } from '@heroicons/react/24/outline'

const COMPANY = {
  name: 'Exatek (SA)',
  vat: 'BE 0831.113.519',
  address: 'Rue de la Colonne 1A, 1080 Molenbeek-Saint-Jean, Belgium',
}

const content = {
  en: {
    title: 'Privacy Policy',
    lastUpdated: 'Last updated',
    backToHome: 'Back to Home',
    intro: [
      'Weevoice («we», «us», «our») operates the Weevoice platform and related services (the «Service»). This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our Service.',
      'By accessing or using the Service, you agree to this Privacy Policy. If you do not agree, please do not use the Service.',
    ],
    sections: [
      {
        id: 'data-we-collect',
        title: 'Information We Collect',
        body: [
          'We collect information you provide directly (account registration, profile, support tickets), usage data (agents, calls, usage metrics), and technical data (IP address, browser, device). For voice interactions we process audio, transcripts, and call metadata to provide and improve the Service. Payment and billing data are processed by our payment provider in accordance with their privacy policy.',
        ],
      },
      {
        id: 'how-we-use',
        title: 'How We Use Your Information',
        body: [
          'We use your information to provide, maintain, and improve the Service; to process transactions and send related information; to send technical notices and support messages; to respond to your requests; to monitor and analyse trends and usage; and to protect the security and integrity of the Service. Voice and conversation data may be used to train or improve our AI models only in accordance with your settings and applicable law.',
        ],
      },
      {
        id: 'sharing',
        title: 'Sharing and Disclosure',
        body: [
          'We may share information with service providers (hosting, analytics, payment processing, communications), with your consent (e.g. CRM or webhook endpoints you configure), or when required by law or to protect rights and safety. We do not sell your personal data.',
        ],
      },
      {
        id: 'security',
        title: 'Security',
        body: [
          'We implement appropriate technical and organisational measures to protect your data, including encryption in transit and at rest, access controls, and regular assessments. No method of transmission over the Internet is 100% secure; we strive to use commercially acceptable means to protect your information.',
        ],
      },
      {
        id: 'your-rights',
        title: 'Your Rights',
        body: [
          'Depending on your location (including under the GDPR if you are in the EEA), you may have the right to access, correct, delete, or port your personal data, to restrict or object to processing, and to lodge a complaint with a supervisory authority. You can exercise many of these rights through your account settings or by contacting us.',
        ],
      },
      {
        id: 'cookies',
        title: 'Cookies and Similar Technologies',
        body: [
          'We use cookies and similar technologies for authentication, preferences, security, and analytics. You can control cookies through your browser settings.',
        ],
      },
      {
        id: 'retention',
        title: 'Data Retention',
        body: [
          'We retain your information for as long as your account is active or as needed to provide the Service, comply with legal obligations, resolve disputes, and enforce our agreements. Call and conversation data may be retained according to your configuration and our retention policy.',
        ],
      },
      {
        id: 'contact',
        title: 'Contact Us',
        body: [
          `For privacy-related questions or to exercise your rights, please contact us at the address below or via our support channel. Data controller: ${COMPANY.name}, ${COMPANY.address}, VAT: ${COMPANY.vat}.`,
        ],
      },
    ],
  },
  fr: {
    title: 'Politique de confidentialité',
    lastUpdated: 'Dernière mise à jour',
    backToHome: "Retour à l'accueil",
    intro: [
      'Weevoice (« nous », « notre ») exploite la plateforme Weevoice et les services associés (le « Service »). Cette Politique de confidentialité explique comment nous collectons, utilisons, divulguons et protégeons vos informations lorsque vous utilisez notre Service.',
      "En accédant au Service ou en l'utilisant, vous acceptez cette Politique. Si vous n'êtes pas d'accord, veuillez ne pas utiliser le Service.",
    ],
    sections: [
      {
        id: 'data-we-collect',
        title: 'Informations que nous collectons',
        body: [
          "Nous collectons les informations que vous fournissez directement (inscription, profil, tickets de support), les données d'utilisation (agents, appels, métriques) et les données techniques (adresse IP, navigateur, appareil). Pour les interactions vocales, nous traitons l'audio, les transcriptions et les métadonnées d'appel pour fournir et améliorer le Service. Les données de paiement sont traitées par notre prestataire conformément à sa politique de confidentialité.",
        ],
      },
      {
        id: 'how-we-use',
        title: "Utilisation de vos informations",
        body: [
          "Nous utilisons vos informations pour fournir, maintenir et améliorer le Service ; traiter les transactions ; envoyer des avis techniques et des messages de support ; répondre à vos demandes ; analyser les tendances et l'utilisation ; et protéger la sécurité du Service. Les données vocales et de conversation peuvent être utilisées pour entraîner ou améliorer nos modèles d'IA conformément à vos paramètres et à la loi.",
        ],
      },
      {
        id: 'sharing',
        title: 'Partage et divulgation',
        body: [
          "Nous pouvons partager des informations avec des prestataires (hébergement, analytique, paiement, communications), avec votre consentement (ex. webhooks ou CRM que vous configurez), ou lorsque la loi l'exige ou pour protéger les droits et la sécurité. Nous ne vendons pas vos données personnelles.",
        ],
      },
      {
        id: 'security',
        title: 'Sécurité',
        body: [
          "Nous mettons en œuvre des mesures techniques et organisationnelles appropriées (chiffrement en transit et au repos, contrôles d'accès, évaluations régulières). Aucune transmission sur Internet n'est totalement sécurisée ; nous nous efforçons d'utiliser des moyens commercialement acceptables pour protéger vos informations.",
        ],
      },
      {
        id: 'your-rights',
        title: 'Vos droits',
        body: [
          "Selon votre lieu de résidence (dont le RGPD si vous êtes dans l'EEE), vous pouvez avoir le droit d'accéder, rectifier, supprimer ou exporter vos données, de restreindre ou vous opposer au traitement, et de déposer une réclamation auprès d'une autorité de contrôle. Vous pouvez exercer nombre de ces droits via les paramètres de votre compte ou en nous contactant.",
        ],
      },
      {
        id: 'cookies',
        title: 'Cookies et technologies similaires',
        body: [
          "Nous utilisons des cookies pour l'authentification, les préférences, la sécurité et l'analytique. Vous pouvez les gérer via les paramètres de votre navigateur.",
        ],
      },
      {
        id: 'retention',
        title: 'Conservation des données',
        body: [
          "Nous conservons vos informations tant que votre compte est actif ou selon les besoins du Service, des obligations légales, du règlement des litiges et de l'application de nos accords. Les données d'appels et de conversations peuvent être conservées selon votre configuration et notre politique de conservation.",
        ],
      },
      {
        id: 'contact',
        title: 'Nous contacter',
        body: [
          `Pour toute question relative à la confidentialité ou pour exercer vos droits, contactez-nous à l'adresse ci-dessous ou via notre support. Responsable du traitement : ${COMPANY.name}, ${COMPANY.address}, TVA : ${COMPANY.vat}.`,
        ],
      },
    ],
  },
}

export default function PrivacyPolicyPage() {
  const { language } = useLanguageStore()
  const t = content[language]
  const isFr = language === 'fr'

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors duration-200">
      {/* Header */}
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

      {/* Content */}
      <main className="max-w-4xl mx-auto px-6 py-12 sm:py-16">
        <div className="mb-12">
          <p className="text-sm font-medium text-indigo-600 dark:text-indigo-400 uppercase tracking-wider mb-2">
            Legal
          </p>
          <h1 className="text-4xl sm:text-5xl font-bold text-gray-900 dark:text-white tracking-tight">
            {t.title}
          </h1>
          <p className="mt-4 text-sm text-gray-500 dark:text-gray-400">
            {t.lastUpdated}: January 2025
          </p>
        </div>

        <article className="space-y-14">
          {/* Introduction */}
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

          {/* Sections */}
          {t.sections.map((section) => (
            <section
              key={section.id}
              id={section.id}
              className="scroll-mt-24"
            >
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-5 pb-2 border-b border-gray-200 dark:border-gray-700">
                {section.title}
              </h2>
              <div className="space-y-4">
                {section.body.map((paragraph, i) => (
                  <p
                    key={i}
                    className="text-gray-700 dark:text-gray-300 leading-relaxed"
                  >
                    {paragraph}
                  </p>
                ))}
              </div>
            </section>
          ))}
        </article>

        {/* Company block */}
        <div className="mt-20 pt-12 border-t border-gray-200 dark:border-gray-700">
          <div className="rounded-2xl bg-gray-100 dark:bg-gray-800/80 p-6 sm:p-8">
            <p className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3">
              {isFr ? 'Responsable du traitement' : 'Data controller'}
            </p>
            <p className="font-semibold text-gray-900 dark:text-white">
              {COMPANY.name}
            </p>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              {COMPANY.address}
            </p>
            <p className="text-gray-600 dark:text-gray-400">VAT: {COMPANY.vat}</p>
            <Link
              to="/support"
              className="inline-flex mt-4 text-indigo-600 dark:text-indigo-400 font-medium hover:underline"
            >
              {isFr ? 'Contact & support' : 'Contact & support'}
            </Link>
          </div>
        </div>
      </main>
    </div>
  )
}
