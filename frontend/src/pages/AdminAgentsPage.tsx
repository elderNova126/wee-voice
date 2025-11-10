import { useEffect, useState } from 'react'
import DashboardLayout from '@/layouts/DashboardLayout'
import { adminAPI } from '@/lib/api'
import toast from 'react-hot-toast'
import {
  MicrophoneIcon,
  GlobeAltIcon,
  CheckCircleIcon,
  XCircleIcon,
  SparklesIcon,
  AdjustmentsHorizontalIcon,
  MagnifyingGlassIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline'
import { Card, CardContent, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'

interface AgentOwner {
  id: number
  full_name: string
  email: string
}

interface AgentMetrics {
  calls_count: number
  minutes_used: number
}

interface AdminAgent {
  id: number
  name: string
  description?: string
  language: string
  voice_id: string
  is_active: boolean
  is_public: boolean
  rag_enabled: boolean
  created_at: string
  owner: AgentOwner
  metrics: AgentMetrics
}

export default function AdminAgentsPage() {
  const [agents, setAgents] = useState<AdminAgent[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filterActive, setFilterActive] = useState<'all' | 'active' | 'inactive'>('all')
  const [filterPublic, setFilterPublic] = useState<'all' | 'public' | 'private'>('all')

  useEffect(() => {
    loadAgents()
  }, [search, filterActive, filterPublic])

  const loadAgents = async () => {
    try {
      setLoading(true)
      const response = await adminAPI.listAgents({
        search: search || undefined,
        is_active: filterActive === 'all' ? undefined : filterActive === 'active',
        is_public: filterPublic === 'all' ? undefined : filterPublic === 'public',
        limit: 200,
      })
      setAgents(response.data)
    } catch (error: any) {
      console.error('Failed to load agents', error)
      toast.error(error.response?.data?.detail || 'Impossible de charger les agents')
    } finally {
      setLoading(false)
    }
  }

  const updateAgentInState = (updatedAgent: AdminAgent) => {
    setAgents((prev) =>
      prev.map((agent) => (agent.id === updatedAgent.id ? updatedAgent : agent))
    )
  }

  const handleToggleActive = async (agent: AdminAgent) => {
    try {
      const response = await adminAPI.updateAgent(agent.id, { is_active: !agent.is_active })
      updateAgentInState(response.data)
      toast.success(`Agent ${response.data.is_active ? 'activé' : 'désactivé'}`)
    } catch (error: any) {
      console.error('Failed to toggle agent active status', error)
      toast.error(error.response?.data?.detail || 'Action impossible')
    }
  }

  const handleTogglePublic = async (agent: AdminAgent) => {
    try {
      const response = await adminAPI.updateAgent(agent.id, { is_public: !agent.is_public })
      updateAgentInState(response.data)
      toast.success(`Agent ${response.data.is_public ? 'rendu public' : 'retiré du public'}`)
    } catch (error: any) {
      console.error('Failed to toggle agent public status', error)
      toast.error(error.response?.data?.detail || 'Action impossible')
    }
  }

  const handleToggleRag = async (agent: AdminAgent) => {
    try {
      const response = await adminAPI.updateAgent(agent.id, { rag_enabled: !agent.rag_enabled })
      updateAgentInState(response.data)
      toast.success(`Knowledge base ${response.data.rag_enabled ? 'activée' : 'désactivée'}`)
    } catch (error: any) {
      console.error('Failed to toggle agent RAG', error)
      toast.error(error.response?.data?.detail || 'Action impossible')
    }
  }

  const resetFilters = () => {
    setSearch('')
    setFilterActive('all')
    setFilterPublic('all')
  }

  const renderLanguage = (language: string) => {
    if (language === 'fr-FR') return 'Français'
    if (language === 'en-US') return 'English'
    return language
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
              Gestion des agents
            </h1>
            <p className="mt-2 text-gray-600 dark:text-gray-400">
              Surveillez et modérez les agents publics et privés de l&apos;ensemble de la plateforme.
            </p>
          </div>
          <Button variant="outline" onClick={loadAgents} icon={<ArrowPathIcon className="w-4 h-4" />}>
            Actualiser
          </Button>
        </div>

        {/* Filters */}
        <Card>
          <CardHeader
            title="Filtres"
            subtitle="Affinez la liste des agents"
            icon={<AdjustmentsHorizontalIcon className="w-6 h-6" />}
          />
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Input
                placeholder="Rechercher par nom, email propriétaire..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                icon={<MagnifyingGlassIcon className="w-5 h-5" />}
              />

              <select
                value={filterActive}
                onChange={(e) => setFilterActive(e.target.value as typeof filterActive)}
                className="px-4 py-2.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              >
                <option value="all">Tous les statuts</option>
                <option value="active">Actifs</option>
                <option value="inactive">Inactifs</option>
              </select>

              <select
                value={filterPublic}
                onChange={(e) => setFilterPublic(e.target.value as typeof filterPublic)}
                className="px-4 py-2.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              >
                <option value="all">Tous les niveaux</option>
                <option value="public">Publics</option>
                <option value="private">Privés</option>
              </select>

              {(search || filterActive !== 'all' || filterPublic !== 'all') && (
                <Button variant="outline" onClick={resetFilters}>
                  Réinitialiser
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Agents table */}
        <Card>
          {loading ? (
            <div className="p-8 text-center">
              <ArrowPathIcon className="w-8 h-8 mx-auto animate-spin text-gray-400" />
              <p className="mt-2 text-gray-600 dark:text-gray-400">Chargement des agents...</p>
            </div>
          ) : agents.length === 0 ? (
            <div className="p-10 text-center space-y-3">
              <MicrophoneIcon className="w-12 h-12 mx-auto text-gray-400" />
              <p className="text-gray-600 dark:text-gray-400">
                Aucun agent correspondant à votre recherche.
              </p>
            </div>
          ) : (
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeader>Agent</TableHeader>
                  <TableHeader>Propriétaire</TableHeader>
                  <TableHeader>Statut</TableHeader>
                  <TableHeader>Langue</TableHeader>
                  <TableHeader>Métriques</TableHeader>
                  <TableHeader className="text-right">Actions</TableHeader>
                </TableRow>
              </TableHead>
              <TableBody>
                {agents.map((agent) => (
                  <TableRow key={agent.id}>
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="font-semibold text-gray-900 dark:text-white">
                          {agent.name}
                        </span>
                        {agent.description && (
                          <span className="text-sm text-gray-500 dark:text-gray-400 line-clamp-1">
                            {agent.description}
                          </span>
                        )}
                        <span className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                          Créé le {new Date(agent.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    </TableCell>

                    <TableCell>
                      <div className="flex flex-col">
                        <span className="font-medium text-gray-900 dark:text-white">
                          {agent.owner.full_name}
                        </span>
                        <span className="text-sm text-gray-500 dark:text-gray-400">
                          {agent.owner.email}
                        </span>
                      </div>
                    </TableCell>

                    <TableCell>
                      <div className="flex flex-col gap-1">
                        <Badge variant={agent.is_active ? 'success' : 'danger'} size="sm">
                          {agent.is_active ? 'Actif' : 'Inactif'}
                        </Badge>
                        <Badge variant={agent.is_public ? 'purple' : 'default'} size="sm">
                          {agent.is_public ? 'Public' : 'Privé'}
                        </Badge>
                        <Badge variant={agent.rag_enabled ? 'info' : 'default'} size="sm" dot={agent.rag_enabled}>
                          <span className="inline-flex items-center gap-1">
                            <SparklesIcon className="w-4 h-4" />
                            {agent.rag_enabled ? 'Knowledge Base active' : 'Knowledge Base off'}
                          </span>
                        </Badge>
                      </div>
                    </TableCell>

                    <TableCell>
                      <div className="flex flex-col gap-1">
                        <Badge variant="info" size="sm" className="w-fit">
                          <GlobeAltIcon className="w-3 h-3" />
                          <span>{renderLanguage(agent.language)}</span>
                        </Badge>
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          Voix: {agent.voice_id}
                        </span>
                      </div>
                    </TableCell>

                    <TableCell>
                      <div className="flex flex-col">
                        <span className="text-sm text-gray-900 dark:text-white font-medium">
                          {agent.metrics.minutes_used.toFixed(1)} min
                        </span>
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          {agent.metrics.calls_count} appels
                        </span>
                      </div>
                    </TableCell>

                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          size="sm"
                          variant={agent.is_active ? 'danger' : 'primary'}
                          onClick={() => handleToggleActive(agent)}
                          icon={agent.is_active ? <XCircleIcon className="w-4 h-4" /> : <CheckCircleIcon className="w-4 h-4" />}
                        >
                          {agent.is_active ? 'Désactiver' : 'Activer'}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleTogglePublic(agent)}
                          icon={agent.is_public ? <XCircleIcon className="w-4 h-4" /> : <CheckCircleIcon className="w-4 h-4" />}
                        >
                          {agent.is_public ? 'Rendre privé' : 'Rendre public'}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleToggleRag(agent)}
                          icon={<SparklesIcon className="w-4 h-4" />}
                        >
                          {agent.rag_enabled ? 'Désactiver KB' : 'Activer KB'}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Card>
      </div>
    </DashboardLayout>
  )
}

