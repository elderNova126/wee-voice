import { useLanguageStore } from '@/store/languageStore'

export type Language = 'fr' | 'en'

export interface Translations {
  // Common
  common: {
    save: string
    cancel: string
    delete: string
    edit: string
    create: string
    update: string
    search: string
    loading: string
    error: string
    success: string
    confirm: string
    close: string
    back: string
    next: string
    previous: string
    actions: string
    status: string
    date: string
    time: string
    name: string
    description: string
    email: string
    password: string
    login: string
    logout: string
    register: string
    settings: string
    profile: string
    dashboard: string
    yes: string
    no: string
  }

  // Navigation
  nav: {
    dashboard: string
    agents: string
    libraries: string
    calls: string
    integrations: string
    phoneNumbers: string
    callbacks: string
    apiKeys: string
    support: string
    settings: string
    admin: string
    billing: string
    usage: string
    security: string
  }

  // Dashboard
  dashboard: {
    title: string
    welcome: string
    totalAgents: string
    totalCalls: string
    activeCalls: string
    recentCalls: string
  }

  // Agents
  agents: {
    title: string
    createAgent: string
    editAgent: string
    deleteAgent: string
    agentName: string
    agentDescription: string
    systemPrompt: string
    greeting: string
    language: string
    voiceId: string
    voiceGender: string
    isActive: string
    isPublic: string
    noAgents: string
    createFirstAgent: string
  }

  // Libraries
  libraries: {
    title: string
    publicLibraries: string
    myLibraries: string
    createLibrary: string
    createPublicLibrary: string
    editLibrary: string
    deleteLibrary: string
    useTemplate: string
    saveToMyLibraries: string
    category: string
    allCategories: string
    searchPlaceholder: string
    noLibraries: string
    createNewAgent: string
    applyToAgent: string
    selectAgent: string
    selectOption: string
    createNewAgentOption: string
    applyToExistingAgent: string
    libraryUpdated: string
    libraryCreated: string
    libraryDeleted: string
    librarySaved: string
  }

  // Calls
  calls: {
    title: string
    callHistory: string
    totalCalls: string
    duration: string
    cost: string
    status: string
    from: string
    to: string
    date: string
    details: string
    transcript: string
    summary: string
    messages: string
    sendEmail: string
    emailSent: string
    favorite: string
    unfavorite: string
    noCalls: string
    loading: string
  }

  // Phone Numbers
  phoneNumbers: {
    title: string
    subtitle: string
    managePhoneNumbers: string
    addPhoneNumber: string
    editPhoneNumber: string
    deletePhoneNumber: string
    phoneNumber: string
    agent: string
    status: string
    noPhoneNumbers: string
    requestNewNumber: string
    addExistingNumber: string
    noPhoneNumbersDesc: string
    monthly: string
    perMinute: string
    pbxRouting: string
    extension: string
    auto: string
    businessHours: string
    afterHours: string
    pbxNotConfigured: string
    pbxNotConfiguredDesc: string
    uploadDocuments: string
    changeAgent: string
    assignAgent: string
    configurePBX: string
    verificationDocuments: string
    noDocumentsUploaded: string
    addExistingPhoneNumber: string
    addExistingDesc: string
    phoneNumberLabel: string
    phoneNumberPlaceholder: string
    phoneNumberHelper: string
    countryCode: string
    businessName: string
    businessNameOptional: string
    businessNamePlaceholder: string
    adding: string
    addPhoneNumberButton: string
    requestNewPhoneNumber: string
    businessType: string
    businessAddress: string
    company: string
    individual: string
    uploadVerificationDocument: string
    documentType: string
    file: string
    uploadDocument: string
    uploadDocumentButton: string
    uploading: string
    selectAnAgent: string
    noAgentsAvailable: string
    assignAgentButton: string
    pbxConfiguration: string
    timezone: string
    openTime: string
    closeTime: string
    days: string
    menuOptions: string
    key: string
    label: string
    destinationType: string
    destinationValue: string
    destination: string
    addMenuOption: string
    afterHoursRouting: string
    message: string
    savePBX: string
    saving: string
    assignAgentToPhoneNumber: string
    activeDays: string
    optional: string
    requesting: string
    assigning: string
    phoneNumberPlaceholderRequest: string
    createAgentFirst: string
    uploadDocumentsFor: string
    speakToSales: string
    option: string
    chooseAgentDescription: string
    notConfigured: string
    connectToAIAgent: string
    sendToVoicemail: string
    forwardTo: string
    externalNumber: string
    externalDestination: string
    customRouting: string
    active: string
    inactive: string
    pendingVerification: string
    configured: string
    notConfiguredStatus: string
    unknownAgent: string
    phoneNumberAddedSuccess: string
    phoneNumberRequestedSuccess: string
    documentUploadedSuccess: string
    agentAssignedSuccess: string
    pbxSavedSuccess: string
    deleteConfirm: string
    deleteSuccess: string
    deleteError: string
    createSuccess: string
    createError: string
    updateSuccess: string
    updateError: string
  }

  // API Keys
  apiKeys: {
    title: string
    createApiKey: string
    deleteApiKey: string
    keyName: string
    apiKey: string
    createdAt: string
    lastUsed: string
    noApiKeys: string
  }

  // Support
  support: {
    title: string
    createTicket: string
    tickets: string
    subject: string
    message: string
    status: string
    priority: string
    createdAt: string
    noTickets: string
  }

  // Billing
  billing: {
    title: string
    currentPlan: string
    credits: string
    usage: string
    paymentMethod: string
    invoices: string
    noInvoices: string
  }

  // Settings
  settings: {
    title: string
    general: string
    security: string
    notifications: string
    language: string
    theme: string
    light: string
    dark: string
    system: string
  }

  // Auth
  auth: {
    login: string
    logout: string
    register: string
    email: string
    password: string
    confirmPassword: string
    fullName: string
    loginSuccess: string
    loginError: string
    registerSuccess: string
    registerError: string
    noAccount: string
    createAccount: string
    hasAccount: string
    loginHere: string
    connecting: string
    connect: string
  }

  // Agent Form
  agentForm: {
    backToAgents: string
    createNewAgent: string
    editAgent: string
    configureDetails: string
    agentName: string
    agentNamePlaceholder: string
    description: string
    descriptionPlaceholder: string
    systemPrompt: string
    systemPromptPlaceholder: string
    greeting: string
    greetingPlaceholder: string
    language: string
    voiceId: string
    voiceGender: string
    isActive: string
    isPublic: string
    ragEnabled: string
    agentCreated: string
    agentUpdated: string
    agentCreateError: string
    agentUpdateError: string
    saveAgentFirst: string
    uploadDocument: string
    addWebsite: string
    websiteUrl: string
    documents: string
    noDocuments: string
    deleteDocument: string
    processing: string
    completed: string
    failed: string
  }

  // Dashboard
  dashboard: {
    welcomeMessage: string
    totalAgentsSubtitle: string
    totalCallsSubtitle: string
    totalMinutesSubtitle: string
    totalCostSubtitle: string
    statsLoadError: string
  }

  // Agents Page
  agentsPage: {
    title: string
    subtitle: string
    newAgent: string
    noAgentsYet: string
    noAgentsDescription: string
    createAgent: string
    active: string
    inactive: string
    private: string
    public: string
    noDescription: string
    test: string
    edit: string
    delete: string
    deleteConfirm: string
    deleteSuccess: string
    deleteError: string
    loadError: string
  }

  // Calls Page
  callsPage: {
    callHistory: string
    allCalls: string
    favorites: string
    filters: string
    status: string
    allStatuses: string
    actionRequired: string
    searchPlaceholder: string
    noCallsFound: string
    bulkDelete: string
    bulkFavorite: string
    bulkUnfavorite: string
    deleteConfirm: string
    deleteSuccess: string
    deleteError: string
    favoriteSuccess: string
    unfavoriteSuccess: string
    favoriteError: string
    page: string
    of: string
    showing: string
    results: string
    minutes: string
    cost: string
    viewDetails: string
    noSummary: string
    noTranscript: string
    keyPoints: string
    actionItems: string
    sentiment: string
    callbackRequested: string
    sendEmail: string
    emailSent: string
    emailError: string
    close: string
  }

  // Categories
  categories: {
    realEstate: string
    customerService: string
    sales: string
    support: string
    marketing: string
    hr: string
    healthcare: string
    education: string
    finance: string
    legal: string
    general: string
  }

  // Register
  register: {
    title: string
    fullName: string
    confirmPassword: string
    passwordMismatch: string
    passwordMinLength: string
    passwordMaxLength: string
    passwordHint: string
    creating: string
    createAccount: string
    hasAccount: string
    loginHere: string
    success: string
    error: string
  }

  // Phone Numbers
  phoneNumbers: {
    subtitle: string
    addPhoneNumber: string
    editPhoneNumber: string
    deletePhoneNumber: string
    phoneNumber: string
    agent: string
    status: string
    noPhoneNumbers: string
    deleteConfirm: string
    deleteSuccess: string
    deleteError: string
    createSuccess: string
    createError: string
    updateSuccess: string
    updateError: string
  }

  // API Keys
  apiKeys: {
    subtitle: string
    createApiKey: string
    deleteApiKey: string
    keyName: string
    apiKey: string
    createdAt: string
    lastUsed: string
    noApiKeys: string
    deleteConfirm: string
    deleteSuccess: string
    deleteError: string
    createSuccess: string
    createError: string
    copySuccess: string
    never: string
  }

  // Support
  support: {
    subtitle: string
    createTicket: string
    tickets: string
    subject: string
    message: string
    status: string
    priority: string
    createdAt: string
    noTickets: string
    createSuccess: string
    createError: string
    low: string
    medium: string
    high: string
    open: string
    closed: string
    inProgress: string
  }

  // Billing
  billing: {
    subtitle: string
    currentPlan: string
    credits: string
    usage: string
    paymentMethod: string
    invoices: string
    noInvoices: string
    addPaymentMethod: string
    updatePaymentMethod: string
    noPaymentMethod: string
  }

  // Profile
  profile: {
    title: string
    subtitle: string
    personalInfo: string
    updateSuccess: string
    updateError: string
    changePassword: string
    currentPassword: string
    newPassword: string
    confirmNewPassword: string
    passwordChanged: string
    passwordError: string
  }

  // Security
  security: {
    title: string
    subtitle: string
    twoFactor: string
    apiKeys: string
    sessions: string
    loginHistory: string
  }

  // Usage
  usage: {
    title: string
    subtitle: string
    period: string
    last7Days: string
    last30Days: string
    last90Days: string
    thisMonth: string
    lastMonth: string
    calls: string
    minutes: string
    cost: string
  }

  // Callbacks
  callbacks: {
    title: string
    subtitle: string
    noCallbacks: string
    scheduled: string
    completed: string
    cancelled: string
    pending: string
    contacted: string
    all: string
    callbackRequests: string
    manageCallbacks: string
    noCallbackRequests: string
    noCallbackRequestsDesc: string
    priority: string
    urgent: string
    high: string
    normal: string
    low: string
    status: string
    callerName: string
    callerPhone: string
    callerEmail: string
    preferredCallbackTime: string
    notes: string
    resolution: string
    assignedTo: string
    viewCall: string
    update: string
    updateCallbackRequest: string
    assignedToPlaceholder: string
    notesPlaceholder: string
    resolutionPlaceholder: string
    updating: string
    updateButton: string
    updateSuccess: string
    updateError: string
    createdAt: string
  }

  // Integrations
  integrations: {
    title: string
    subtitle: string
    noIntegrations: string
    addIntegration: string
    editIntegration: string
    deleteIntegration: string
    newIntegration: string
    createIntegration: string
    allTypes: string
    allStatuses: string
    active: string
    inactive: string
    error: string
    pendingAuth: string
    testConnection: string
    syncData: string
    activate: string
    deactivate: string
    lastSynced: string
    deleteConfirm: string
    deleteSuccess: string
    deleteError: string
    testSuccess: string
    testError: string
    syncSuccess: string
    syncError: string
    activateSuccess: string
    activateError: string
    loadError: string
    backToIntegrations: string
    newIntegrationTitle: string
    editIntegrationTitle: string
    name: string
    namePlaceholder: string
    description: string
    descriptionPlaceholder: string
    integrationType: string
    selectType: string
    provider: string
    selectProvider: string
    configuration: string
    headersJson: string
    credentialsWarning: string
    saving: string
    updateIntegration: string
    createIntegrationButton: string
    updateSuccess: string
    createSuccess: string
    saveError: string
    loadIntegrationError: string
    typeCalendar: string
    typeEmail: string
    typeContactManagement: string
    typeDatabase: string
    typeCRM: string
    typeAccounting: string
    typeOther: string
  }

  // Admin
  admin: {
    overview: string
    users: string
    agents: string
    support: string
    overviewTitle: string
    overviewSubtitle: string
    usersTitle: string
    agentsTitle: string
    supportTitle: string
    totalUsers: string
    activeUsers: string
    pendingUsers: string
    totalAgents: string
    activeAgents: string
    publicAgents: string
    totalCalls: string
    openTickets: string
    usage: string
    revenue: string
    recentUsers: string
    recentAgents: string
    recentTickets: string
    approved: string
    pending: string
    active: string
    inactive: string
    public: string
    private: string
    approve: string
    reject: string
    activate: string
    deactivate: string
    makeAdmin: string
    removeAdmin: string
    approveSuccess: string
    rejectSuccess: string
    activateSuccess: string
    deactivateSuccess: string
    makeAdminSuccess: string
    removeAdminSuccess: string
  }

  // Dashboard Quick Actions
  quickActions: {
    createAgent: string
    createAgentDesc: string
    manageApiKeys: string
    manageApiKeysDesc: string
    tryDemo: string
    tryDemoDesc: string
  }

  // Agent Documents
  agentDocuments: {
    title: string
    backToAgents: string
    agent: string
    ragEnabled: string
    addKnowledgeSources: string
    uploadPdfDocument: string
    clickToUpload: string
    pdfFilesOnly: string
    chooseFile: string
    scrapeWebsite: string
    websiteUrlPlaceholder: string
    scrape: string
    howItWorks: string
    howItWorksDesc: string
    uploadedDocuments: string
    noDocumentsUploaded: string
    source: string
    size: string
    pages: string
    chunks: string
    added: string
    processed: string
    deleteDocument: string
    deleteConfirm: string
    onlyPdfSupported: string
    fileSizeLimit: string
    uploadingFile: string
    processingEmbeddings: string
    scrapingWebsite: string
    enterWebsiteUrl: string
    enterValidUrl: string
    uploadSuccess: string
    uploadError: string
    deleteSuccess: string
    deleteError: string
    loadError: string
    toggleRAGError: string
    completed: string
    processing: string
    failed: string
    pending: string
  }

  // Agent Embed
  agentEmbed: {
    title: string
    backToAgents: string
    embedConfiguration: string
    enableEmbed: string
    widgetColor: string
    widgetPosition: string
    greetingMessage: string
    allowedDomains: string
    addDomain: string
    domainPlaceholder: string
    embedCode: string
    copyCode: string
    codeCopied: string
    saveConfig: string
    saving: string
    saveSuccess: string
    saveError: string
    bottomRight: string
    bottomLeft: string
    topRight: string
    topLeft: string
  }

  // Call Detail
  callDetail: {
    backToCalls: string
    callDetails: string
    generateSummary: string
    regenerating: string
    regenerateSummary: string
    generating: string
    summaryGenerated: string
    summaryError: string
    callNotFound: string
    overview: string
    transcript: string
    duration: string
    cost: string
    status: string
    callSummary: string
    sentiment: string
    detectedActions: string
    keyPoints: string
    actionItems: string
    conversation: string
    user: string
    agent: string
    fullTranscript: string
    transcriptNotAvailable: string
  }

  // Public Agent
  publicAgent: {
    agentNotFound: string
    agentInactive: string
    loadError: string
    connect: string
    disconnect: string
    connecting: string
    disconnecting: string
    recording: string
    stop: string
    sendMessage: string
    sending: string
    messagePlaceholder: string
    disconnectFirst: string
  }

  // Demo
  demo: {
    title: string
    selectAgent: string
    noAgentsAvailable: string
    loadError: string
    connect: string
    disconnect: string
    connecting: string
    disconnecting: string
    recording: string
    stop: string
    sendMessage: string
    sending: string
    messagePlaceholder: string
    disconnectFirst: string
  }

  // Admin Support
  adminSupport: {
    title: string
    subtitle: string
    searchPlaceholder: string
    allStatuses: string
    allPriorities: string
    open: string
    inProgress: string
    resolved: string
    closed: string
    low: string
    medium: string
    high: string
    urgent: string
    statusUpdated: string
    priorityUpdated: string
    updateError: string
    loadError: string
    noTickets: string
    ticketNumber: string
    subject: string
    name: string
    email: string
    category: string
    createdAt: string
    updatedAt: string
    responses: string
    lastResponse: string
    never: string
    updateStatus: string
    updatePriority: string
  }

  // Landing
  landing: {
    agentsPublics: string
    demo: string
    commencer: string
    tableauDeBord: string
    deconnexion: string
    agentsVocaux: string
    intelligents: string
    enFrancais: string
    heroDescription: string
    commencerGratuitement: string
    essayerDemo: string
    latenceMoyenne: string
    disponibilite: string
    langues: string
    clients: string
    fonctionnalitesPuissantes: string
    fonctionnalitesDesc: string
    latenceUltraFaible: string
    latenceDesc: string
    francaisNatif: string
    francaisDesc: string
    iaAvancee: string
    iaDesc: string
    backofficeComplet: string
    backofficeDesc: string
    integrationCRM: string
    crmDesc: string
    apiSimple: string
    apiDesc: string
    essayezMaintenant: string
    agentsPublicsDisponibles: string
    agentsPublicsDesc: string
    essayerMaintenant: string
    appeler: string
    aucunAgentPublic: string
    creerPremierAgent: string
    pourquoiChoisir: string
    config5Minutes: string
    aucuneExpertise: string
    scalingAutomatique: string
    support247: string
    securiteRGPD: string
    integrationsIllimitees: string
    securiteConformite: string
    securiteDesc: string
    cryptageSSL: string
    conforme: string
    uptime: string
    pretTransformer: string
    pretDesc: string
    commencerMaintenant: string
    tousDroitsReserves: string
    documentation: string
    support: string
    knowledgeBase: string
  }
}

const translations: Record<Language, Translations> = {
  fr: {
    common: {
      save: 'Enregistrer',
      cancel: 'Annuler',
      delete: 'Supprimer',
      edit: 'Modifier',
      create: 'Créer',
      update: 'Mettre à jour',
      search: 'Rechercher',
      loading: 'Chargement...',
      error: 'Erreur',
      success: 'Succès',
      confirm: 'Confirmer',
      close: 'Fermer',
      back: 'Retour',
      next: 'Suivant',
      previous: 'Précédent',
      actions: 'Actions',
      status: 'Statut',
      date: 'Date',
      time: 'Heure',
      name: 'Nom',
      description: 'Description',
      email: 'Email',
      password: 'Mot de passe',
      login: 'Connexion',
      logout: 'Déconnexion',
      register: 'Inscription',
      settings: 'Paramètres',
      profile: 'Profil',
      dashboard: 'Tableau de bord',
      yes: 'Oui',
      no: 'Non',
    },
    nav: {
      dashboard: 'Tableau de bord',
      agents: 'Agents',
      libraries: 'Bibliothèques',
      calls: 'Appels',
      integrations: 'Intégrations',
      phoneNumbers: 'Numéros de téléphone',
      callbacks: 'Rappels',
      apiKeys: 'Clés API',
      support: 'Support',
      settings: 'Paramètres',
      admin: 'Administration',
      billing: 'Facturation',
      usage: 'Utilisation',
      security: 'Sécurité',
    },
    dashboard: {
      title: 'Tableau de bord',
      welcome: 'Bienvenue',
      totalAgents: 'Agents totaux',
      totalCalls: 'Appels totaux',
      activeCalls: 'Appels actifs',
      recentCalls: 'Appels récents',
    },
    agents: {
      title: 'Agents',
      createAgent: 'Créer un agent',
      editAgent: 'Modifier l\'agent',
      deleteAgent: 'Supprimer l\'agent',
      agentName: 'Nom de l\'agent',
      agentDescription: 'Description',
      systemPrompt: 'Prompt système',
      greeting: 'Message d\'accueil',
      language: 'Langue',
      voiceId: 'ID de voix',
      voiceGender: 'Genre de voix',
      isActive: 'Actif',
      isPublic: 'Public',
      noAgents: 'Aucun agent',
      createFirstAgent: 'Créer votre premier agent',
    },
    libraries: {
      title: 'Bibliothèques d\'agents',
      subtitle: 'Parcourez et enregistrez des modèles d\'agents pour créer rapidement de nouveaux agents',
      publicLibraries: 'Bibliothèques publiques',
      myLibraries: 'Mes bibliothèques',
      createLibrary: 'Créer une bibliothèque',
      createPublicLibrary: 'Créer une bibliothèque publique',
      editLibrary: 'Modifier la bibliothèque',
      deleteLibrary: 'Supprimer la bibliothèque',
      useTemplate: 'Utiliser le modèle',
      saveToMyLibraries: 'Enregistrer dans mes bibliothèques',
      category: 'Catégorie',
      allCategories: 'Toutes les catégories',
      searchPlaceholder: 'Rechercher des bibliothèques par nom, description ou prompt...',
      noLibraries: 'Aucune bibliothèque',
      createNewAgent: 'Créer un nouvel agent',
      applyToAgent: 'Appliquer à l\'agent',
      selectAgent: 'Sélectionner un agent',
      selectOption: 'Sélectionner une option',
      createNewAgentOption: 'Créer un nouvel agent',
      applyToExistingAgent: 'Appliquer à un agent existant',
      libraryUpdated: 'Bibliothèque mise à jour avec succès',
      libraryCreated: 'Bibliothèque publique créée avec succès',
      libraryDeleted: 'Bibliothèque supprimée avec succès',
      librarySaved: 'Bibliothèque enregistrée avec succès',
    },
    calls: {
      title: 'Appels',
      callHistory: 'Historique des appels',
      totalCalls: 'Appels totaux',
      duration: 'Durée',
      cost: 'Coût',
      status: 'Statut',
      from: 'De',
      to: 'Vers',
      date: 'Date',
      details: 'Détails',
      transcript: 'Transcription',
      summary: 'Résumé',
      messages: 'Messages',
      sendEmail: 'Envoyer un email',
      emailSent: 'Email envoyé',
      favorite: 'Favori',
      unfavorite: 'Retirer des favoris',
      noCalls: 'Aucun appel',
      loading: 'Chargement...',
    },
    phoneNumbers: {
      title: 'Numéros de téléphone',
      subtitle: 'Gérez les numéros de téléphone pour vos agents vocaux',
      managePhoneNumbers: 'Gérer les numéros de téléphone',
      addPhoneNumber: 'Ajouter un numéro',
      editPhoneNumber: 'Modifier le numéro',
      deletePhoneNumber: 'Supprimer le numéro',
      phoneNumber: 'Numéro de téléphone',
      agent: 'Agent',
      status: 'Statut',
      noPhoneNumbers: 'Aucun numéro de téléphone',
      requestNewNumber: 'Demander un nouveau numéro',
      addExistingNumber: 'Ajouter un numéro existant',
      noPhoneNumbersDesc: 'Ajoutez votre numéro Zadarma existant ou demandez-en un nouveau',
      monthly: 'Mensuel:',
      perMinute: 'Par minute:',
      pbxRouting: 'Routage PBX',
      extension: 'Extension:',
      auto: 'Auto',
      businessHours: 'Heures d\'ouverture:',
      afterHours: 'Hors heures:',
      pbxNotConfigured: 'Menu PBX non configuré',
      pbxNotConfiguredDesc: 'Les appels sont routés directement vers l\'agent assigné.',
      uploadDocuments: 'Télécharger des documents',
      changeAgent: 'Changer d\'agent',
      assignAgent: 'Assigner un agent',
      configurePBX: 'Configurer PBX',
      verificationDocuments: 'Documents de vérification',
      noDocumentsUploaded: 'Aucun document téléchargé pour le moment',
      addExistingPhoneNumber: 'Ajouter un numéro de téléphone existant',
      addExistingDesc: 'Ajoutez un numéro de téléphone que vous possédez déjà sur Zadarma (ex: +3242833288)',
      phoneNumberLabel: 'Numéro de téléphone *',
      phoneNumberPlaceholder: '+3242833288',
      phoneNumberHelper: 'Inclure l\'indicatif du pays (ex: +32 pour la Belgique)',
      countryCode: 'Code pays',
      businessName: 'Nom de l\'entreprise',
      businessNameOptional: 'Nom de l\'entreprise (Optionnel)',
      businessNamePlaceholder: 'Nom de votre entreprise',
      adding: 'Ajout...',
      addPhoneNumberButton: 'Ajouter le numéro',
      requestNewPhoneNumber: 'Demander un nouveau numéro de téléphone',
      businessType: 'Type d\'entreprise',
      businessAddress: 'Adresse de l\'entreprise',
      company: 'Entreprise',
      individual: 'Individuel',
      uploadVerificationDocument: 'Télécharger un document de vérification',
      documentType: 'Type de document',
      file: 'Fichier',
      uploadDocument: 'Télécharger le document',
      uploadDocumentButton: 'Télécharger',
      uploading: 'Téléchargement...',
      selectAnAgent: 'Sélectionner un agent',
      noAgentsAvailable: 'Aucun agent disponible',
      assignAgentButton: 'Assigner l\'agent',
      pbxConfiguration: 'Configuration PBX',
      timezone: 'Fuseau horaire',
      openTime: 'Heure d\'ouverture',
      closeTime: 'Heure de fermeture',
      days: 'Jours',
      menuOptions: 'Options du menu',
      key: 'Touche',
      label: 'Libellé',
      destinationType: 'Type de destination',
      destinationValue: 'Valeur de destination',
      destination: 'Destination',
      addMenuOption: 'Ajouter une option de menu',
      afterHoursRouting: 'Routage hors heures',
      message: 'Message',
      savePBX: 'Enregistrer PBX',
      saving: 'Enregistrement...',
      assignAgentToPhoneNumber: 'Assigner un agent au numéro de téléphone',
      activeDays: 'Jours actifs',
      optional: 'optionnel',
      requesting: 'Demande...',
      assigning: 'Assignation...',
      phoneNumberPlaceholderRequest: '+33123456789',
      createAgentFirst: 'Créez d\'abord un agent pour l\'assigner à ce numéro',
      uploadDocumentsFor: 'Téléchargez des documents pour',
      speakToSales: 'Parler aux ventes',
      option: 'Option',
      chooseAgentDescription: 'Choisissez quel agent gérera les appels vers',
      notConfigured: 'Non configuré',
      connectToAIAgent: 'Se connecter à l\'agent IA',
      sendToVoicemail: 'Envoyer vers la messagerie vocale',
      forwardTo: 'Transférer vers',
      externalNumber: 'numéro externe',
      externalDestination: 'Destination externe:',
      customRouting: 'Routage personnalisé',
      active: 'Actif',
      inactive: 'Inactif',
      pendingVerification: 'Vérification en attente',
      configured: 'Configuré',
      notConfiguredStatus: 'Non configuré',
      unknownAgent: 'Agent inconnu',
      phoneNumberAddedSuccess: 'Numéro de téléphone ajouté avec succès ! Vous pouvez maintenant l\'assigner à un agent.',
      phoneNumberRequestedSuccess: 'Demande de numéro envoyée avec succès',
      documentUploadedSuccess: 'Document téléchargé avec succès',
      agentAssignedSuccess: 'Agent assigné avec succès',
      pbxSavedSuccess: 'Configuration PBX enregistrée avec succès',
      deleteConfirm: 'Êtes-vous sûr de vouloir supprimer ce numéro ?',
      deleteSuccess: 'Numéro supprimé avec succès',
      deleteError: 'Échec de la suppression du numéro',
      createSuccess: 'Numéro créé avec succès',
      createError: 'Échec de la création du numéro',
      updateSuccess: 'Numéro mis à jour avec succès',
      updateError: 'Échec de la mise à jour du numéro',
    },
    apiKeys: {
      title: 'Clés API',
      createApiKey: 'Créer une clé API',
      deleteApiKey: 'Supprimer la clé API',
      keyName: 'Nom de la clé',
      apiKey: 'Clé API',
      createdAt: 'Créée le',
      lastUsed: 'Dernière utilisation',
      noApiKeys: 'Aucune clé API',
    },
    support: {
      title: 'Support',
      createTicket: 'Créer un ticket',
      tickets: 'Tickets',
      subject: 'Sujet',
      message: 'Message',
      status: 'Statut',
      priority: 'Priorité',
      createdAt: 'Créé le',
      noTickets: 'Aucun ticket',
    },
    billing: {
      title: 'Facturation',
      currentPlan: 'Plan actuel',
      credits: 'Crédits',
      usage: 'Utilisation',
      paymentMethod: 'Méthode de paiement',
      invoices: 'Factures',
      noInvoices: 'Aucune facture',
    },
    settings: {
      title: 'Paramètres',
      general: 'Général',
      security: 'Sécurité',
      notifications: 'Notifications',
      language: 'Langue',
      theme: 'Thème',
      light: 'Clair',
      dark: 'Sombre',
      system: 'Système',
    },
    auth: {
      login: 'Connexion',
      logout: 'Déconnexion',
      register: 'Inscription',
      email: 'Email',
      password: 'Mot de passe',
      confirmPassword: 'Confirmer le mot de passe',
      fullName: 'Nom complet',
      loginSuccess: 'Connexion réussie!',
      loginError: 'Erreur de connexion',
      registerSuccess: 'Inscription réussie!',
      registerError: 'Erreur d\'inscription',
      noAccount: 'Pas encore de compte ?',
      createAccount: 'Créer un compte',
      hasAccount: 'Vous avez déjà un compte ?',
      loginHere: 'Se connecter',
      connecting: 'Connexion...',
      connect: 'Se connecter',
    },
    agentForm: {
      backToAgents: 'Retour aux agents',
      createNewAgent: 'Créer un nouvel agent',
      editAgent: 'Modifier l\'agent',
      configureDetails: 'Configurez les détails, le comportement et la langue de votre agent IA.',
      agentName: 'Nom de l\'agent *',
      agentNamePlaceholder: 'Bot de support client',
      description: 'Description',
      descriptionPlaceholder: 'Description courte de votre agent...',
      systemPrompt: 'Prompt système *',
      systemPromptPlaceholder: 'Tu es un assistant IA...',
      greeting: 'Message d\'accueil',
      greetingPlaceholder: 'Bonjour, je suis assistante chez Weedoo. Comment puis-je vous aider ?',
      language: 'Langue *',
      voiceId: 'ID de voix',
      voiceGender: 'Genre de voix',
      isActive: 'Actif',
      isPublic: 'Public',
      ragEnabled: 'Base de connaissances activée',
      agentCreated: '🎉 Agent créé avec succès',
      agentUpdated: '✅ Agent mis à jour avec succès',
      agentCreateError: 'Échec de la création de l\'agent.',
      agentUpdateError: 'Échec de la mise à jour de l\'agent.',
      saveAgentFirst: 'Veuillez d\'abord enregistrer l\'agent avant de télécharger des documents',
      uploadDocument: 'Télécharger un document',
      addWebsite: 'Ajouter un site web',
      websiteUrl: 'URL du site web',
      documents: 'Documents',
      noDocuments: 'Aucun document',
      deleteDocument: 'Supprimer le document',
      processing: 'Traitement en cours',
      completed: 'Terminé',
      failed: 'Échec',
    },
    dashboard: {
      welcomeMessage: 'Bienvenue ! Voici un aperçu de vos agents vocaux.',
      totalAgentsSubtitle: 'Agents vocaux actifs',
      totalCallsSubtitle: 'Appels effectués',
      totalMinutes: 'Minutes Utilisées',
      totalMinutesSubtitle: 'Temps d\'appel total',
      totalCost: 'Coût Total',
      totalCostSubtitle: 'Dépenses cumulées',
      statsLoadError: 'Échec du chargement des statistiques',
      quickActions: 'Actions Rapides',
    },
    agentsPage: {
      title: 'Voice Agents',
      subtitle: 'Gérez, démarrez et améliorez vos agents vocaux IA',
      newAgent: 'Nouvel agent',
      noAgentsYet: 'Aucun agent pour le moment',
      noAgentsDescription: 'Vous n\'avez pas encore d\'agents vocaux. Commencez par créer votre premier agent ci-dessous.',
      createAgent: 'Créer un agent',
      active: 'Actif',
      inactive: 'Inactif',
      private: 'Privé',
      public: 'Public',
      noDescription: 'Aucune description fournie.',
      test: 'Tester',
      edit: 'Modifier',
      delete: 'Supprimer',
      deleteConfirm: 'Êtes-vous sûr de vouloir supprimer cet agent ?',
      deleteSuccess: 'Agent supprimé avec succès',
      deleteError: 'Échec de la suppression de l\'agent',
      loadError: 'Échec du chargement des agents',
    },
    callsPage: {
      callHistory: 'Historique des appels',
      allCalls: 'Tous les appels',
      favorites: 'Favoris',
      filters: 'Filtres',
      status: 'Statut',
      allStatuses: 'Tous les statuts',
      actionRequired: 'Action requise',
      searchPlaceholder: 'Rechercher des appels...',
      noCallsFound: 'Aucun appel trouvé',
      bulkDelete: 'Supprimer la sélection',
      bulkFavorite: 'Ajouter aux favoris',
      bulkUnfavorite: 'Retirer des favoris',
      deleteConfirm: 'Êtes-vous sûr de vouloir supprimer ces appels ?',
      deleteSuccess: 'Appels supprimés avec succès',
      deleteError: 'Échec de la suppression des appels',
      favoriteSuccess: 'Ajouté aux favoris',
      unfavoriteSuccess: 'Retiré des favoris',
      favoriteError: 'Échec de la mise à jour',
      page: 'Page',
      of: 'sur',
      showing: 'Affichage',
      results: 'résultats',
      minutes: 'minutes',
      cost: 'Coût',
      viewDetails: 'Voir les détails',
      noSummary: 'Aucun résumé disponible',
      noTranscript: 'Aucune transcription disponible',
      keyPoints: 'Points clés',
      actionItems: 'Actions requises',
      sentiment: 'Sentiment',
      callbackRequested: 'Rappel demandé',
      sendEmail: 'Envoyer un email',
      emailSent: 'Email envoyé',
      emailError: 'Échec de l\'envoi de l\'email',
      close: 'Fermer',
      callDetails: 'Détails de l\'appel',
      sessionId: 'ID de session',
      duration: 'Durée',
      regenerateSummary: 'Régénérer le résumé',
      regenerating: 'Régénération...',
      generateSummary: 'Générer un résumé',
      followUpActions: 'Actions de suivi détectées',
      actionItems: 'Détails des actions à entreprendre',
      summary: 'Résumé',
      messages: 'Messages',
      live: 'En direct',
      visitor: 'Visiteur',
      system: 'Système',
      agent: 'Agent',
      compose: 'Composer',
      to: 'À',
      subject: 'Sujet',
      message: 'Message',
      sending: 'Envoi...',
      noCalls: 'Aucun appel',
      favorite: 'Ajouter aux favoris',
      unfavorite: 'Retirer des favoris',
      loading: 'Chargement...',
    },
    categories: {
      realEstate: 'Immobilier',
      customerService: 'Service Client',
      sales: 'Vente',
      support: 'Support',
      marketing: 'Marketing',
      hr: 'RH',
      healthcare: 'Santé',
      education: 'Éducation',
      finance: 'Finance',
      legal: 'Juridique',
      general: 'Général',
    },
    register: {
      title: 'Créer un compte',
      fullName: 'Nom complet',
      confirmPassword: 'Confirmer le mot de passe',
      passwordMismatch: 'Les mots de passe ne correspondent pas',
      passwordMinLength: 'Le mot de passe doit contenir au moins 8 caractères',
      passwordMaxLength: 'Le mot de passe ne peut pas dépasser 72 caractères',
      passwordHint: '8-72 caractères',
      creating: 'Création...',
      createAccount: 'Créer mon compte',
      hasAccount: 'Déjà un compte ?',
      loginHere: 'Se connecter',
      success: 'Compte créé avec succès! Veuillez attendre l\'approbation d\'un administrateur avant de vous connecter.',
      error: 'Erreur lors de la création du compte',
    },
    phoneNumbers: {
      subtitle: 'Gérez les numéros de téléphone pour vos agents vocaux',
      addPhoneNumber: 'Ajouter un numéro',
      editPhoneNumber: 'Modifier le numéro',
      deletePhoneNumber: 'Supprimer le numéro',
      phoneNumber: 'Numéro de téléphone',
      agent: 'Agent',
      status: 'Statut',
      noPhoneNumbers: 'Aucun numéro de téléphone',
      deleteConfirm: 'Êtes-vous sûr de vouloir supprimer ce numéro ?',
      deleteSuccess: 'Numéro supprimé avec succès',
      deleteError: 'Échec de la suppression du numéro',
      createSuccess: 'Numéro créé avec succès',
      createError: 'Échec de la création du numéro',
      updateSuccess: 'Numéro mis à jour avec succès',
      updateError: 'Échec de la mise à jour du numéro',
    },
    apiKeys: {
      subtitle: 'Gérez de manière sécurisée vos clés d\'accès pour les API d\'agents vocaux.',
      createApiKey: 'Nouvelle clé API',
      deleteApiKey: 'Supprimer la clé API',
      keyName: 'Nom de la clé',
      apiKey: 'Clé API',
      createdAt: 'Créée le',
      lastUsed: 'Dernière utilisation',
      noApiKeys: 'Aucune clé API trouvée',
      deleteConfirm: 'Êtes-vous sûr de vouloir supprimer cette clé API ?',
      deleteSuccess: 'Clé API supprimée avec succès',
      deleteError: 'Échec de la suppression de la clé API',
      createSuccess: 'Clé API créée avec succès',
      createError: 'Échec de la création de la clé API',
      copySuccess: 'Clé API copiée dans le presse-papiers',
      never: 'Jamais',
    },
    support: {
      subtitle: 'Contactez notre équipe pour toute question ou problème',
      createTicket: 'Créer un ticket',
      tickets: 'Tickets',
      subject: 'Sujet',
      message: 'Message',
      status: 'Statut',
      priority: 'Priorité',
      createdAt: 'Créé le',
      noTickets: 'Aucun ticket',
      createSuccess: 'Votre demande a été envoyée avec succès!',
      createError: 'Erreur lors de l\'envoi de votre demande',
      low: 'Faible',
      medium: 'Moyenne',
      high: 'Élevée',
      open: 'Ouvert',
      closed: 'Fermé',
      inProgress: 'En cours',
    },
    billing: {
      subtitle: 'Gérez votre facturation et vos méthodes de paiement',
      currentPlan: 'Plan actuel',
      credits: 'Crédits',
      usage: 'Utilisation',
      paymentMethod: 'Méthode de paiement',
      invoices: 'Factures',
      noInvoices: 'Aucune facture',
      addPaymentMethod: 'Ajouter une méthode de paiement',
      updatePaymentMethod: 'Mettre à jour la méthode de paiement',
      noPaymentMethod: 'Aucune méthode de paiement',
    },
    profile: {
      title: 'Profil',
      subtitle: 'Gérez vos informations personnelles',
      personalInfo: 'Informations personnelles',
      updateSuccess: 'Profil mis à jour avec succès',
      updateError: 'Échec de la mise à jour du profil',
      changePassword: 'Changer le mot de passe',
      currentPassword: 'Mot de passe actuel',
      newPassword: 'Nouveau mot de passe',
      confirmNewPassword: 'Confirmer le nouveau mot de passe',
      passwordChanged: 'Mot de passe modifié avec succès',
      passwordError: 'Échec de la modification du mot de passe',
    },
    security: {
      title: 'Sécurité',
      subtitle: 'Gérez vos paramètres de sécurité',
      twoFactor: 'Authentification à deux facteurs',
      apiKeys: 'Clés API',
      sessions: 'Sessions actives',
      loginHistory: 'Historique de connexion',
    },
    usage: {
      title: 'Utilisation',
      subtitle: 'Consultez votre utilisation et vos statistiques',
      period: 'Période',
      last7Days: '7 derniers jours',
      last30Days: '30 derniers jours',
      last90Days: '90 derniers jours',
      thisMonth: 'Ce mois',
      lastMonth: 'Mois dernier',
      calls: 'Appels',
      minutes: 'Minutes',
      cost: 'Coût',
    },
    callbacks: {
      title: 'Rappels',
      subtitle: 'Gérez vos rappels programmés',
      noCallbacks: 'Aucun rappel',
      scheduled: 'Programmé',
      completed: 'Terminé',
      cancelled: 'Annulé',
      pending: 'En attente',
      contacted: 'Contacté',
      all: 'Tous',
      callbackRequests: 'Demandes de rappel',
      manageCallbacks: 'Gérez les demandes de rappel de vos agents vocaux',
      noCallbackRequests: 'Aucune demande de rappel',
      noCallbackRequestsDesc: 'Les demandes de rappel apparaîtront ici lorsque les agents détecteront le besoin d\'une intervention humaine',
      priority: 'Priorité',
      urgent: 'Urgent',
      high: 'Élevée',
      normal: 'Normale',
      low: 'Faible',
      status: 'Statut',
      callerName: 'Nom de l\'appelant',
      callerPhone: 'Téléphone de l\'appelant',
      callerEmail: 'Email de l\'appelant',
      preferredCallbackTime: 'Heure de rappel préférée',
      notes: 'Notes',
      resolution: 'Résolution',
      assignedTo: 'Assigné à',
      viewCall: 'Voir l\'appel',
      update: 'Mettre à jour',
      updateCallbackRequest: 'Mettre à jour la demande de rappel',
      assignedToPlaceholder: 'Nom ou email',
      notesPlaceholder: 'Notes ou commentaires supplémentaires',
      resolutionPlaceholder: 'Comment cela a-t-il été résolu ?',
      updating: 'Mise à jour...',
      updateButton: 'Mettre à jour',
      updateSuccess: 'Rappel mis à jour avec succès !',
      updateError: 'Erreur lors de la mise à jour du rappel',
      createdAt: 'Créé le',
    },
    integrations: {
      title: 'Intégrations',
      subtitle: 'Connectez votre calendrier, email, CRM et autres outils métier',
      noIntegrations: 'Aucune intégration',
      addIntegration: 'Ajouter une intégration',
      editIntegration: 'Modifier l\'intégration',
      deleteIntegration: 'Supprimer l\'intégration',
      newIntegration: 'Nouvelle intégration',
      createIntegration: 'Créer une intégration',
      allTypes: 'Tous les types',
      allStatuses: 'Tous les statuts',
      active: 'Actif',
      inactive: 'Inactif',
      error: 'Erreur',
      pendingAuth: 'Authentification en attente',
      testConnection: 'Tester la connexion',
      syncData: 'Synchroniser les données',
      activate: 'Activer',
      deactivate: 'Désactiver',
      lastSynced: 'Dernière synchronisation:',
      deleteConfirm: 'Êtes-vous sûr de vouloir supprimer cette intégration ?',
      deleteSuccess: 'Intégration supprimée avec succès',
      deleteError: 'Échec de la suppression de l\'intégration',
      testSuccess: 'Test de connexion réussi',
      testError: 'Échec du test de connexion',
      syncSuccess: 'Synchronisation terminée avec succès',
      syncError: 'Échec de la synchronisation',
      activateSuccess: 'Intégration activée',
      activateError: 'Échec de la mise à jour de l\'intégration',
      loadError: 'Échec du chargement des intégrations',
      backToIntegrations: 'Retour aux intégrations',
      newIntegrationTitle: 'Nouvelle intégration',
      editIntegrationTitle: 'Modifier l\'intégration',
      name: 'Nom *',
      namePlaceholder: 'Mon calendrier Google',
      description: 'Description',
      descriptionPlaceholder: 'Description optionnelle pour cette intégration',
      integrationType: 'Type d\'intégration *',
      selectType: 'Sélectionner un type',
      provider: 'Fournisseur *',
      selectProvider: 'Sélectionner un fournisseur',
      configuration: 'Configuration',
      headersJson: 'En-têtes (JSON)',
      credentialsWarning: '⚠️ Les identifiants sont stockés de manière sécurisée. Assurez-vous d\'utiliser des identifiants valides pour votre intégration.',
      saving: 'Enregistrement...',
      updateIntegration: 'Mettre à jour l\'intégration',
      createIntegrationButton: 'Créer l\'intégration',
      updateSuccess: '✅ Intégration mise à jour avec succès',
      createSuccess: '🎉 Intégration créée avec succès',
      saveError: 'Échec de l\'enregistrement de l\'intégration.',
      loadIntegrationError: 'Échec du chargement de l\'intégration.',
      typeCalendar: '📅 Calendrier',
      typeEmail: '📧 Email',
      typeContactManagement: '👥 Contacts',
      typeDatabase: '💾 Base de données',
      typeCRM: '📊 CRM',
      typeAccounting: '💰 Comptabilité',
      typeOther: '🔧 Autre',
    },
    admin: {
      overview: 'Vue d\'ensemble',
      users: 'Utilisateurs',
      agents: 'Agents',
      support: 'Support',
      overviewTitle: 'Admin Overview',
      overviewSubtitle: 'Vue d\'ensemble de la plateforme : utilisateurs, agents, appels et support.',
      usersTitle: 'Gestion des utilisateurs',
      agentsTitle: 'Gestion des agents',
      supportTitle: 'Support',
      totalUsers: 'Utilisateurs',
      activeUsers: 'actifs',
      pendingUsers: 'en attente',
      totalAgents: 'Agents',
      activeAgents: 'actifs',
      publicAgents: 'publics',
      totalCalls: 'Appels (30j)',
      openTickets: 'Tickets ouverts',
      usage: 'Utilisation',
      revenue: 'Revenus',
      recentUsers: 'Nouveaux utilisateurs',
      recentAgents: 'Agents récents',
      recentTickets: 'Tickets récents',
      approved: 'Approuvé',
      pending: 'En attente',
      active: 'Actif',
      inactive: 'Inactif',
      public: 'Public',
      private: 'Privé',
      approve: 'Approuver',
      reject: 'Rejeter',
      activate: 'Activer',
      deactivate: 'Désactiver',
      makeAdmin: 'Rendre admin',
      removeAdmin: 'Retirer admin',
      approveSuccess: 'Utilisateur approuvé',
      rejectSuccess: 'Utilisateur rejeté',
      activateSuccess: 'Utilisateur activé',
      deactivateSuccess: 'Utilisateur désactivé',
      makeAdminSuccess: 'Admin ajouté',
      removeAdminSuccess: 'Admin retiré',
    },
    quickActions: {
      createAgent: 'Créer un Agent',
      createAgentDesc: 'Construisez un agent vocal personnalisé pour votre cas d\'usage',
      manageApiKeys: 'Gérer les Clés API',
      manageApiKeysDesc: 'Créez et gérez vos clés d\'accès API pour l\'intégration',
      tryDemo: 'Essayer la Démo',
      tryDemoDesc: 'Testez l\'agent de démonstration publique en direct',
    },
    agentDocuments: {
      title: 'Documents RAG',
      backToAgents: 'Retour aux agents',
      agent: 'Agent:',
      ragEnabled: 'RAG Activé:',
      addKnowledgeSources: 'Ajouter des sources de connaissances',
      uploadPdfDocument: '📄 Télécharger un document PDF',
      clickToUpload: 'Cliquez pour télécharger ou glissez-déposez',
      pdfFilesOnly: 'Fichiers PDF uniquement, max 10 Mo (supporte les PDF scannés)',
      chooseFile: 'Choisir un fichier',
      scrapeWebsite: '🌐 Scraper un site web',
      websiteUrlPlaceholder: 'https://example.com/documentation',
      scrape: 'Scraper',
      howItWorks: 'Comment ça fonctionne:',
      howItWorksDesc: 'Ajoutez des documents PDF ou des URLs de sites web pour donner des connaissances à votre agent. Le contenu sera traité, découpé et intégré pour la recherche sémantique pendant les conversations.',
      uploadedDocuments: 'Documents téléchargés',
      noDocumentsUploaded: 'Aucun document téléchargé pour le moment',
      source: 'Source',
      size: 'Taille',
      pages: 'Pages',
      chunks: 'Chunks',
      added: 'Ajouté:',
      processed: 'Traité:',
      deleteDocument: 'Supprimer le document',
      deleteConfirm: 'Êtes-vous sûr de vouloir supprimer ce document ?',
      onlyPdfSupported: 'Seuls les fichiers PDF sont pris en charge',
      fileSizeLimit: 'La taille du fichier doit être inférieure à 10 Mo',
      uploadingFile: 'Téléchargement du fichier...',
      processingEmbeddings: 'Traitement et génération des embeddings...',
      scrapingWebsite: 'Scraping du site web...',
      enterWebsiteUrl: 'Veuillez entrer une URL de site web',
      enterValidUrl: 'Veuillez entrer une URL valide (ex: https://example.com)',
      uploadSuccess: 'Document téléchargé avec succès',
      uploadError: 'Échec du téléchargement du document',
      deleteSuccess: 'Document supprimé avec succès',
      deleteError: 'Échec de la suppression du document',
      loadError: 'Échec du chargement des données',
      toggleRAGError: 'Échec de la modification du RAG',
      completed: 'Terminé',
      processing: 'En cours',
      failed: 'Échoué',
      pending: 'En attente',
    },
    agentEmbed: {
      title: 'Intégration de l\'agent',
      backToAgents: 'Retour aux agents',
      embedConfiguration: 'Configuration d\'intégration',
      enableEmbed: 'Activer l\'intégration',
      widgetColor: 'Couleur du widget',
      widgetPosition: 'Position du widget',
      greetingMessage: 'Message de bienvenue',
      allowedDomains: 'Domaines autorisés',
      addDomain: 'Ajouter un domaine',
      domainPlaceholder: 'example.com',
      embedCode: 'Code d\'intégration',
      copyCode: 'Copier le code',
      codeCopied: 'Code copié !',
      saveConfig: 'Enregistrer la configuration',
      saving: 'Enregistrement...',
      saveSuccess: 'Configuration d\'intégration enregistrée avec succès !',
      saveError: 'Erreur lors de l\'enregistrement de la configuration',
      bottomRight: 'En bas à droite',
      bottomLeft: 'En bas à gauche',
      topRight: 'En haut à droite',
      topLeft: 'En haut à gauche',
    },
    callDetail: {
      backToCalls: 'Retour aux appels',
      callDetails: 'Détails de l\'Appel',
      generateSummary: 'Générer un résumé',
      regenerating: 'Régénération...',
      regenerateSummary: 'Régénérer le résumé',
      generating: 'Génération...',
      summaryGenerated: 'Résumé généré avec succès',
      summaryError: 'Erreur lors de la génération du résumé',
      callNotFound: 'Appel non trouvé',
      overview: 'Vue d\'ensemble',
      transcript: 'Transcription',
      duration: 'Durée',
      cost: 'Coût',
      status: 'Statut',
      callSummary: 'Résumé de l\'Appel',
      sentiment: 'Sentiment:',
      detectedActions: 'Actions détectées',
      keyPoints: 'Points Clés:',
      actionItems: 'Actions à entreprendre',
      conversation: 'Conversation',
      user: 'Utilisateur',
      agent: 'Agent',
      fullTranscript: 'Transcription Complète',
      transcriptNotAvailable: 'Transcription non disponible pour cet appel',
    },
    publicAgent: {
      agentNotFound: 'Agent introuvable ou non public',
      agentInactive: 'Cet agent est actuellement inactif',
      loadError: 'Échec du chargement de l\'agent',
      connect: 'Se connecter',
      disconnect: 'Se déconnecter',
      connecting: 'Connexion...',
      disconnecting: 'Déconnexion...',
      recording: 'Enregistrement',
      stop: 'Arrêter',
      sendMessage: 'Envoyer un message',
      sending: 'Envoi...',
      messagePlaceholder: 'Tapez votre message...',
      disconnectFirst: 'Déconnectez-vous d\'abord pour changer d\'agent',
    },
    demo: {
      title: 'Démo',
      selectAgent: 'Sélectionner un agent',
      noAgentsAvailable: 'Aucun agent de démonstration disponible',
      loadError: 'Impossible de charger les agents de démonstration',
      connect: 'Se connecter',
      disconnect: 'Se déconnecter',
      connecting: 'Connexion...',
      disconnecting: 'Déconnexion...',
      recording: 'Enregistrement',
      stop: 'Arrêter',
      sendMessage: 'Envoyer un message',
      sending: 'Envoi...',
      messagePlaceholder: 'Tapez votre message...',
      disconnectFirst: 'Déconnectez-vous d\'abord pour changer d\'agent',
    },
    adminSupport: {
      title: 'Support',
      subtitle: 'Gérer les tickets de support',
      searchPlaceholder: 'Rechercher des tickets...',
      allStatuses: 'Tous les statuts',
      allPriorities: 'Toutes les priorités',
      open: 'Ouvert',
      inProgress: 'En cours',
      resolved: 'Résolu',
      closed: 'Fermé',
      low: 'Faible',
      medium: 'Moyenne',
      high: 'Haute',
      urgent: 'Urgente',
      statusUpdated: 'Statut mis à jour',
      priorityUpdated: 'Priorité mise à jour',
      updateError: 'Impossible de mettre à jour',
      loadError: 'Impossible de charger les tickets',
      noTickets: 'Aucun ticket',
      ticketNumber: 'Numéro de ticket',
      subject: 'Sujet',
      name: 'Nom',
      email: 'Email',
      category: 'Catégorie',
      createdAt: 'Créé le',
      updatedAt: 'Mis à jour le',
      responses: 'Réponses',
      lastResponse: 'Dernière réponse',
      never: 'Jamais',
      updateStatus: 'Mettre à jour le statut',
      updatePriority: 'Mettre à jour la priorité',
    },
    landing: {
      agentsPublics: 'Agents Publics',
      demo: 'Démo',
      commencer: 'Commencer',
      tableauDeBord: 'Tableau de bord',
      deconnexion: 'Déconnexion',
      agentsVocaux: 'Agents Vocaux',
      intelligents: 'Intelligents',
      enFrancais: 'en Français',
      heroDescription: 'Créez des agents vocaux IA qui parlent français naturellement. Latence ultra-faible, intégration simple.',
      commencerGratuitement: 'Commencer Gratuitement',
      essayerDemo: 'Essayer la Démo',
      latenceMoyenne: 'Latence moyenne',
      disponibilite: 'Disponibilité',
      langues: 'Langues',
      clients: 'Clients',
      fonctionnalitesPuissantes: 'Fonctionnalités Puissantes',
      fonctionnalitesDesc: 'Tout ce dont vous avez besoin pour créer des agents vocaux professionnels',
      latenceUltraFaible: 'Latence Ultra-Faible',
      latenceDesc: 'Réponse en moins de 500ms pour une conversation naturelle',
      francaisNatif: 'Français Natif',
      francaisDesc: 'Compréhension et génération de français naturel et fluide',
      iaAvancee: 'IA Avancée',
      iaDesc: 'GPT-4 et modèles de pointe pour des conversations intelligentes',
      backofficeComplet: 'Backoffice Complet',
      backofficeDesc: 'Gérez vos agents, appels, analytics et intégrations en un seul endroit',
      integrationCRM: 'Intégration CRM',
      crmDesc: 'Connectez votre CRM pour synchroniser les données en temps réel',
      apiSimple: 'API Simple',
      apiDesc: 'Intégration facile avec notre API REST bien documentée',
      essayezMaintenant: 'Essayez Maintenant',
      agentsPublicsDisponibles: 'Agents Publics Disponibles',
      agentsPublicsDesc: 'Testez nos agents de démonstration en direct',
      essayerMaintenant: 'Essayer Maintenant',
      appeler: 'Appeler',
      aucunAgentPublic: 'Aucun agent public disponible',
      creerPremierAgent: 'Créez votre premier agent pour commencer',
      pourquoiChoisir: 'Pourquoi Nous Choisir',
      config5Minutes: 'Configuration en 5 Minutes',
      aucuneExpertise: 'Aucune expertise technique requise',
      scalingAutomatique: 'Scaling Automatique',
      support247: 'Support 24/7',
      securiteRGPD: 'Sécurité & RGPD',
      integrationsIllimitees: 'Intégrations Illimitées',
      securiteConformite: 'Sécurité & Conformité',
      securiteDesc: 'Vos données sont protégées et conformes aux réglementations',
      cryptageSSL: 'Cryptage SSL',
      conforme: 'Conforme RGPD',
      uptime: 'Uptime 99.9%',
      pretTransformer: 'Prêt à Transformer',
      pretDesc: 'Votre Communication',
      commencerMaintenant: 'Commencer Maintenant',
      tousDroitsReserves: 'Tous droits réservés',
      documentation: 'Documentation',
      support: 'Support',
      knowledgeBase: 'Base de connaissances',
    },
  },
  en: {
    common: {
      save: 'Save',
      cancel: 'Cancel',
      delete: 'Delete',
      edit: 'Edit',
      create: 'Create',
      update: 'Update',
      search: 'Search',
      loading: 'Loading...',
      error: 'Error',
      success: 'Success',
      confirm: 'Confirm',
      close: 'Close',
      back: 'Back',
      next: 'Next',
      previous: 'Previous',
      actions: 'Actions',
      status: 'Status',
      date: 'Date',
      time: 'Time',
      name: 'Name',
      description: 'Description',
      email: 'Email',
      password: 'Password',
      login: 'Login',
      logout: 'Logout',
      register: 'Register',
      settings: 'Settings',
      profile: 'Profile',
      dashboard: 'Dashboard',
      yes: 'Yes',
      no: 'No',
    },
    nav: {
      dashboard: 'Dashboard',
      agents: 'Agents',
      libraries: 'Libraries',
      calls: 'Calls',
      integrations: 'Integrations',
      phoneNumbers: 'Phone Numbers',
      callbacks: 'Callbacks',
      apiKeys: 'API Keys',
      support: 'Support',
      settings: 'Settings',
      admin: 'Administration',
      billing: 'Billing',
      usage: 'Usage',
      security: 'Security',
    },
    dashboard: {
      title: 'Dashboard',
      welcome: 'Welcome',
      totalAgents: 'Total Agents',
      totalCalls: 'Total Calls',
      activeCalls: 'Active Calls',
      recentCalls: 'Recent Calls',
    },
    agents: {
      title: 'Agents',
      createAgent: 'Create Agent',
      editAgent: 'Edit Agent',
      deleteAgent: 'Delete Agent',
      agentName: 'Agent Name',
      agentDescription: 'Description',
      systemPrompt: 'System Prompt',
      greeting: 'Greeting',
      language: 'Language',
      voiceId: 'Voice ID',
      voiceGender: 'Voice Gender',
      isActive: 'Active',
      isPublic: 'Public',
      noAgents: 'No Agents',
      createFirstAgent: 'Create your first agent',
    },
    libraries: {
      title: 'Agent Libraries',
      subtitle: 'Browse and save agent templates to quickly create new agents',
      publicLibraries: 'Public Libraries',
      myLibraries: 'My Libraries',
      createLibrary: 'Create Library',
      createPublicLibrary: 'Create Public Library',
      editLibrary: 'Edit Library',
      deleteLibrary: 'Delete Library',
      useTemplate: 'Use Template',
      saveToMyLibraries: 'Save to My Libraries',
      category: 'Category',
      allCategories: 'All Categories',
      searchPlaceholder: 'Search libraries by name, description, or prompt...',
      noLibraries: 'No Libraries',
      createNewAgent: 'Create New Agent',
      applyToAgent: 'Apply to Agent',
      selectAgent: 'Select Agent',
      selectOption: 'Select Option',
      createNewAgentOption: 'Create New Agent',
      applyToExistingAgent: 'Apply to Existing Agent',
      libraryUpdated: 'Library updated successfully',
      libraryCreated: 'Public library created successfully',
      libraryDeleted: 'Library deleted successfully',
      librarySaved: 'Library saved successfully',
    },
    calls: {
      title: 'Calls',
      callHistory: 'Call History',
      totalCalls: 'Total Calls',
      duration: 'Duration',
      cost: 'Cost',
      status: 'Status',
      from: 'From',
      to: 'To',
      date: 'Date',
      details: 'Details',
      transcript: 'Transcript',
      summary: 'Summary',
      messages: 'Messages',
      sendEmail: 'Send Email',
      emailSent: 'Email Sent',
      favorite: 'Favorite',
      unfavorite: 'Unfavorite',
      noCalls: 'No Calls',
      loading: 'Loading...',
    },
    phoneNumbers: {
      title: 'Phone Numbers',
      subtitle: 'Manage phone numbers for your voice agents',
      managePhoneNumbers: 'Manage phone numbers for your voice agents',
      addPhoneNumber: 'Add Phone Number',
      editPhoneNumber: 'Edit Phone Number',
      deletePhoneNumber: 'Delete Phone Number',
      phoneNumber: 'Phone Number',
      agent: 'Agent',
      status: 'Status',
      noPhoneNumbers: 'No Phone Numbers',
      requestNewNumber: 'Request New Number',
      addExistingNumber: 'Add Existing Number',
      noPhoneNumbersDesc: 'Add your existing Zadarma number or request a new one',
      monthly: 'Monthly:',
      perMinute: 'Per minute:',
      pbxRouting: 'PBX Routing',
      extension: 'Extension:',
      auto: 'Auto',
      businessHours: 'Business hours:',
      afterHours: 'After hours:',
      pbxNotConfigured: 'PBX menu not configured yet',
      pbxNotConfiguredDesc: 'Calls route directly to the assigned agent.',
      uploadDocuments: 'Upload Documents',
      changeAgent: 'Change Agent',
      assignAgent: 'Assign Agent',
      configurePBX: 'Configure PBX',
      verificationDocuments: 'Verification Documents',
      noDocumentsUploaded: 'No documents uploaded yet',
      addExistingPhoneNumber: 'Add Existing Phone Number',
      addExistingDesc: 'Add a phone number you already own on Zadarma (e.g., +3242833288)',
      phoneNumberLabel: 'Phone Number *',
      phoneNumberPlaceholder: '+3242833288',
      phoneNumberHelper: 'Include country code (e.g., +32 for Belgium)',
      countryCode: 'Country Code',
      businessName: 'Business Name',
      businessNameOptional: 'Business Name (Optional)',
      businessNamePlaceholder: 'Your Company Name',
      adding: 'Adding...',
      addPhoneNumberButton: 'Add Phone Number',
      requestNewPhoneNumber: 'Request New Phone Number',
      businessType: 'Business Type',
      businessAddress: 'Business Address',
      company: 'Company',
      individual: 'Individual',
      uploadVerificationDocument: 'Upload Verification Document',
      documentType: 'Document Type',
      file: 'File',
      uploadDocument: 'Upload Document',
      uploadDocumentButton: 'Upload',
      uploading: 'Uploading...',
      selectAnAgent: 'Select an Agent',
      noAgentsAvailable: 'No agents available',
      assignAgentButton: 'Assign Agent',
      pbxConfiguration: 'PBX Configuration',
      timezone: 'Timezone',
      openTime: 'Open Time',
      closeTime: 'Close Time',
      days: 'Days',
      menuOptions: 'Menu Options',
      key: 'Key',
      label: 'Label',
      destinationType: 'Destination Type',
      destinationValue: 'Destination Value',
      destination: 'Destination',
      addMenuOption: 'Add Menu Option',
      afterHoursRouting: 'After-Hours Routing',
      message: 'Message',
      savePBX: 'Save PBX',
      saving: 'Saving...',
      assignAgentToPhoneNumber: 'Assign Agent to Phone Number',
      activeDays: 'Active Days',
      optional: 'optional',
      requesting: 'Requesting...',
      assigning: 'Assigning...',
      phoneNumberPlaceholderRequest: '+33123456789',
      createAgentFirst: 'Create an agent first to assign to this number',
      uploadDocumentsFor: 'Upload documents for',
      speakToSales: 'Speak to sales',
      option: 'Option',
      chooseAgentDescription: 'Choose which agent will handle calls to',
      notConfigured: 'Not configured',
      connectToAIAgent: 'Connect to AI agent',
      sendToVoicemail: 'Send to voicemail',
      forwardTo: 'Forward to',
      externalNumber: 'external number',
      externalDestination: 'External destination:',
      customRouting: 'Custom routing',
      active: 'Active',
      inactive: 'Inactive',
      pendingVerification: 'Pending Verification',
      configured: 'Configured',
      notConfiguredStatus: 'Not Configured',
      unknownAgent: 'Unknown Agent',
      phoneNumberAddedSuccess: 'Phone number added successfully! You can now assign it to an agent.',
      phoneNumberRequestedSuccess: 'Phone number request submitted successfully',
      documentUploadedSuccess: 'Document uploaded successfully',
      agentAssignedSuccess: 'Agent assigned successfully',
      pbxSavedSuccess: 'PBX configuration saved successfully',
      deleteConfirm: 'Are you sure you want to delete this phone number?',
      deleteSuccess: 'Phone number deleted successfully',
      deleteError: 'Failed to delete phone number',
      createSuccess: 'Phone number created successfully',
      createError: 'Failed to create phone number',
      updateSuccess: 'Phone number updated successfully',
      updateError: 'Failed to update phone number',
    },
    apiKeys: {
      title: 'API Keys',
      createApiKey: 'Create API Key',
      deleteApiKey: 'Delete API Key',
      keyName: 'Key Name',
      apiKey: 'API Key',
      createdAt: 'Created At',
      lastUsed: 'Last Used',
      noApiKeys: 'No API Keys',
    },
    support: {
      title: 'Support',
      createTicket: 'Create Ticket',
      tickets: 'Tickets',
      subject: 'Subject',
      message: 'Message',
      status: 'Status',
      priority: 'Priority',
      createdAt: 'Created At',
      noTickets: 'No Tickets',
    },
    billing: {
      title: 'Billing',
      currentPlan: 'Current Plan',
      credits: 'Credits',
      usage: 'Usage',
      paymentMethod: 'Payment Method',
      invoices: 'Invoices',
      noInvoices: 'No Invoices',
    },
    settings: {
      title: 'Settings',
      general: 'General',
      security: 'Security',
      notifications: 'Notifications',
      language: 'Language',
      theme: 'Theme',
      light: 'Light',
      dark: 'Dark',
      system: 'System',
    },
    auth: {
      login: 'Login',
      logout: 'Logout',
      register: 'Register',
      email: 'Email',
      password: 'Password',
      confirmPassword: 'Confirm Password',
      fullName: 'Full Name',
      loginSuccess: 'Login successful!',
      loginError: 'Login error',
      registerSuccess: 'Registration successful!',
      registerError: 'Registration error',
      noAccount: 'Don\'t have an account yet?',
      createAccount: 'Create an account',
      hasAccount: 'Already have an account?',
      loginHere: 'Login here',
      connecting: 'Connecting...',
      connect: 'Connect',
    },
    agentForm: {
      backToAgents: 'Back to Agents',
      createNewAgent: 'Create New Agent',
      editAgent: 'Edit Agent',
      configureDetails: 'Configure details, behavior, and language for your AI agent.',
      agentName: 'Agent Name *',
      agentNamePlaceholder: 'Customer Support Bot',
      description: 'Description',
      descriptionPlaceholder: 'Short description of your agent...',
      systemPrompt: 'System Prompt *',
      systemPromptPlaceholder: 'You are an AI assistant...',
      greeting: 'Greeting',
      greetingPlaceholder: 'Hello, I\'m a assistant from Weedoo. How can I help you?',
      language: 'Language *',
      voiceId: 'Voice ID',
      voiceGender: 'Voice Gender',
      isActive: 'Active',
      isPublic: 'Public',
      ragEnabled: 'Knowledge Base Enabled',
      agentCreated: '🎉 Agent created successfully',
      agentUpdated: '✅ Agent updated successfully',
      agentCreateError: 'Failed to save agent.',
      agentUpdateError: 'Failed to save agent.',
      saveAgentFirst: 'Please save the agent first before uploading documents',
      uploadDocument: 'Upload Document',
      addWebsite: 'Add Website',
      websiteUrl: 'Website URL',
      documents: 'Documents',
      noDocuments: 'No documents',
      deleteDocument: 'Delete Document',
      processing: 'Processing',
      completed: 'Completed',
      failed: 'Failed',
    },
    dashboard: {
      welcomeMessage: 'Welcome! Here\'s an overview of your voice agents.',
      totalAgentsSubtitle: 'Active voice agents',
      totalCallsSubtitle: 'Calls made',
      totalMinutes: 'Minutes Used',
      totalMinutesSubtitle: 'Total call time',
      totalCost: 'Total Cost',
      totalCostSubtitle: 'Cumulative expenses',
      statsLoadError: 'Failed to load statistics',
      quickActions: 'Quick Actions',
    },
    agentsPage: {
      title: 'Voice Agents',
      subtitle: 'Manage, start, and improve your AI voice agents',
      newAgent: 'New Agent',
      noAgentsYet: 'No Agents Yet',
      noAgentsDescription: 'You don\'t have any voice agents yet. Start by creating your first one below.',
      createAgent: 'Create Agent',
      active: 'Active',
      inactive: 'Inactive',
      private: 'Private',
      public: 'Public',
      noDescription: 'No description provided.',
      test: 'Test',
      edit: 'Edit',
      delete: 'Delete',
      deleteConfirm: 'Are you sure you want to delete this agent?',
      deleteSuccess: 'Agent deleted successfully',
      deleteError: 'Failed to delete agent',
      loadError: 'Failed to load agents',
    },
    callsPage: {
      callHistory: 'Call History',
      allCalls: 'All Calls',
      favorites: 'Favorites',
      filters: 'Filters',
      status: 'Status',
      allStatuses: 'All Statuses',
      actionRequired: 'Action Required',
      searchPlaceholder: 'Search calls...',
      noCallsFound: 'No calls found',
      bulkDelete: 'Delete Selected',
      bulkFavorite: 'Add to Favorites',
      bulkUnfavorite: 'Remove from Favorites',
      deleteConfirm: 'Are you sure you want to delete these calls?',
      deleteSuccess: 'Calls deleted successfully',
      deleteError: 'Failed to delete calls',
      favoriteSuccess: 'Added to favorites',
      unfavoriteSuccess: 'Removed from favorites',
      favoriteError: 'Failed to update',
      page: 'Page',
      of: 'of',
      showing: 'Showing',
      results: 'results',
      minutes: 'minutes',
      cost: 'Cost',
      viewDetails: 'View Details',
      noSummary: 'No summary available',
      noTranscript: 'No transcript available',
      keyPoints: 'Key Points',
      actionItems: 'Action Items',
      sentiment: 'Sentiment',
      callbackRequested: 'Callback Requested',
      sendEmail: 'Send Email',
      emailSent: 'Email Sent',
      emailError: 'Failed to send email',
      close: 'Close',
      callDetails: 'Call Details',
      sessionId: 'Session ID',
      duration: 'Duration',
      regenerateSummary: 'Regenerate Summary',
      regenerating: 'Regenerating...',
      generateSummary: 'Generate Summary',
      followUpActions: 'Follow-up Actions Detected',
      actionItems: 'Action Items Details',
      summary: 'Summary',
      messages: 'Messages',
      live: 'Live',
      visitor: 'Visitor',
      system: 'System',
      agent: 'Agent',
      compose: 'Compose',
      to: 'To',
      subject: 'Subject',
      message: 'Message',
      sending: 'Sending...',
      noCalls: 'No calls yet',
      favorite: 'Add to favorites',
      unfavorite: 'Remove from favorites',
      loading: 'Loading...',
    },
    categories: {
      realEstate: 'Real Estate',
      customerService: 'Customer Service',
      sales: 'Sales',
      support: 'Support',
      marketing: 'Marketing',
      hr: 'HR',
      healthcare: 'Healthcare',
      education: 'Education',
      finance: 'Finance',
      legal: 'Legal',
      general: 'General',
    },
    register: {
      title: 'Create Account',
      fullName: 'Full Name',
      confirmPassword: 'Confirm Password',
      passwordMismatch: 'Passwords do not match',
      passwordMinLength: 'Password must be at least 8 characters',
      passwordMaxLength: 'Password cannot exceed 72 characters',
      passwordHint: '8-72 characters',
      creating: 'Creating...',
      createAccount: 'Create Account',
      hasAccount: 'Already have an account?',
      loginHere: 'Login here',
      success: 'Account created successfully! Please wait for administrator approval before logging in.',
      error: 'Error creating account',
    },
    phoneNumbers: {
      subtitle: 'Manage phone numbers for your voice agents',
      addPhoneNumber: 'Add Phone Number',
      editPhoneNumber: 'Edit Phone Number',
      deletePhoneNumber: 'Delete Phone Number',
      phoneNumber: 'Phone Number',
      agent: 'Agent',
      status: 'Status',
      noPhoneNumbers: 'No Phone Numbers',
      deleteConfirm: 'Are you sure you want to delete this phone number?',
      deleteSuccess: 'Phone number deleted successfully',
      deleteError: 'Failed to delete phone number',
      createSuccess: 'Phone number created successfully',
      createError: 'Failed to create phone number',
      updateSuccess: 'Phone number updated successfully',
      updateError: 'Failed to update phone number',
    },
    apiKeys: {
      subtitle: 'Securely manage your access keys for voice agent APIs.',
      createApiKey: 'New API Key',
      deleteApiKey: 'Delete API Key',
      keyName: 'Key Name',
      apiKey: 'API Key',
      createdAt: 'Created At',
      lastUsed: 'Last Used',
      noApiKeys: 'No API Keys Found',
      deleteConfirm: 'Are you sure you want to delete this API key?',
      deleteSuccess: 'API key deleted successfully',
      deleteError: 'Failed to delete API key',
      createSuccess: 'API key created successfully',
      createError: 'Failed to create API key',
      copySuccess: 'API key copied to clipboard',
      never: 'Never',
    },
    support: {
      subtitle: 'Contact our team for any questions or issues',
      createTicket: 'Create Ticket',
      tickets: 'Tickets',
      subject: 'Subject',
      message: 'Message',
      status: 'Status',
      priority: 'Priority',
      createdAt: 'Created At',
      noTickets: 'No Tickets',
      createSuccess: 'Your request has been sent successfully!',
      createError: 'Error sending your request',
      low: 'Low',
      medium: 'Medium',
      high: 'High',
      open: 'Open',
      closed: 'Closed',
      inProgress: 'In Progress',
    },
    billing: {
      subtitle: 'Manage your billing and payment methods',
      currentPlan: 'Current Plan',
      credits: 'Credits',
      usage: 'Usage',
      paymentMethod: 'Payment Method',
      invoices: 'Invoices',
      noInvoices: 'No Invoices',
      addPaymentMethod: 'Add Payment Method',
      updatePaymentMethod: 'Update Payment Method',
      noPaymentMethod: 'No Payment Method',
    },
    profile: {
      title: 'Profile',
      subtitle: 'Manage your personal information',
      personalInfo: 'Personal Information',
      updateSuccess: 'Profile updated successfully',
      updateError: 'Failed to update profile',
      changePassword: 'Change Password',
      currentPassword: 'Current Password',
      newPassword: 'New Password',
      confirmNewPassword: 'Confirm New Password',
      passwordChanged: 'Password changed successfully',
      passwordError: 'Failed to change password',
    },
    security: {
      title: 'Security',
      subtitle: 'Manage your security settings',
      twoFactor: 'Two-Factor Authentication',
      apiKeys: 'API Keys',
      sessions: 'Active Sessions',
      loginHistory: 'Login History',
    },
    usage: {
      title: 'Usage',
      subtitle: 'View your usage and statistics',
      period: 'Period',
      last7Days: 'Last 7 Days',
      last30Days: 'Last 30 Days',
      last90Days: 'Last 90 Days',
      thisMonth: 'This Month',
      lastMonth: 'Last Month',
      calls: 'Calls',
      minutes: 'Minutes',
      cost: 'Cost',
    },
    callbacks: {
      title: 'Callbacks',
      subtitle: 'Manage your scheduled callbacks',
      noCallbacks: 'No Callbacks',
      scheduled: 'Scheduled',
      completed: 'Completed',
      cancelled: 'Cancelled',
      pending: 'Pending',
      contacted: 'Contacted',
      all: 'All',
      callbackRequests: 'Callback Requests',
      manageCallbacks: 'Manage callback requests from your voice agents',
      noCallbackRequests: 'No callback requests',
      noCallbackRequestsDesc: 'Callback requests will appear here when agents detect the need for human intervention',
      priority: 'Priority',
      urgent: 'Urgent',
      high: 'High',
      normal: 'Normal',
      low: 'Low',
      status: 'Status',
      callerName: 'Caller Name',
      callerPhone: 'Caller Phone',
      callerEmail: 'Caller Email',
      preferredCallbackTime: 'Preferred Callback Time',
      notes: 'Notes',
      resolution: 'Resolution',
      assignedTo: 'Assigned To',
      viewCall: 'View Call',
      update: 'Update',
      updateCallbackRequest: 'Update Callback Request',
      assignedToPlaceholder: 'Name or email',
      notesPlaceholder: 'Additional notes or comments',
      resolutionPlaceholder: 'How was this resolved?',
      updating: 'Updating...',
      updateButton: 'Update',
      updateSuccess: 'Callback updated successfully!',
      updateError: 'Error updating callback',
      createdAt: 'Created at',
    },
    integrations: {
      title: 'Integrations',
      subtitle: 'Connect your calendar, email, CRM, and other business tools',
      noIntegrations: 'No Integrations',
      addIntegration: 'Add Integration',
      editIntegration: 'Edit Integration',
      deleteIntegration: 'Delete Integration',
      newIntegration: 'New Integration',
      createIntegration: 'Create Integration',
      allTypes: 'All Types',
      allStatuses: 'All Statuses',
      active: 'Active',
      inactive: 'Inactive',
      error: 'Error',
      pendingAuth: 'Pending Auth',
      testConnection: 'Test Connection',
      syncData: 'Sync Data',
      activate: 'Activate',
      deactivate: 'Deactivate',
      lastSynced: 'Last synced:',
      deleteConfirm: 'Are you sure you want to delete this integration?',
      deleteSuccess: 'Integration deleted successfully',
      deleteError: 'Failed to delete integration',
      testSuccess: 'Connection test successful',
      testError: 'Connection test failed',
      syncSuccess: 'Sync completed successfully',
      syncError: 'Sync failed',
      activateSuccess: 'Integration activated',
      activateError: 'Failed to update integration',
      loadError: 'Failed to load integrations',
      backToIntegrations: 'Back to Integrations',
      newIntegrationTitle: 'New Integration',
      editIntegrationTitle: 'Edit Integration',
      name: 'Name *',
      namePlaceholder: 'My Google Calendar',
      description: 'Description',
      descriptionPlaceholder: 'Optional description for this integration',
      integrationType: 'Integration Type *',
      selectType: 'Select a type',
      provider: 'Provider *',
      selectProvider: 'Select a provider',
      configuration: 'Configuration',
      headersJson: 'Headers (JSON)',
      credentialsWarning: '⚠️ Credentials are stored securely. Make sure to use valid credentials for your integration.',
      saving: 'Saving...',
      updateIntegration: 'Update Integration',
      createIntegrationButton: 'Create Integration',
      updateSuccess: '✅ Integration updated successfully',
      createSuccess: '🎉 Integration created successfully',
      saveError: 'Failed to save integration.',
      loadIntegrationError: 'Failed to load integration.',
      typeCalendar: '📅 Calendar',
      typeEmail: '📧 Email',
      typeContactManagement: '👥 Contacts',
      typeDatabase: '💾 Database',
      typeCRM: '📊 CRM',
      typeAccounting: '💰 Accounting',
      typeOther: '🔧 Other',
    },
    admin: {
      overview: 'Overview',
      users: 'Users',
      agents: 'Agents',
      support: 'Support',
      overviewTitle: 'Admin Overview',
      overviewSubtitle: 'Platform overview: users, agents, calls, and support.',
      usersTitle: 'User Management',
      agentsTitle: 'Agent Management',
      supportTitle: 'Support',
      totalUsers: 'Users',
      activeUsers: 'active',
      pendingUsers: 'pending',
      totalAgents: 'Agents',
      activeAgents: 'active',
      publicAgents: 'public',
      totalCalls: 'Calls (30d)',
      openTickets: 'Open Tickets',
      usage: 'Usage',
      revenue: 'Revenue',
      recentUsers: 'Recent Users',
      recentAgents: 'Recent Agents',
      recentTickets: 'Recent Tickets',
      approved: 'Approved',
      pending: 'Pending',
      active: 'Active',
      inactive: 'Inactive',
      public: 'Public',
      private: 'Private',
      approve: 'Approve',
      reject: 'Reject',
      activate: 'Activate',
      deactivate: 'Deactivate',
      makeAdmin: 'Make Admin',
      removeAdmin: 'Remove Admin',
      approveSuccess: 'User approved',
      rejectSuccess: 'User rejected',
      activateSuccess: 'User activated',
      deactivateSuccess: 'User deactivated',
      makeAdminSuccess: 'Admin added',
      removeAdminSuccess: 'Admin removed',
    },
    quickActions: {
      createAgent: 'Create Agent',
      createAgentDesc: 'Build a custom voice agent for your use case',
      manageApiKeys: 'Manage API Keys',
      manageApiKeysDesc: 'Create and manage your API access keys for integration',
      tryDemo: 'Try Demo',
      tryDemoDesc: 'Test the public demonstration agent live',
    },
    agentDocuments: {
      title: 'RAG Documents',
      backToAgents: 'Back to Agents',
      agent: 'Agent:',
      ragEnabled: 'RAG Enabled:',
      addKnowledgeSources: 'Add Knowledge Sources',
      uploadPdfDocument: '📄 Upload PDF Document',
      clickToUpload: 'Click to upload or drag and drop',
      pdfFilesOnly: 'PDF files only, max 10MB (supports scanned PDFs)',
      chooseFile: 'Choose File',
      scrapeWebsite: '🌐 Scrape Website',
      websiteUrlPlaceholder: 'https://example.com/documentation',
      scrape: 'Scrape',
      howItWorks: 'How it works:',
      howItWorksDesc: 'Add PDF documents or website URLs to give your agent knowledge. Content will be processed, chunked, and embedded for semantic search during conversations.',
      uploadedDocuments: 'Uploaded Documents',
      noDocumentsUploaded: 'No documents uploaded yet',
      source: 'Source',
      size: 'Size',
      pages: 'Pages',
      chunks: 'Chunks',
      added: 'Added:',
      processed: 'Processed:',
      deleteDocument: 'Delete document',
      deleteConfirm: 'Are you sure you want to delete this document?',
      onlyPdfSupported: 'Only PDF files are supported',
      fileSizeLimit: 'File size must be less than 10MB',
      uploadingFile: 'Uploading file...',
      processingEmbeddings: 'Processing and generating embeddings...',
      scrapingWebsite: 'Scraping website...',
      enterWebsiteUrl: 'Please enter a website URL',
      enterValidUrl: 'Please enter a valid URL (e.g., https://example.com)',
      uploadSuccess: 'Document uploaded successfully',
      uploadError: 'Failed to upload document',
      deleteSuccess: 'Document deleted successfully',
      deleteError: 'Failed to delete document',
      loadError: 'Failed to load data',
      toggleRAGError: 'Failed to toggle RAG',
      completed: 'Completed',
      processing: 'Processing',
      failed: 'Failed',
      pending: 'Pending',
    },
    agentEmbed: {
      title: 'Agent Embed',
      backToAgents: 'Back to Agents',
      embedConfiguration: 'Embed Configuration',
      enableEmbed: 'Enable Embed',
      widgetColor: 'Widget Color',
      widgetPosition: 'Widget Position',
      greetingMessage: 'Greeting Message',
      allowedDomains: 'Allowed Domains',
      addDomain: 'Add Domain',
      domainPlaceholder: 'example.com',
      embedCode: 'Embed Code',
      copyCode: 'Copy Code',
      codeCopied: 'Code copied!',
      saveConfig: 'Save Configuration',
      saving: 'Saving...',
      saveSuccess: 'Embed configuration saved successfully!',
      saveError: 'Error saving configuration',
      bottomRight: 'Bottom Right',
      bottomLeft: 'Bottom Left',
      topRight: 'Top Right',
      topLeft: 'Top Left',
    },
    callDetail: {
      backToCalls: 'Back to Calls',
      callDetails: 'Call Details',
      generateSummary: 'Generate Summary',
      regenerating: 'Regenerating...',
      regenerateSummary: 'Regenerate Summary',
      generating: 'Generating...',
      summaryGenerated: 'Summary generated successfully',
      summaryError: 'Error generating summary',
      callNotFound: 'Call not found',
      overview: 'Overview',
      transcript: 'Transcript',
      duration: 'Duration',
      cost: 'Cost',
      status: 'Status',
      callSummary: 'Call Summary',
      sentiment: 'Sentiment:',
      detectedActions: 'Detected Actions',
      keyPoints: 'Key Points:',
      actionItems: 'Action Items',
      conversation: 'Conversation',
      user: 'User',
      agent: 'Agent',
      fullTranscript: 'Full Transcript',
      transcriptNotAvailable: 'Transcript not available for this call',
    },
    publicAgent: {
      agentNotFound: 'Agent not found or not public',
      agentInactive: 'This agent is currently inactive',
      loadError: 'Failed to load agent',
      connect: 'Connect',
      disconnect: 'Disconnect',
      connecting: 'Connecting...',
      disconnecting: 'Disconnecting...',
      recording: 'Recording',
      stop: 'Stop',
      sendMessage: 'Send Message',
      sending: 'Sending...',
      messagePlaceholder: 'Type your message...',
      disconnectFirst: 'Disconnect first to change agents',
    },
    demo: {
      title: 'Demo',
      selectAgent: 'Select Agent',
      noAgentsAvailable: 'No demo agents available',
      loadError: 'Unable to load demo agents',
      connect: 'Connect',
      disconnect: 'Disconnect',
      connecting: 'Connecting...',
      disconnecting: 'Disconnecting...',
      recording: 'Recording',
      stop: 'Stop',
      sendMessage: 'Send Message',
      sending: 'Sending...',
      messagePlaceholder: 'Type your message...',
      disconnectFirst: 'Disconnect first to change agents',
    },
    adminSupport: {
      title: 'Support',
      subtitle: 'Manage support tickets',
      searchPlaceholder: 'Search tickets...',
      allStatuses: 'All Statuses',
      allPriorities: 'All Priorities',
      open: 'Open',
      inProgress: 'In Progress',
      resolved: 'Resolved',
      closed: 'Closed',
      low: 'Low',
      medium: 'Medium',
      high: 'High',
      urgent: 'Urgent',
      statusUpdated: 'Status updated',
      priorityUpdated: 'Priority updated',
      updateError: 'Failed to update',
      loadError: 'Unable to load tickets',
      noTickets: 'No Tickets',
      ticketNumber: 'Ticket Number',
      subject: 'Subject',
      name: 'Name',
      email: 'Email',
      category: 'Category',
      createdAt: 'Created At',
      updatedAt: 'Updated At',
      responses: 'Responses',
      lastResponse: 'Last Response',
      never: 'Never',
      updateStatus: 'Update Status',
      updatePriority: 'Update Priority',
    },
    landing: {
      agentsPublics: 'Public Agents',
      demo: 'Demo',
      commencer: 'Get Started',
      tableauDeBord: 'Dashboard',
      deconnexion: 'Logout',
      agentsVocaux: 'Voice Agents',
      intelligents: 'Intelligent',
      enFrancais: 'in French',
      heroDescription: 'Create AI voice agents that speak French naturally. Ultra-low latency, simple integration.',
      commencerGratuitement: 'Get Started Free',
      essayerDemo: 'Try Demo',
      latenceMoyenne: 'Average latency',
      disponibilite: 'Availability',
      langues: 'Languages',
      clients: 'Clients',
      fonctionnalitesPuissantes: 'Powerful Features',
      fonctionnalitesDesc: 'Everything you need to create professional voice agents',
      latenceUltraFaible: 'Ultra-Low Latency',
      latenceDesc: 'Response in under 500ms for natural conversation',
      francaisNatif: 'Native French',
      francaisDesc: 'Natural and fluent French understanding and generation',
      iaAvancee: 'Advanced AI',
      iaDesc: 'GPT-4 and cutting-edge models for intelligent conversations',
      backofficeComplet: 'Complete Backoffice',
      backofficeDesc: 'Manage your agents, calls, analytics and integrations in one place',
      integrationCRM: 'CRM Integration',
      crmDesc: 'Connect your CRM to sync data in real-time',
      apiSimple: 'Simple API',
      apiDesc: 'Easy integration with our well-documented REST API',
      essayezMaintenant: 'Try Now',
      agentsPublicsDisponibles: 'Available Public Agents',
      agentsPublicsDesc: 'Test our demonstration agents live',
      essayerMaintenant: 'Try Now',
      appeler: 'Call',
      aucunAgentPublic: 'No public agents available',
      creerPremierAgent: 'Create your first agent to get started',
      pourquoiChoisir: 'Why Choose Us',
      config5Minutes: '5-Minute Setup',
      aucuneExpertise: 'No technical expertise required',
      scalingAutomatique: 'Automatic Scaling',
      support247: '24/7 Support',
      securiteRGPD: 'Security & GDPR',
      integrationsIllimitees: 'Unlimited Integrations',
      securiteConformite: 'Security & Compliance',
      securiteDesc: 'Your data is protected and compliant with regulations',
      cryptageSSL: 'SSL Encryption',
      conforme: 'GDPR Compliant',
      uptime: '99.9% Uptime',
      pretTransformer: 'Ready to Transform',
      pretDesc: 'Your Communication',
      commencerMaintenant: 'Get Started Now',
      tousDroitsReserves: 'All rights reserved',
      documentation: 'Documentation',
      support: 'Support',
      knowledgeBase: 'Knowledge Base',
    },
  },
}

export const useTranslation = () => {
  const { language } = useLanguageStore()
  const translation = translations[language] || translations.fr // Fallback to French if language is undefined
  return translation
}

export default translations

