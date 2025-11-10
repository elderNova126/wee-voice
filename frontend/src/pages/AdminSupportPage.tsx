import { useEffect, useState } from 'react'
import DashboardLayout from '@/layouts/DashboardLayout'
import { adminAPI } from '@/lib/api'
import toast from 'react-hot-toast'
import {
  LifebuoyIcon,
  ChatBubbleLeftRightIcon,
  ArrowPathIcon,
  MagnifyingGlassIcon,
  PaperAirplaneIcon,
} from '@heroicons/react/24/outline'
import { Card, CardContent, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Input } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'

interface AdminSupportTicket {
  id: number
  ticket_number: string
  subject: string
  name: string
  email: string
  status: string
  priority: string
  category: string
  created_at: string
  updated_at: string
  responses_count: number
  last_response_at?: string | null
}

const STATUS_OPTIONS = [
  { value: 'open', label: 'Ouvert' },
  { value: 'in_progress', label: 'En cours' },
  { value: 'resolved', label: 'Résolu' },
  { value: 'closed', label: 'Fermé' },
]

const PRIORITY_OPTIONS = [
  { value: 'low', label: 'Faible' },
  { value: 'medium', label: 'Moyenne' },
  { value: 'high', label: 'Haute' },
  { value: 'urgent', label: 'Urgente' },
]

export default function AdminSupportPage() {
  const [tickets, setTickets] = useState<AdminSupportTicket[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [priorityFilter, setPriorityFilter] = useState('all')
  const [updatingTicketId, setUpdatingTicketId] = useState<number | null>(null)

  useEffect(() => {
    loadTickets()
  }, [search, statusFilter, priorityFilter])

  const loadTickets = async () => {
    try {
      setLoading(true)
      const response = await adminAPI.listSupportTickets({
        search: search || undefined,
        status: statusFilter === 'all' ? undefined : statusFilter,
        priority: priorityFilter === 'all' ? undefined : priorityFilter,
        limit: 200,
      })
      setTickets(response.data)
    } catch (error: any) {
      console.error('Failed to load support tickets', error)
      toast.error(error.response?.data?.detail || 'Impossible de charger les tickets')
    } finally {
      setLoading(false)
    }
  }

  const updateTicketInState = (updated: AdminSupportTicket) => {
    setTickets((prev) => prev.map((ticket) => (ticket.id === updated.id ? updated : ticket)))
  }

  const handleStatusChange = async (ticket: AdminSupportTicket, status: string) => {
    try {
      setUpdatingTicketId(ticket.id)
      const response = await adminAPI.updateSupportTicket(ticket.id, { status })
      updateTicketInState(response.data)
      toast.success('Statut mis à jour')
    } catch (error: any) {
      console.error('Failed to update ticket status', error)
      toast.error(error.response?.data?.detail || 'Impossible de mettre à jour le statut')
    } finally {
      setUpdatingTicketId(null)
    }
  }

  const handlePriorityChange = async (ticket: AdminSupportTicket, priority: string) => {
    try {
      setUpdatingTicketId(ticket.id)
      const response = await adminAPI.updateSupportTicket(ticket.id, { priority })
      updateTicketInState(response.data)
      toast.success('Priorité mise à jour')
    } catch (error: any) {
      console.error('Failed to update ticket priority', error)
      toast.error(error.response?.data?.detail || 'Impossible de mettre à jour la priorité')
    } finally {
      setUpdatingTicketId(null)
    }
  }

  const handleAddResponse = async (ticket: AdminSupportTicket) => {
    const message = window.prompt(`Ajouter une réponse au ticket #${ticket.ticket_number}`)
    if (!message || !message.trim()) {
      return
    }

    try {
      setUpdatingTicketId(ticket.id)
      const response = await adminAPI.updateSupportTicket(ticket.id, { response_message: message.trim() })
      updateTicketInState(response.data)
      toast.success('Réponse envoyée')
    } catch (error: any) {
      console.error('Failed to add response', error)
      toast.error(error.response?.data?.detail || 'Impossible d\'ajouter une réponse')
    } finally {
      setUpdatingTicketId(null)
    }
  }

  const resetFilters = () => {
    setSearch('')
    setStatusFilter('all')
    setPriorityFilter('all')
  }

  const formatDateTime = (isoDate: string) => {
    const date = new Date(isoDate)
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  const statusVariant = (status: string) => {
    switch (status) {
      case 'open':
        return 'warning'
      case 'in_progress':
        return 'info'
      case 'resolved':
        return 'success'
      case 'closed':
        return 'default'
      default:
        return 'default'
    }
  }

  const priorityVariant = (priority: string) => {
    switch (priority) {
      case 'urgent':
        return 'danger'
      case 'high':
        return 'warning'
      case 'medium':
        return 'info'
      default:
        return 'default'
    }
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
              Support & Tickets
            </h1>
            <p className="mt-2 text-gray-600 dark:text-gray-400">
              Répondez rapidement aux demandes et assurez un suivi de qualité.
            </p>
          </div>
          <Button variant="outline" onClick={loadTickets} icon={<ArrowPathIcon className="w-4 h-4" />}>
            Actualiser
          </Button>
        </div>

        {/* Filters */}
        <Card>
          <CardHeader
            title="Filtres"
            subtitle="Recherchez et filtrez les tickets support"
            icon={<LifebuoyIcon className="w-6 h-6" />}
          />
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Input
                placeholder="Rechercher par sujet, email, numéro..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                icon={<MagnifyingGlassIcon className="w-5 h-5" />}
              />

              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-4 py-2.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              >
                <option value="all">Tous les statuts</option>
                {STATUS_OPTIONS.map((status) => (
                  <option key={status.value} value={status.value}>
                    {status.label}
                  </option>
                ))}
              </select>

              <select
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value)}
                className="px-4 py-2.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              >
                <option value="all">Toutes les priorités</option>
                {PRIORITY_OPTIONS.map((priority) => (
                  <option key={priority.value} value={priority.value}>
                    {priority.label}
                  </option>
                ))}
              </select>

              {(search || statusFilter !== 'all' || priorityFilter !== 'all') && (
                <Button variant="outline" onClick={resetFilters}>
                  Réinitialiser
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Tickets table */}
        <Card>
          {loading ? (
            <div className="p-8 text-center">
              <ArrowPathIcon className="w-8 h-8 mx-auto animate-spin text-gray-400" />
              <p className="mt-2 text-gray-600 dark:text-gray-400">Chargement des tickets...</p>
            </div>
          ) : tickets.length === 0 ? (
            <div className="p-10 text-center space-y-3">
              <ChatBubbleLeftRightIcon className="w-12 h-12 mx-auto text-gray-400" />
              <p className="text-gray-600 dark:text-gray-400">
                Aucun ticket ne correspond à votre filtre.
              </p>
            </div>
          ) : (
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeader>Ticket</TableHeader>
                  <TableHeader>Contact</TableHeader>
                  <TableHeader>Statut</TableHeader>
                  <TableHeader>Priorité</TableHeader>
                  <TableHeader>Activité</TableHeader>
                  <TableHeader className="text-right">Actions</TableHeader>
                </TableRow>
              </TableHead>
              <TableBody>
                {tickets.map((ticket) => (
                  <TableRow key={ticket.id}>
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="font-semibold text-gray-900 dark:text-white">
                          {ticket.subject}
                        </span>
                        <span className="text-sm text-gray-500 dark:text-gray-400">
                          #{ticket.ticket_number} • Catégorie : {ticket.category.replace('_', ' ')}
                        </span>
                        <span className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                          Créé le {formatDateTime(ticket.created_at)}
                        </span>
                      </div>
                    </TableCell>

                    <TableCell>
                      <div className="flex flex-col">
                        <span className="font-medium text-gray-900 dark:text-white">
                          {ticket.name}
                        </span>
                        <span className="text-sm text-gray-500 dark:text-gray-400">
                          {ticket.email}
                        </span>
                      </div>
                    </TableCell>

                    <TableCell>
                      <select
                        value={ticket.status}
                        onChange={(e) => handleStatusChange(ticket, e.target.value)}
                        disabled={updatingTicketId === ticket.id}
                        className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                      >
                        {STATUS_OPTIONS.map((status) => (
                          <option key={status.value} value={status.value}>
                            {status.label}
                          </option>
                        ))}
                      </select>
                      <Badge variant={statusVariant(ticket.status)} size="sm" className="mt-2">
                        {ticket.status.replace('_', ' ')}
                      </Badge>
                    </TableCell>

                    <TableCell>
                      <select
                        value={ticket.priority}
                        onChange={(e) => handlePriorityChange(ticket, e.target.value)}
                        disabled={updatingTicketId === ticket.id}
                        className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                      >
                        {PRIORITY_OPTIONS.map((priority) => (
                          <option key={priority.value} value={priority.value}>
                            {priority.label}
                          </option>
                        ))}
                      </select>
                      <Badge variant={priorityVariant(ticket.priority)} size="sm" className="mt-2">
                        {ticket.priority}
                      </Badge>
                    </TableCell>

                    <TableCell>
                      <div className="flex flex-col">
                        <span className="text-sm text-gray-900 dark:text-white font-medium">
                          {ticket.responses_count} réponses
                        </span>
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          {ticket.last_response_at ? `Dernière réponse: ${formatDateTime(ticket.last_response_at)}` : 'Aucune réponse'}
                        </span>
                      </div>
                    </TableCell>

                    <TableCell className="text-right">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleAddResponse(ticket)}
                        icon={<PaperAirplaneIcon className="w-4 h-4" />}
                        disabled={updatingTicketId === ticket.id}
                      >
                        Répondre
                      </Button>
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

