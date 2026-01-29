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
    title: 'Terms of Service',
    lastUpdated: 'Last updated',
    backToHome: 'Back to Home',
    intro: [
      'Welcome to Weevoice. These Terms of Service («Terms») govern your access to and use of the Weevoice platform and related services (the «Service») operated by Exatek (SA) («we», «us», «our»). By accessing or using the Service, you agree to be bound by these Terms. If you do not agree, please do not use the Service.',
    ],
    sections: [
      {
        id: 'acceptance',
        title: 'Acceptance of Terms',
        body: [
          'By creating an account or using the Service, you confirm that you have read, understood, and agree to these Terms and our Privacy Policy. If you are using the Service on behalf of an organisation, you represent that you have authority to bind that organisation.',
        ],
      },
      {
        id: 'description',
        title: 'Description of Service',
        body: [
          'Weevoice provides a platform for creating, configuring, and deploying AI-powered voice and text agents. The Service includes dashboards, APIs, telephony integration, knowledge bases, analytics, and related features. We may update, suspend, or discontinue parts of the Service with reasonable notice where practicable.',
        ],
      },
      {
        id: 'account',
        title: 'Account and Registration',
        body: [
          'You must provide accurate and complete registration information and keep your account secure. You are responsible for all activity under your account. You must notify us promptly of any unauthorised use. We may require verification (e.g. email) and may suspend or terminate accounts that violate these Terms or for other legitimate reasons.',
        ],
      },
      {
        id: 'acceptable-use',
        title: 'Acceptable Use',
        body: [
          'You agree not to use the Service for any unlawful, harmful, or abusive purpose. You must not: (a) violate any applicable law or third-party rights; (b) distribute malware, spam, or harmful content; (c) attempt to gain unauthorised access to our or others’ systems or data; (d) use the Service to harass, defame, or harm others; (e) resell or sublicense the Service except as permitted; or (f) use the Service in a way that could harm, overload, or impair the Service or our infrastructure. We may suspend or terminate access for violations.',
        ],
      },
      {
        id: 'content-and-ip',
        title: 'Content and Intellectual Property',
        body: [
          'You retain ownership of content you submit (e.g. prompts, documents, configurations). You grant us a licence to use, host, and process that content as necessary to provide and improve the Service. Our Service, including software, designs, and branding, remains our property or our licensors’. You may not copy, modify, or create derivative works of our Service except as expressly permitted.',
        ],
      },
      {
        id: 'payment',
        title: 'Payment and Billing',
        body: [
          'Paid plans and usage-based charges are billed according to the pricing in effect at the time. You agree to pay all fees and applicable taxes. Fees are generally non-refundable unless required by law or as stated in our refund policy. We may change pricing with reasonable notice. Failure to pay may result in suspension or termination of the Service.',
        ],
      },
      {
        id: 'termination',
        title: 'Termination',
        body: [
          'You may stop using the Service and close your account at any time. We may suspend or terminate your access for breach of these Terms, non-payment, or for operational or legal reasons, with notice where reasonably practicable. Upon termination, your right to use the Service ceases. Provisions that by their nature should survive (e.g. liability, indemnity, governing law) will survive termination.',
        ],
      },
      {
        id: 'disclaimers',
        title: 'Disclaimers',
        body: [
          'The Service is provided «as is» and «as available». We disclaim all warranties, express or implied, including merchantability and fitness for a particular purpose. We do not warrant that the Service will be uninterrupted, error-free, or secure. AI-generated outputs may be inaccurate; you are responsible for reviewing and using them appropriately.',
        ],
      },
      {
        id: 'limitation',
        title: 'Limitation of Liability',
        body: [
          'To the maximum extent permitted by law, we and our affiliates shall not be liable for any indirect, incidental, special, consequential, or punitive damages, or for loss of profits, data, or goodwill, arising out of or in connection with the Service or these Terms. Our total liability for any claims arising from or related to the Service or these Terms shall not exceed the amount you paid us in the twelve (12) months preceding the claim. Some jurisdictions do not allow certain limitations; in such cases our liability is limited to the maximum permitted by law.',
        ],
      },
      {
        id: 'indemnification',
        title: 'Indemnification',
        body: [
          'You agree to indemnify and hold harmless Exatek (SA), its affiliates, and their officers, directors, employees, and agents from and against any claims, damages, losses, liabilities, and expenses (including reasonable legal fees) arising out of or related to your use of the Service, your content, your violation of these Terms, or your violation of any third-party rights.',
        ],
      },
      {
        id: 'governing-law',
        title: 'Governing Law and Disputes',
        body: [
          'These Terms are governed by the laws of Belgium. Any dispute arising out of or relating to these Terms or the Service shall be subject to the exclusive jurisdiction of the courts of Belgium, without prejudice to your statutory rights as a consumer in your country of residence.',
        ],
      },
      {
        id: 'changes',
        title: 'Changes to the Terms',
        body: [
          'We may modify these Terms from time to time. We will notify you of material changes by posting the updated Terms on the Service and updating the «Last updated» date, or by email where appropriate. Your continued use of the Service after the effective date of changes constitutes acceptance of the revised Terms. If you do not agree, you must stop using the Service.',
        ],
      },
      {
        id: 'contact',
        title: 'Contact',
        body: [
          `For questions about these Terms, please contact us at the address below or via our support channel. Exatek (SA), ${COMPANY.address}, VAT: ${COMPANY.vat}.`,
        ],
      },
    ],
  },
  fr: {
    title: "Conditions d'utilisation",
    lastUpdated: 'Dernière mise à jour',
    backToHome: "Retour à l'accueil",
    intro: [
      "Bienvenue sur Weevoice. Les présentes Conditions d'utilisation (« Conditions ») régissent votre accès et votre utilisation de la plateforme Weevoice et des services associés (le « Service ») exploités par Exatek (SA) (« nous », « notre »). En accédant au Service ou en l'utilisant, vous acceptez d'être lié par ces Conditions. Dans le cas contraire, veuillez ne pas utiliser le Service.",
    ],
    sections: [
      {
        id: 'acceptance',
        title: "Acceptation des conditions",
        body: [
          "En créant un compte ou en utilisant le Service, vous confirmez avoir lu, compris et accepté ces Conditions et notre Politique de confidentialité. Si vous utilisez le Service au nom d'une organisation, vous déclarez avoir l'autorité d'engager cette organisation.",
        ],
      },
      {
        id: 'description',
        title: "Description du service",
        body: [
          "Weevoice fournit une plateforme pour créer, configurer et déployer des agents vocaux et textuels alimentés par l'IA. Le Service comprend tableaux de bord, API, intégration téléphonie, bases de connaissances, analytiques et fonctionnalités associées. Nous pouvons mettre à jour, suspendre ou interrompre des parties du Service avec un préavis raisonnable lorsque cela est possible.",
        ],
      },
      {
        id: 'account',
        title: 'Compte et inscription',
        body: [
          "Vous devez fournir des informations d'inscription exactes et complètes et maintenir la sécurité de votre compte. Vous êtes responsable de toute activité sous votre compte. Vous devez nous informer rapidement de toute utilisation non autorisée. Nous pouvons exiger une vérification (ex. email) et suspendre ou résilier les comptes en violation de ces Conditions ou pour d'autres motifs légitimes.",
        ],
      },
      {
        id: 'acceptable-use',
        title: "Usage acceptable",
        body: [
          "Vous vous engagez à ne pas utiliser le Service à des fins illégales, nuisibles ou abusives. Vous ne devez pas : (a) violer la loi ou les droits de tiers ; (b) distribuer des logiciels malveillants, du spam ou du contenu nuisible ; (c) tenter d'accéder sans autorisation à nos systèmes ou données ou à ceux de tiers ; (d) utiliser le Service pour harceler, diffamer ou nuire ; (e) revendre ou sous-licencier le Service sauf autorisation ; (f) utiliser le Service de manière à nuire, surcharger ou compromettre le Service ou notre infrastructure. Nous pouvons suspendre ou résilier l'accès en cas de violation.",
        ],
      },
      {
        id: 'content-and-ip',
        title: 'Contenu et propriété intellectuelle',
        body: [
          "Vous conservez la propriété du contenu que vous soumettez (ex. prompts, documents, configurations). Vous nous accordez une licence pour utiliser, héberger et traiter ce contenu selon les besoins du Service. Notre Service, y compris logiciels, designs et marques, reste notre propriété ou celle de nos concédants. Vous ne pouvez pas copier, modifier ou créer des œuvres dérivées du Service sauf autorisation expresse.",
        ],
      },
      {
        id: 'payment',
        title: 'Paiement et facturation',
        body: [
          "Les formules payantes et les frais à l'usage sont facturés selon les tarifs en vigueur. Vous acceptez de payer tous les frais et taxes applicables. Les frais sont en général non remboursables sauf disposition légale ou politique de remboursement. Nous pouvons modifier les tarifs avec un préavis raisonnable. Le défaut de paiement peut entraîner la suspension ou la résiliation du Service.",
        ],
      },
      {
        id: 'termination',
        title: 'Résiliation',
        body: [
          "Vous pouvez cesser d'utiliser le Service et fermer votre compte à tout moment. Nous pouvons suspendre ou résilier votre accès en cas de violation de ces Conditions, de non-paiement ou pour des raisons opérationnelles ou légales, avec préavis lorsque raisonnablement possible. À la résiliation, votre droit d'utilisation du Service cesse. Les dispositions qui par nature doivent survivre (ex. responsabilité, indemnisation, droit applicable) restent en vigueur.",
        ],
      },
      {
        id: 'disclaimers',
        title: 'Exclusion de garantie',
        body: [
          "Le Service est fourni « en l'état » et « selon disponibilité ». Nous excluons toutes garanties, expresses ou implicites, y compris de qualité marchande et d'adéquation à un usage particulier. Nous ne garantissons pas que le Service sera ininterrompu, exempt d'erreurs ou sécurisé. Les sorties générées par l'IA peuvent être inexactes ; vous êtes responsable de les vérifier et de les utiliser de manière appropriée.",
        ],
      },
      {
        id: 'limitation',
        title: 'Limitation de responsabilité',
        body: [
          "Dans la limite maximale permise par la loi, nous et nos affiliés ne serons pas responsables des dommages indirects, accessoires, spéciaux, consécutifs ou punitifs, ou des pertes de profits, de données ou de clientèle, découlant du Service ou de ces Conditions. Notre responsabilité totale pour toute réclamation liée au Service ou à ces Conditions ne dépassera pas le montant que vous nous avez payé au cours des douze (12) mois précédant la réclamation. Certaines juridictions n'autorisent pas certaines limitations ; dans ce cas notre responsabilité est limitée au maximum permis par la loi.",
        ],
      },
      {
        id: 'indemnification',
        title: 'Indemnisation',
        body: [
          "Vous acceptez d'indemniser et de dégager de toute responsabilité Exatek (SA), ses affiliés et leurs dirigeants, administrateurs, employés et mandataires à l'égard de toute réclamation, dommage, perte, responsabilité et frais (y compris honoraires d'avocat raisonnables) découlant de votre utilisation du Service, de votre contenu, de votre violation de ces Conditions ou des droits de tiers.",
        ],
      },
      {
        id: 'governing-law',
        title: 'Droit applicable et litiges',
        body: [
          "Ces Conditions sont régies par le droit belge. Tout litige découlant de ces Conditions ou du Service relève de la compétence exclusive des tribunaux belges, sans préjudice de vos droits légaux en tant que consommateur dans votre pays de résidence.",
        ],
      },
      {
        id: 'changes',
        title: 'Modifications des conditions',
        body: [
          "Nous pouvons modifier ces Conditions de temps à autre. Nous vous informerons des modifications importantes en publiant les Conditions mises à jour sur le Service et en mettant à jour la date « Dernière mise à jour », ou par email le cas échéant. Votre poursuite de l'utilisation du Service après la date d'effet des modifications constitue une acceptation des Conditions révisées. Si vous n'acceptez pas, vous devez cesser d'utiliser le Service.",
        ],
      },
      {
        id: 'contact',
        title: 'Contact',
        body: [
          `Pour toute question concernant ces Conditions, contactez-nous à l'adresse ci-dessous ou via notre support. Exatek (SA), ${COMPANY.address}, TVA : ${COMPANY.vat}.`,
        ],
      },
    ],
  },
}

export default function TermsOfServicePage() {
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
              {isFr ? 'Éditeur du service' : 'Service provider'}
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
