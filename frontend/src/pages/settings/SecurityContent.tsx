import { useState, useEffect } from 'react'
import { securityAPI } from '@/lib/api'
import { useTranslation } from '@/lib/translations'
import toast from 'react-hot-toast'

interface DomainAllowlist {
  id: number
  domain: string
  description: string | null
  is_active: boolean
  public_key: string
  verified: boolean
  verification_token: string | null
  total_requests: number
  last_used_at: string | null
  created_at: string
}

interface IPAllowlist {
  id: number
  ip_address: string
  ip_range: string | null
  description: string | null
  is_active: boolean
  total_requests: number
  last_used_at: string | null
  created_at: string
}

interface SecurityLog {
  id: number
  event_type: string
  severity: string
  message: string
  ip_address: string | null
  user_agent: string | null
  endpoint: string | null
  created_at: string
}

export default function SecurityContent() {
  const t = useTranslation()
  const [domains, setDomains] = useState<DomainAllowlist[]>([])
  const [ips, setIPs] = useState<IPAllowlist[]>([])
  const [logs, setLogs] = useState<SecurityLog[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'domains' | 'ips' | 'logs'>('domains')
  
  // Form states
  const [showDomainModal, setShowDomainModal] = useState(false)
  const [showIPModal, setShowIPModal] = useState(false)
  const [domainForm, setDomainForm] = useState({ domain: '', description: '' })
  const [ipForm, setIPForm] = useState({ ip_address: '', ip_range: '', description: '' })
  
  // Selected key for display
  const [selectedKey, setSelectedKey] = useState<string | null>(null)

  useEffect(() => {
    loadSecurityData()
  }, [])

  const loadSecurityData = async () => {
    try {
      setLoading(true)
      const [domainsRes, ipsRes, logsRes] = await Promise.all([
        securityAPI.getDomains(),
        securityAPI.getIPs(),
        securityAPI.getLogs(),
      ])
      
      setDomains(domainsRes.data)
      setIPs(ipsRes.data)
      setLogs(logsRes.data)
    } catch (error) {
      console.error('Error loading security data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleAddDomain = async () => {
    if (!domainForm.domain) {
      toast.error(t.common.status === 'Statut' ? 'Veuillez entrer un domaine' : 'Please enter a domain')
      return
    }

    try {
      const response = await securityAPI.createDomain(domainForm)
      setDomains([response.data, ...domains])
      setDomainForm({ domain: '', description: '' })
      setShowDomainModal(false)
      setSelectedKey(response.data.public_key)
      toast.success(t.common.status === 'Statut' ? 'Domaine ajouté avec succès ! Votre clé publique a été générée.' : 'Domain added successfully! Your public key has been generated.')
    } catch (error: any) {
      console.error('Error adding domain:', error)
      toast.error(error.response?.data?.detail || (t.common.status === 'Statut' ? 'Échec de l\'ajout du domaine' : 'Failed to add domain'))
    }
  }

  const handleAddIP = async () => {
    if (!ipForm.ip_address) {
      toast.error(t.common.status === 'Statut' ? 'Veuillez entrer une adresse IP' : 'Please enter an IP address')
      return
    }

    try {
      const response = await securityAPI.createIP(ipForm)
      setIPs([response.data, ...ips])
      setIPForm({ ip_address: '', ip_range: '', description: '' })
      setShowIPModal(false)
      toast.success(t.common.status === 'Statut' ? 'IP ajoutée avec succès' : 'IP added successfully')
    } catch (error: any) {
      console.error('Error adding IP:', error)
      toast.error(error.response?.data?.detail || (t.common.status === 'Statut' ? 'Échec de l\'ajout de l\'IP' : 'Failed to add IP'))
    }
  }

  const handleDeleteDomain = async (id: number) => {
    if (!confirm(t.common.status === 'Statut' ? 'Êtes-vous sûr de vouloir supprimer ce domaine ?' : 'Are you sure you want to remove this domain?')) return

    try {
      await securityAPI.deleteDomain(id)
      setDomains(domains.filter(d => d.id !== id))
      toast.success(t.common.status === 'Statut' ? 'Domaine supprimé avec succès' : 'Domain deleted successfully')
    } catch (error) {
      console.error('Error deleting domain:', error)
      toast.error(t.common.status === 'Statut' ? 'Échec de la suppression du domaine' : 'Failed to delete domain')
    }
  }

  const handleDeleteIP = async (id: number) => {
    if (!confirm(t.common.status === 'Statut' ? 'Êtes-vous sûr de vouloir supprimer cette IP ?' : 'Are you sure you want to remove this IP?')) return

    try {
      await securityAPI.deleteIP(id)
      setIPs(ips.filter(ip => ip.id !== id))
      toast.success(t.common.status === 'Statut' ? 'IP supprimée avec succès' : 'IP deleted successfully')
    } catch (error) {
      console.error('Error deleting IP:', error)
      toast.error(t.common.status === 'Statut' ? 'Échec de la suppression de l\'IP' : 'Failed to delete IP')
    }
  }

  const handleToggleDomain = async (id: number, is_active: boolean) => {
    try {
      const response = await securityAPI.updateDomain(id, { is_active: !is_active })
      setDomains(domains.map(d => d.id === id ? response.data : d))
      toast.success(t.common.status === 'Statut' ? 'Domaine mis à jour' : 'Domain updated')
    } catch (error) {
      console.error('Error toggling domain:', error)
      toast.error(t.common.status === 'Statut' ? 'Échec de la mise à jour du domaine' : 'Failed to update domain')
    }
  }

  const handleToggleIP = async (id: number, is_active: boolean) => {
    try {
      const response = await securityAPI.updateIP(id, { is_active: !is_active })
      setIPs(ips.map(ip => ip.id === id ? response.data : ip))
      toast.success(t.common.status === 'Statut' ? 'IP mise à jour' : 'IP updated')
    } catch (error) {
      console.error('Error toggling IP:', error)
      toast.error(t.common.status === 'Statut' ? 'Échec de la mise à jour de l\'IP' : 'Failed to update IP')
    }
  }

  const handleRegenerateKey = async (id: number) => {
    if (!confirm(t.common.status === 'Statut' ? 'Êtes-vous sûr ? Cela invalidera la clé actuelle.' : 'Are you sure? This will invalidate the current key.')) return

    try {
      const response = await securityAPI.regenerateDomainKey(id)
      setDomains(domains.map(d => d.id === id ? response.data : d))
      setSelectedKey(response.data.public_key)
      toast.success(t.common.status === 'Statut' ? 'Clé régénérée avec succès !' : 'Key regenerated successfully!')
    } catch (error) {
      console.error('Error regenerating key:', error)
      toast.error(t.common.status === 'Statut' ? 'Échec de la régénération de la clé' : 'Failed to regenerate key')
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    toast.success(t.common.status === 'Statut' ? 'Copié dans le presse-papiers !' : 'Copied to clipboard!')
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const getSeverityColor = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical':
        return 'bg-red-100 text-red-800'
      case 'error':
        return 'bg-red-50 text-red-700'
      case 'warning':
        return 'bg-yellow-100 text-yellow-800'
      case 'info':
        return 'bg-blue-100 text-blue-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="max-w-7xl mx-auto">
      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700 mb-6">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('domains')}
            className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'domains'
                ? 'border-indigo-500 text-indigo-600 dark:text-indigo-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
            }`}
          >
            {t.common.status === 'Statut' ? 'Liste blanche des domaines' : 'Domain Allowlist'}
          </button>
          <button
            onClick={() => setActiveTab('ips')}
            className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'ips'
                ? 'border-indigo-500 text-indigo-600 dark:text-indigo-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
            }`}
          >
            {t.common.status === 'Statut' ? 'Liste blanche des IP' : 'IP Allowlist'}
          </button>
          <button
            onClick={() => setActiveTab('logs')}
            className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'logs'
                ? 'border-indigo-500 text-indigo-600 dark:text-indigo-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
            }`}
          >
            {t.security.loginHistory}
          </button>
        </nav>
      </div>

      {/* Domain Allowlist Tab */}
      {activeTab === 'domains' && (
        <div className="space-y-6">
          <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4 mb-6">
            <h3 className="font-semibold text-blue-900 dark:text-blue-300 mb-2">{t.common.status === 'Statut' ? 'À propos de la liste blanche des domaines' : 'About Domain Allowlist'}</h3>
            <p className="text-sm text-blue-800 dark:text-blue-200">
              {t.common.status === 'Statut' ? 'Ajoutez des domaines pour générer des clés publiques qui peuvent être utilisées pour accéder à vos agents vocaux depuis des domaines spécifiques. Ceci est utile pour intégrer des agents vocaux sur votre site web avec des restrictions de clé API.' : 'Add domains to generate public keys that can be used to access your voice agents from specific domains. This is useful for embedding voice agents on your website with API key restrictions.'}
            </p>
          </div>

          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">{t.common.status === 'Statut' ? 'Domaines autorisés' : 'Allowed Domains'}</h2>
            <button
              onClick={() => setShowDomainModal(true)}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
            >
              + {t.common.status === 'Statut' ? 'Ajouter un domaine' : 'Add Domain'}
            </button>
          </div>

          {/* Domain List */}
          <div className="bg-white dark:bg-gray-800 shadow rounded-lg overflow-hidden">
            {loading ? (
              <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="p-6">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-48 animate-pulse"></div>
                          <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-16 animate-pulse"></div>
                        </div>
                        <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-64 mb-3 animate-pulse"></div>
                        <div className="bg-gray-50 rounded p-3 mb-2">
                          <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-24 mb-1 animate-pulse"></div>
                          <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-full animate-pulse"></div>
                        </div>
                        <div className="flex gap-4">
                          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-24 animate-pulse"></div>
                          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-32 animate-pulse"></div>
                        </div>
                      </div>
                      <div className="flex gap-2 ml-4">
                        <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-20 animate-pulse"></div>
                        <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-32 animate-pulse"></div>
                        <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-20 animate-pulse"></div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : domains.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-gray-500 dark:text-gray-400">{t.common.status === 'Statut' ? 'Aucun domaine configuré' : 'No domains configured'}</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {domains.map((domain) => (
                  <div key={domain.id} className="p-6 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{domain.domain}</h3>
                          <span className={`px-2 py-1 text-xs rounded ${domain.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}`}>
                            {domain.is_active ? (t.common.status === 'Statut' ? 'Actif' : 'Active') : (t.common.status === 'Statut' ? 'Inactif' : 'Inactive')}
                          </span>
                          {domain.verified && (
                            <span className="px-2 py-1 text-xs rounded bg-blue-100 text-blue-800">
                              {t.common.status === 'Statut' ? 'Vérifié' : 'Verified'}
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">{domain.description || (t.common.status === 'Statut' ? 'Aucune description' : 'No description')}</p>
                        
                        <div className="bg-gray-50 dark:bg-gray-900 rounded p-3 mb-2">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-semibold text-gray-700 dark:text-gray-300">{t.common.status === 'Statut' ? 'Clé publique :' : 'Public Key:'}</span>
                            <button
                              onClick={() => copyToClipboard(domain.public_key)}
                              className="text-xs text-indigo-600 hover:text-indigo-700"
                            >
                              {t.common.status === 'Statut' ? 'Copier' : 'Copy'}
                            </button>
                          </div>
                          <code className="text-xs text-gray-600 dark:text-gray-300 break-all">{domain.public_key}</code>
                        </div>
                        
                        <div className="flex gap-4 text-sm text-gray-500">
                          <span>{t.common.status === 'Statut' ? 'Requêtes :' : 'Requests:'} {domain.total_requests}</span>
                          <span>{t.common.status === 'Statut' ? 'Créé le :' : 'Created:'} {formatDate(domain.created_at)}</span>
                          {domain.last_used_at && <span>{t.common.status === 'Statut' ? 'Dernière utilisation :' : 'Last used:'} {formatDate(domain.last_used_at)}</span>}
                        </div>
                      </div>
                      
                      <div className="flex gap-2 ml-4">
                        <button
                          onClick={() => handleToggleDomain(domain.id, domain.is_active)}
                          className="px-3 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-900 dark:text-white"
                        >
                          {domain.is_active ? (t.common.status === 'Statut' ? 'Désactiver' : 'Disable') : (t.common.status === 'Statut' ? 'Activer' : 'Enable')}
                        </button>
                        <button
                          onClick={() => handleRegenerateKey(domain.id)}
                          className="px-3 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-900 dark:text-white"
                        >
                          {t.common.status === 'Statut' ? 'Régénérer la clé' : 'Regenerate Key'}
                        </button>
                        <button
                          onClick={() => handleDeleteDomain(domain.id)}
                          className="px-3 py-1 text-sm text-red-600 dark:text-red-400 border border-red-300 dark:border-red-800 rounded hover:bg-red-50 dark:hover:bg-red-900/20"
                        >
                          {t.common.delete}
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* IP Allowlist Tab */}
      {activeTab === 'ips' && (
        <div className="space-y-6">
          <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4 mb-6">
            <h3 className="font-semibold text-blue-900 dark:text-blue-300 mb-2">{t.common.status === 'Statut' ? 'À propos de la liste blanche des IP' : 'About IP Allowlist'}</h3>
            <p className="text-sm text-blue-800 dark:text-blue-200">
              {t.common.status === 'Statut' ? 'Configurez les adresses IP ou les plages (notation CIDR) autorisées à accéder à votre API. Si aucune IP n\'est configurée, toutes les IP sont autorisées. Une fois que vous ajoutez une IP, seules les IP listées auront accès.' : 'Configure IP addresses or ranges (CIDR notation) that are allowed to access your API. If no IPs are configured, all IPs are allowed. Once you add an IP, only listed IPs will have access.'}
            </p>
          </div>

          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">{t.common.status === 'Statut' ? 'Adresses IP autorisées' : 'Allowed IP Addresses'}</h2>
            <button
              onClick={() => setShowIPModal(true)}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
            >
              + {t.common.status === 'Statut' ? 'Ajouter une IP' : 'Add IP'}
            </button>
          </div>

          {/* IP List */}
          <div className="bg-white dark:bg-gray-800 shadow rounded-lg overflow-hidden">
            {loading ? (
              <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="p-6">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-40 animate-pulse"></div>
                          <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-16 animate-pulse"></div>
                        </div>
                        <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-56 mb-3 animate-pulse"></div>
                        <div className="flex gap-4">
                          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-24 animate-pulse"></div>
                          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-32 animate-pulse"></div>
                        </div>
                      </div>
                      <div className="flex gap-2 ml-4">
                        <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-20 animate-pulse"></div>
                        <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-20 animate-pulse"></div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : ips.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-gray-500 dark:text-gray-400">{t.common.status === 'Statut' ? 'Aucune restriction IP configurée (toutes les IP sont autorisées)' : 'No IP restrictions configured (all IPs allowed)'}</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {ips.map((ip) => (
                  <div key={ip.id} className="p-6 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <h3 className="text-lg font-semibold text-gray-900 dark:text-white font-mono">{ip.ip_address}</h3>
                          <span className={`px-2 py-1 text-xs rounded ${ip.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}`}>
                            {ip.is_active ? (t.common.status === 'Statut' ? 'Actif' : 'Active') : (t.common.status === 'Statut' ? 'Inactif' : 'Inactive')}
                          </span>
                        </div>
                        {ip.ip_range && (
                          <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                            {t.common.status === 'Statut' ? 'Plage :' : 'Range:'} <code className="bg-gray-100 dark:bg-gray-900 px-2 py-1 rounded text-gray-900 dark:text-white">{ip.ip_range}</code>
                          </p>
                        )}
                        <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">{ip.description || (t.common.status === 'Statut' ? 'Aucune description' : 'No description')}</p>
                        
                        <div className="flex gap-4 text-sm text-gray-500">
                          <span>{t.common.status === 'Statut' ? 'Requêtes :' : 'Requests:'} {ip.total_requests}</span>
                          <span>{t.common.status === 'Statut' ? 'Créé le :' : 'Created:'} {formatDate(ip.created_at)}</span>
                          {ip.last_used_at && <span>{t.common.status === 'Statut' ? 'Dernière utilisation :' : 'Last used:'} {formatDate(ip.last_used_at)}</span>}
                        </div>
                      </div>
                      
                      <div className="flex gap-2 ml-4">
                        <button
                          onClick={() => handleToggleIP(ip.id, ip.is_active)}
                          className="px-3 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-900 dark:text-white"
                        >
                          {ip.is_active ? (t.common.status === 'Statut' ? 'Désactiver' : 'Disable') : (t.common.status === 'Statut' ? 'Activer' : 'Enable')}
                        </button>
                        <button
                          onClick={() => handleDeleteIP(ip.id)}
                          className="px-3 py-1 text-sm text-red-600 dark:text-red-400 border border-red-300 dark:border-red-800 rounded hover:bg-red-50 dark:hover:bg-red-900/20"
                        >
                          {t.common.delete}
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Security Logs Tab */}
      {activeTab === 'logs' && (
        <div className="space-y-6">
          <h2 className="text-xl font-semibold">{t.common.status === 'Statut' ? 'Événements de sécurité' : 'Security Events'}</h2>
          
          <div className="bg-white dark:bg-gray-800 shadow rounded-lg overflow-hidden">
            {loading ? (
              <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="p-4">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <div className="h-5 bg-gray-200 dark:bg-gray-700 rounded w-20 animate-pulse"></div>
                          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-32 animate-pulse"></div>
                        </div>
                        <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-full mb-2 animate-pulse"></div>
                        <div className="flex gap-4">
                          <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-32 animate-pulse"></div>
                          <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-24 animate-pulse"></div>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : logs.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-gray-500 dark:text-gray-400">{t.common.status === 'Statut' ? 'Aucun journal de sécurité' : 'No security logs'}</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {logs.map((log) => (
                  <div key={log.id} className="p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <span className={`px-2 py-1 text-xs rounded font-semibold ${getSeverityColor(log.severity)}`}>
                            {log.severity.toUpperCase()}
                          </span>
                          <span className="text-sm text-gray-600 dark:text-gray-400">{log.event_type}</span>
                        </div>
                        <p className="text-sm text-gray-900 dark:text-white mb-2">{log.message}</p>
                        <div className="flex gap-4 text-xs text-gray-500 dark:text-gray-400">
                          <span>{formatDate(log.created_at)}</span>
                          {log.ip_address && <span>IP: {log.ip_address}</span>}
                          {log.endpoint && <span>{t.common.status === 'Statut' ? 'Point de terminaison :' : 'Endpoint:'} {log.endpoint}</span>}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Add Domain Modal */}
      {showDomainModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-4">{t.common.status === 'Statut' ? 'Ajouter un domaine à la liste blanche' : 'Add Domain to Allowlist'}</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  {t.common.status === 'Statut' ? 'Domaine' : 'Domain'} <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={domainForm.domain}
                  onChange={(e) => setDomainForm({ ...domainForm, domain: e.target.value })}
                  placeholder="example.com"
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-indigo-500 focus:border-indigo-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t.common.status === 'Statut' ? 'Entrez sans http:// ou https://' : 'Enter without http:// or https://'}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t.common.status === 'Statut' ? 'Description' : 'Description'}</label>
                <textarea
                  value={domainForm.description}
                  onChange={(e) => setDomainForm({ ...domainForm, description: e.target.value })}
                  placeholder={t.common.status === 'Statut' ? 'Description optionnelle' : 'Optional description'}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-indigo-500 focus:border-indigo-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                />
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowDomainModal(false)}
                className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-900 dark:text-white"
              >
                {t.common.cancel}
              </button>
              <button
                onClick={handleAddDomain}
                className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
              >
                {t.common.status === 'Statut' ? 'Ajouter le domaine' : 'Add Domain'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add IP Modal */}
      {showIPModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-4">{t.common.status === 'Statut' ? 'Ajouter une IP à la liste blanche' : 'Add IP to Allowlist'}</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  {t.common.status === 'Statut' ? 'Adresse IP' : 'IP Address'} <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={ipForm.ip_address}
                  onChange={(e) => setIPForm({ ...ipForm, ip_address: e.target.value })}
                  placeholder="192.168.1.1"
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-indigo-500 focus:border-indigo-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t.common.status === 'Statut' ? 'Plage IP (CIDR)' : 'IP Range (CIDR)'}</label>
                <input
                  type="text"
                  value={ipForm.ip_range}
                  onChange={(e) => setIPForm({ ...ipForm, ip_range: e.target.value })}
                  placeholder="192.168.1.0/24"
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-indigo-500 focus:border-indigo-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t.common.status === 'Statut' ? 'Optionnel : Autoriser toute la plage IP en utilisant la notation CIDR' : 'Optional: Allow entire IP range using CIDR notation'}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t.common.status === 'Statut' ? 'Description' : 'Description'}</label>
                <textarea
                  value={ipForm.description}
                  onChange={(e) => setIPForm({ ...ipForm, description: e.target.value })}
                  placeholder={t.common.status === 'Statut' ? 'Description optionnelle' : 'Optional description'}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-indigo-500 focus:border-indigo-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                />
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowIPModal(false)}
                className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-900 dark:text-white"
              >
                {t.common.cancel}
              </button>
              <button
                onClick={handleAddIP}
                className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
              >
                {t.common.status === 'Statut' ? 'Ajouter l\'IP' : 'Add IP'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

