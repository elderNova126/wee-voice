import { ChangeEvent, FormEvent, useCallback, useEffect, useState, useRef } from 'react'
import { PhoneIcon, ClockIcon, CurrencyDollarIcon, FunnelIcon, ExclamationTriangleIcon, TrashIcon, ArrowPathIcon, ChartBarIcon, ChevronLeftIcon, ChevronRightIcon, StarIcon, MagnifyingGlassIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { StarIcon as StarIconSolid } from '@heroicons/react/24/solid'
import DashboardLayout from '@/layouts/DashboardLayout'
import { callsAPI } from '@/lib/api'
import { useAuthStore } from '@/store/authStore'
import toast from 'react-hot-toast'
import { useTranslation } from '@/lib/translations'

interface Call {
  id: number
  agent_id: number
  is_favorite?: boolean
  session_id: string
  status: string
  duration_minutes: number
  cost: number
  started_at: string | null  // Nullable - set when session actually starts
  ended_at: string | null
  summary?: string | null
  sentiment?: string | null
  transcript?: string | null
  callback_requested?: boolean
  callback_reason?: string | null
  action_items?: string[]
  action_tags?: string[]
  summarization_status?: string | null  // "summarized", "not_summarized", or null
  messages?: CallMessage[]  // Messages for the call
}

interface CallMessage {
  role: string
  content: string
  timestamp: string
}

interface CallWithDetails extends Call {
  key_points?: string[]
  messages?: CallMessage[]
}

const partitionFollowUpTags = (tags: string[] = []) => {
  return tags.reduce(
    (acc, tag) => {
      const normalized = tag.toLowerCase()
      if (normalized.includes('request')) {
        acc.actionRequests.push(tag)
      } else {
        acc.others.push(tag)
      }
      return acc
    },
    { actionRequests: [] as string[], others: [] as string[] }
  )
}

const getTagColor = (tag: string) => {
  const normalized = tag.toLowerCase()
  if (normalized.includes('request')) {
    return 'bg-amber-200 text-amber-900 dark:bg-amber-900 dark:text-amber-100 border border-amber-400 dark:border-amber-600'
  }
  if (normalized.includes('email')) {
    return 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-100'
  }
  if (normalized.includes('message')) {
    return 'bg-sky-100 text-sky-800 dark:bg-sky-900 dark:text-sky-100'
  }
  if (normalized.includes('callback')) {
    return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100'
  }
  if (normalized.includes('meeting') || normalized.includes('rdv') || normalized.includes('rendez')) {
    return 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-100'
  }
  if (normalized.includes('quote') || normalized.includes('devis')) {
    return 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-100'
  }
  if (normalized.includes('share document')) {
    return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-100'
  }
  if (normalized.includes('book demo')) {
    return 'bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-100'
  }
  return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
}

export default function CallsPage() {
  const t = useTranslation()
  const [calls, setCalls] = useState<Call[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedCall, setSelectedCall] = useState<Call | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [actionRequiredFilter, setActionRequiredFilter] = useState<boolean | null>(null)
  const [selectedCallIds, setSelectedCallIds] = useState<Set<number>>(new Set())
  const [deleting, setDeleting] = useState(false)
  const [deletingCallId, setDeletingCallId] = useState<number | null>(null)
  const [togglingBulkFavorite, setTogglingBulkFavorite] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const [itemsPerPage, setItemsPerPage] = useState(10)
  const [totalCalls, setTotalCalls] = useState(0)
  const [totalPages, setTotalPages] = useState(0)
  const [activeTab, setActiveTab] = useState<'all' | 'favorites'>('all')
  const [togglingFavorite, setTogglingFavorite] = useState<number | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const wsRef = useRef<WebSocket | null>(null)
  const token = useAuthStore(state => state.token)

  useEffect(() => {
    loadCalls()
  }, [currentPage, itemsPerPage, statusFilter, actionRequiredFilter, activeTab, searchQuery])
  
  useEffect(() => {
    // Connect to WebSocket for real-time updates
    if (token) {
      const wsUrl = `${import.meta.env.VITE_API_URL?.replace('http', 'ws') || 'ws://localhost:8000'}/api/v1/ws/calls/monitor?token=${token}`
      const ws = new WebSocket(wsUrl)
      
      ws.onopen = () => {
        console.log('Connected to call monitor WebSocket')
      }
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'call_update') {
            // Update the call in the list, or add it if it doesn't exist
            setCalls(prevCalls => {
              const existingIndex = prevCalls.findIndex(call => call.id === data.call.id)
              if (existingIndex >= 0) {
                // Update existing call
                const updatedCall = { ...prevCalls[existingIndex], ...data.call }
                
                // If there's a new message, we need to reload the call to get full details
                if (data.call.new_message) {
                  // Reload call details to get updated messages
                  callsAPI.get(data.call.id).then(response => {
                    setCalls(prevCalls => 
                      prevCalls.map(call => 
                        call.id === data.call.id 
                          ? { ...call, ...response.data }
                          : call
                      )
                    )
                  }).catch(err => {
                    console.error('Error reloading call:', err)
                  })
                }
                
                return prevCalls.map(call => 
                  call.id === data.call.id 
                    ? updatedCall
                    : call
                )
              } else {
                // Add new call at the beginning (most recent first)
                return [data.call, ...prevCalls]
              }
            })
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error)
        }
      }
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
      }
      
      ws.onclose = () => {
        console.log('Disconnected from call monitor WebSocket')
        // Attempt to reconnect after 5 seconds
        setTimeout(() => {
          if (token) {
            // Reconnect logic would go here if needed
          }
        }, 5000)
      }
      
      wsRef.current = ws
      
      return () => {
        ws.close()
      }
    }
  }, [token])

  const loadCalls = async () => {
    try {
      setLoading(true)
      const params: any = {
        page: currentPage,
        per_page: itemsPerPage
      }
      
      if (statusFilter !== 'all') {
        params.status = statusFilter
      }
      
      if (actionRequiredFilter !== null) {
        params.action_required = actionRequiredFilter
      }
      
      // Add favorite filter based on active tab
      if (activeTab === 'favorites') {
        params.favorite = true
      }
      
      // Add search query if provided
      if (searchQuery.trim()) {
        params.search = searchQuery.trim()
      }
      
      const response = await callsAPI.list(params)
      const data = response.data
      setCalls(data.items || [])
      setTotalCalls(data.total || 0)
      setTotalPages(data.total_pages || 0)
    } catch (error) {
      console.error('Failed to load calls:', error)
      toast.error('Failed to load calls')
    } finally {
      setLoading(false)
    }
  }


  const handleSelectCall = (callId: number, event: React.MouseEvent) => {
    event.stopPropagation()
    setSelectedCallIds(prev => {
      const newSet = new Set(prev)
      if (newSet.has(callId)) {
        newSet.delete(callId)
      } else {
        newSet.add(callId)
      }
      return newSet
    })
  }

  const handleSelectAll = () => {
    // Select/deselect all calls on current page
    const pageCallIds = paginatedCalls.map(c => c.id)
    const allSelected = pageCallIds.every(id => selectedCallIds.has(id))
    
    if (allSelected) {
      // Deselect all calls on current page
      setSelectedCallIds(prev => {
        const newSet = new Set(prev)
        pageCallIds.forEach(id => newSet.delete(id))
        return newSet
      })
    } else {
      // Select all calls on current page
      setSelectedCallIds(prev => {
        const newSet = new Set(prev)
        pageCallIds.forEach(id => newSet.add(id))
        return newSet
      })
    }
  }

  const handleDeleteCall = async (callId: number, event: React.MouseEvent) => {
    event.stopPropagation()
    if (!confirm('Are you sure you want to delete this call?')) return
    
    try {
      setDeletingCallId(callId)
      setDeleting(true)
      await callsAPI.delete(callId)
      toast.success('Call deleted successfully')
      loadCalls()
      setSelectedCallIds(prev => {
        const newSet = new Set(prev)
        newSet.delete(callId)
        return newSet
      })
    } catch (error: any) {
      console.error('Failed to delete call:', error)
      toast.error(error?.response?.data?.detail || 'Failed to delete call')
    } finally {
      setDeleting(false)
      setDeletingCallId(null)
    }
  }

  const handleBulkDelete = async () => {
    if (selectedCallIds.size === 0) return
    if (!confirm(`Are you sure you want to delete ${selectedCallIds.size} call(s)?`)) return
    
    try {
      setDeleting(true)
      const response = await callsAPI.bulkDelete(Array.from(selectedCallIds))
      toast.success(response.data.message || `Deleted ${response.data.deleted_count} call(s)`)
      loadCalls()
      setSelectedCallIds(new Set())
    } catch (error: any) {
      console.error('Failed to delete calls:', error)
      toast.error(error?.response?.data?.detail || 'Failed to delete calls')
    } finally {
      setDeleting(false)
    }
  }

  const handleToggleFavorite = async (callId: number, event: React.MouseEvent) => {
    event.stopPropagation()
    try {
      setTogglingFavorite(callId)
      const response = await callsAPI.toggleFavorite(callId)
      // Update the call in the list
      setCalls(prevCalls => 
        prevCalls.map(call => 
          call.id === callId ? { ...call, is_favorite: response.data.is_favorite } : call
        )
      )
      toast.success(response.data.message)
    } catch (error: any) {
      console.error('Failed to toggle favorite:', error)
      toast.error(error?.response?.data?.detail || 'Failed to update favorite status')
    } finally {
      setTogglingFavorite(null)
    }
  }

  const handleBulkToggleFavorite = async (isFavorite: boolean) => {
    if (selectedCallIds.size === 0) return
    
    try {
      setTogglingBulkFavorite(true)
      const response = await callsAPI.bulkToggleFavorite(Array.from(selectedCallIds), isFavorite)
      toast.success(response.data.message)
      loadCalls() // Reload to get updated favorite status
      setSelectedCallIds(new Set())
    } catch (error: any) {
      console.error('Failed to update favorites:', error)
      toast.error(error?.response?.data?.detail || 'Failed to update favorites')
    } finally {
      setTogglingBulkFavorite(false)
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString()
  }

  const getSentimentColor = (sentiment: string) => {
    switch (sentiment?.toLowerCase()) {
      case 'positive':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      case 'negative':
        return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'completed':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      case 'failed':
        return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
      case 'in_progress':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
      case 'summarizing':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
    }
  }

  // Use calls directly since they're already paginated from the server
  const paginatedCalls = calls
  
  // Calculate display values
  const startItem = totalCalls > 0 ? (currentPage - 1) * itemsPerPage + 1 : 0
  const endItem = Math.min(currentPage * itemsPerPage, totalCalls)

  // Reset to page 1 when filters, tab, or search changes
  useEffect(() => {
    setCurrentPage(1)
  }, [statusFilter, actionRequiredFilter, activeTab, searchQuery])

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearchQuery(searchInput)
    }, 500) // 500ms debounce
    
    return () => clearTimeout(timer)
  }, [searchInput])

  const handleSearchClear = () => {
    setSearchInput('')
    setSearchQuery('')
  }

  // Reset to page 1 when items per page changes
  useEffect(() => {
    setCurrentPage(1)
  }, [itemsPerPage])

  return (
    <DashboardLayout>
      <div className="mb-8">
        {/* Header Section with Title and Tabs */}
        <div className="mb-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white mb-1">{t.callsPage.callHistory}</h1>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                {t.common.status === 'Statut' ? 'Consultez et analysez tous les appels des agents vocaux' : 'View and analyze all voice agent calls'}
              </p>
            </div>
            
            {/* Stats Card */}
            <div className="bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 border border-blue-200 dark:border-blue-800 rounded-xl p-4 shadow-sm">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-100 dark:bg-blue-900/50 rounded-lg">
                  <ChartBarIcon className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <div className="text-xs font-medium text-blue-600 dark:text-blue-400 uppercase tracking-wide">
                    {t.callsPage.totalCalls}
                  </div>
                  {loading ? (
                    <div className="flex items-center gap-2">
                      <ArrowPathIcon className="h-5 w-5 text-blue-600 dark:text-blue-400 animate-spin" />
                      <span className="text-2xl font-bold text-gray-900 dark:text-white">{t.callsPage.loading}</span>
                    </div>
                  ) : (
                    <div className="text-2xl font-bold text-gray-900 dark:text-white">
                      {totalCalls}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-2 bg-gray-100 dark:bg-gray-800 p-1 rounded-lg border border-gray-200 dark:border-gray-700 w-fit">
            <button
              onClick={() => setActiveTab('all')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                activeTab === 'all'
                  ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
              }`}
            >
              {t.callsPage.allCalls}
            </button>
            <button
              onClick={() => setActiveTab('favorites')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2 ${
                activeTab === 'favorites'
                  ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
              }`}
            >
              <StarIconSolid className={`h-4 w-4 ${activeTab === 'favorites' ? 'text-yellow-500' : ''}`} />
              {t.callsPage.favorites}
            </button>
          </div>
        </div>

        {/* Search Bar */}
        <div className="mb-4">
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <MagnifyingGlassIcon className="h-5 w-5 text-gray-400" />
            </div>
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder={t.callsPage.searchPlaceholder}
              className="w-full pl-10 pr-10 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
            />
            {searchInput && (
              <button
                onClick={handleSearchClear}
                className="absolute inset-y-0 right-0 pr-3 flex items-center"
              >
                <XMarkIcon className="h-5 w-5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300" />
              </button>
            )}
          </div>
        </div>
        
        {/* Filters Section */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4 shadow-sm mb-4">
          <div className="flex flex-col gap-4">
            {/* Filter Header */}
            <div className="flex items-center gap-2 pb-2 border-b border-gray-200 dark:border-gray-700">
              <div className="p-1.5 bg-gray-100 dark:bg-gray-700 rounded-lg">
                <FunnelIcon className="h-4 w-4 text-gray-600 dark:text-gray-400" />
              </div>
              <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">{t.callsPage.filters}</span>
            </div>
            
            {/* Filter Controls */}
            <div className="flex flex-col sm:flex-row gap-3 sm:gap-4">
              {/* Status Filter */}
              <div className="flex-1">
                <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">
                  {t.callsPage.status}
                </label>
                <div className="relative">
                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all appearance-none cursor-pointer hover:border-gray-400 dark:hover:border-gray-500"
                  >
                    <option value="all">{t.callsPage.allStatuses}</option>
                    <option value="initiated">Initiated</option>
                    <option value="in_progress">In Progress</option>
                    <option value="summarizing">Summarizing</option>
                    <option value="completed">Completed</option>
                    <option value="failed">Failed</option>
                    <option value="interrupted">Interrupted</option>
                  </select>
                  <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
                    <svg className="h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </div>
              </div>
              
              {/* Action Required Filter */}
              <div className="flex-1">
                <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">
                  {t.callsPage.actionRequired}
                </label>
                <div className="relative">
                  {actionRequiredFilter === true && (
                    <div className="absolute -top-1 -right-1 z-10">
                      <ExclamationTriangleIcon className="h-4 w-4 text-amber-500 dark:text-amber-400 animate-pulse" />
                    </div>
                  )}
                  <select
                    value={actionRequiredFilter === null ? 'all' : actionRequiredFilter ? 'yes' : 'no'}
                    onChange={(e) => {
                      const value = e.target.value
                      setActionRequiredFilter(value === 'all' ? null : value === 'yes')
                    }}
                    className={`w-full px-3 py-2.5 border-2 rounded-lg text-sm focus:outline-none focus:ring-2 transition-all duration-200 appearance-none cursor-pointer ${
                      actionRequiredFilter === true
                        ? 'border-amber-400 dark:border-amber-600 bg-amber-50 dark:bg-amber-900/30 text-amber-900 dark:text-amber-100 focus:ring-amber-500 font-semibold shadow-sm'
                        : actionRequiredFilter === false
                        ? 'border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-blue-500 hover:border-gray-400 dark:hover:border-gray-500'
                        : 'border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-blue-500 hover:border-gray-400 dark:hover:border-gray-500'
                    }`}
                  >
                    <option value="all">{t.callsPage.allCalls}</option>
                    <option value="yes">{t.callsPage.actionRequired}</option>
                    <option value="no">{t.common.status === 'Statut' ? 'Aucune action requise' : 'No Action Required'}</option>
                  </select>
                  <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
                    <svg className={`h-4 w-4 ${actionRequiredFilter === true ? 'text-amber-500' : 'text-gray-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </div>
                {actionRequiredFilter === true && (
                  <div className="mt-1.5 flex items-center gap-1.5">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold text-amber-900 dark:text-amber-100 bg-amber-200 dark:bg-amber-800">
                      ACTIVE FILTER
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
        
        {/* Bulk Actions */}
        {selectedCallIds.size > 0 && (
          <div className="mt-4 p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <span className="text-sm font-medium text-amber-900 dark:text-amber-100">
              {selectedCallIds.size} {t.common.status === 'Statut' ? 'appel(s) sélectionné(s)' : 'call(s) selected'}
            </span>
            <div className="flex items-center gap-2 flex-wrap">
              {activeTab === 'all' ? (
                <button
                  onClick={() => handleBulkToggleFavorite(true)}
                  disabled={togglingBulkFavorite || deleting}
                  className="px-4 py-2 bg-yellow-500 hover:bg-yellow-600 disabled:bg-gray-400 text-white rounded-md text-sm font-medium transition-colors flex items-center gap-2"
                >
                  {togglingBulkFavorite ? (
                    <ArrowPathIcon className="h-4 w-4 animate-spin" />
                  ) : (
                    <StarIconSolid className="h-4 w-4" />
                  )}
                  {togglingBulkFavorite ? (t.common.status === 'Statut' ? 'Ajout...' : 'Adding...') : t.callsPage.bulkFavorite}
                </button>
              ) : (
                <button
                  onClick={() => handleBulkToggleFavorite(false)}
                  disabled={togglingBulkFavorite || deleting}
                  className="px-4 py-2 bg-gray-600 hover:bg-gray-700 disabled:bg-gray-400 text-white rounded-md text-sm font-medium transition-colors flex items-center gap-2"
                >
                  {togglingBulkFavorite ? (
                    <ArrowPathIcon className="h-4 w-4 animate-spin" />
                  ) : (
                    <StarIcon className="h-4 w-4" />
                  )}
                  {togglingBulkFavorite ? (t.common.status === 'Statut' ? 'Retrait...' : 'Removing...') : t.callsPage.bulkUnfavorite}
                </button>
              )}
              <button
                onClick={handleBulkDelete}
                disabled={deleting || togglingBulkFavorite}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-gray-400 text-white rounded-md text-sm font-medium transition-colors flex items-center gap-2"
              >
                {deleting ? (
                  <ArrowPathIcon className="h-4 w-4 animate-spin" />
                ) : (
                  <TrashIcon className="h-4 w-4" />
                )}
                {deleting ? (t.common.status === 'Statut' ? 'Suppression...' : 'Deleting...') : t.callsPage.bulkDelete}
              </button>
            </div>
          </div>
        )}
      </div>
      
      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="card animate-pulse">
              <div className="h-20 bg-gray-200 dark:bg-gray-700 rounded"></div>
            </div>
          ))}
        </div>
      ) : calls.length === 0 ? (
        <div className="card text-center py-12">
          <PhoneIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-semibold text-gray-900 dark:text-white">{t.callsPage.noCalls}</h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {t.common.status === 'Statut' ? 'Commencez à tester vos agents pour voir l\'historique des appels ici.' : 'Start testing your agents to see call history here.'}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Pagination Header - Info and Per Page */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4">
            <div className="flex items-center gap-4 flex-wrap">
              <div className="text-sm text-gray-600 dark:text-gray-400">
                {t.callsPage.showing} <span className="font-semibold text-gray-900 dark:text-white">{startItem}</span> {t.common.status === 'Statut' ? 'à' : 'to'}{' '}
                <span className="font-semibold text-gray-900 dark:text-white">{endItem}</span> {t.callsPage.of}{' '}
                <span className="font-semibold text-gray-900 dark:text-white">{totalCalls}</span> {t.common.status === 'Statut' ? 'appels' : 'calls'}
                {searchQuery && (
                  <span className="ml-2 text-blue-600 dark:text-blue-400">
                    ({t.common.search}: "{searchQuery}")
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <label className="text-sm text-gray-600 dark:text-gray-400 whitespace-nowrap">{t.common.status === 'Statut' ? 'Par page :' : 'Per page:'}</label>
                <select
                  value={itemsPerPage}
                  onChange={(e) => setItemsPerPage(Number(e.target.value))}
                  className="px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent appearance-none cursor-pointer"
                >
                  <option value={5}>5</option>
                  <option value={10}>10</option>
                  <option value={20}>20</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
              </div>
            </div>
            
            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                  disabled={currentPage === 1}
                  className="p-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  title="Previous page"
                >
                  <ChevronLeftIcon className="h-5 w-5" />
                </button>
                
                <div className="flex items-center gap-1">
                  {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                    let pageNum: number
                    if (totalPages <= 5) {
                      pageNum = i + 1
                    } else if (currentPage <= 3) {
                      pageNum = i + 1
                    } else if (currentPage >= totalPages - 2) {
                      pageNum = totalPages - 4 + i
                    } else {
                      pageNum = currentPage - 2 + i
                    }
                    
                    return (
                      <button
                        key={pageNum}
                        onClick={() => setCurrentPage(pageNum)}
                        className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                          currentPage === pageNum
                            ? 'bg-blue-600 text-white'
                            : 'bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-600'
                        }`}
                      >
                        {pageNum}
                      </button>
                    )
                  })}
                </div>
                
                <button
                  onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                  disabled={currentPage === totalPages}
                  className="p-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  title="Next page"
                >
                  <ChevronRightIcon className="h-5 w-5" />
                </button>
              </div>
            )}
          </div>

          {/* Select All Checkbox */}
          <div className="flex items-center gap-2 mb-2 px-2">
            <input
              type="checkbox"
              checked={paginatedCalls.length > 0 && paginatedCalls.every(c => selectedCallIds.has(c.id))}
              onChange={handleSelectAll}
              className="w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
            />
            <label className="text-sm text-gray-700 dark:text-gray-300">{t.common.status === 'Statut' ? 'Tout sélectionner (Page actuelle)' : 'Select All (Current Page)'}</label>
          </div>
          
          {paginatedCalls
            .map((call) => {
            const { actionRequests, others } = partitionFollowUpTags(call.action_tags ?? [])
            return (
              <div
                key={call.id}
                className={`card hover:shadow-lg transition-shadow cursor-pointer ${selectedCallIds.has(call.id) ? 'ring-2 ring-indigo-500 bg-indigo-50 dark:bg-indigo-900/20' : ''}`}
                onClick={() => setSelectedCall(call)}
              >
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                  <div className="flex items-start space-x-3 sm:space-x-4 flex-1 min-w-0">
                    {/* Checkbox */}
                    <input
                      type="checkbox"
                      checked={selectedCallIds.has(call.id)}
                      onChange={(e) => handleSelectCall(call.id, e as any)}
                      onClick={(e) => e.stopPropagation()}
                      className="mt-1 w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500 flex-shrink-0"
                    />
                    <div className="p-2 sm:p-3 bg-blue-100 dark:bg-blue-900 rounded-lg flex-shrink-0">
                      <PhoneIcon className="h-5 w-5 sm:h-6 sm:w-6 text-blue-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <h3 className="text-base sm:text-lg font-semibold text-gray-900 dark:text-white">
                          Call #{call.id}
                        </h3>
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${getStatusColor(call.status)}`}>
                          {call.status}
                        </span>
                        {call.sentiment && (
                          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${getSentimentColor(call.sentiment)}`}>
                            {call.sentiment}
                          </span>
                        )}
                        {actionRequests.length > 0 && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200 uppercase tracking-wide">
                            {t.callsPage.actionRequired}
                          </span>
                        )}
                        {call.summarization_status && (
                          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                            call.summarization_status === 'summarized'
                              ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                              : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                          }`}>
                            {call.summarization_status === 'summarized' ? 'Summarized' : 'No Summarized'}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
                        {call.started_at ? formatDate(call.started_at) : 'Initializing...'}
                      </p>
                      {call.summary && (
                        <p className="text-sm text-gray-600 dark:text-gray-300 line-clamp-2">
                          {call.summary}
                        </p>
                      )}
                      {actionRequests.length > 0 && (
                        <div className="flex flex-wrap gap-2 mt-3">
                          {actionRequests.map((tag, index) => (
                            <span
                              key={`request-${tag}-${index}`}
                              className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${getTagColor(tag)}`}
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                      {others.length > 0 && (
                        <div className={`flex flex-wrap gap-2 ${actionRequests.length > 0 ? 'mt-2' : 'mt-3'}`}>
                          {others.map((tag, index) => (
                            <span
                              key={`other-${tag}-${index}`}
                              className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${getTagColor(tag)}`}
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 sm:gap-3 flex-shrink-0">
                    <div className="text-right">
                      <div className="flex items-center text-xs sm:text-sm text-gray-500 dark:text-gray-400">
                        <ClockIcon className="h-3 w-3 sm:h-4 sm:w-4 mr-1" />
                        <span className="whitespace-nowrap">{Math.max(0, call.duration_minutes || 0).toFixed(1)} min</span>
                      </div>
                      <div className="flex items-center text-xs sm:text-sm text-gray-500 dark:text-gray-400 mt-1">
                        <CurrencyDollarIcon className="h-3 w-3 sm:h-4 sm:w-4 mr-1" />
                        <span className="whitespace-nowrap">${Math.max(0, call.cost || 0).toFixed(2)}</span>
                      </div>
                    </div>
                    <button
                      onClick={(e) => handleToggleFavorite(call.id, e)}
                      disabled={togglingFavorite === call.id}
                      className={`p-2 rounded-md transition-colors disabled:opacity-50 flex-shrink-0 ${
                        call.is_favorite
                          ? 'text-yellow-500 hover:text-yellow-600 hover:bg-yellow-50 dark:hover:bg-yellow-900/20'
                          : 'text-gray-400 hover:text-yellow-500 hover:bg-gray-50 dark:hover:bg-gray-700'
                      }`}
                      title={call.is_favorite ? t.callsPage.unfavorite : t.callsPage.favorite}
                    >
                      {togglingFavorite === call.id ? (
                        <ArrowPathIcon className="h-5 w-5 animate-spin" />
                      ) : call.is_favorite ? (
                        <StarIconSolid className="h-5 w-5" />
                      ) : (
                        <StarIcon className="h-5 w-5" />
                      )}
                    </button>
                    <button
                      onClick={(e) => handleDeleteCall(call.id, e)}
                      disabled={deleting && deletingCallId === call.id}
                      className="p-2 text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md transition-colors disabled:opacity-50 flex-shrink-0"
                      title={deleting && deletingCallId === call.id ? (t.common.status === 'Statut' ? 'Suppression...' : 'Deleting...') : t.common.delete}
                    >
                      {deleting && deletingCallId === call.id ? (
                        <ArrowPathIcon className="h-5 w-5 animate-spin" />
                      ) : (
                        <TrashIcon className="h-5 w-5" />
                      )}
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
          
          {/* Pagination Footer */}
          {totalPages > 1 && (
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4 mt-6 pt-4 border-t border-gray-200 dark:border-gray-700">
              <div className="text-sm text-gray-600 dark:text-gray-400">
                {t.callsPage.page} <span className="font-semibold text-gray-900 dark:text-white">{currentPage}</span> {t.callsPage.of}{' '}
                <span className="font-semibold text-gray-900 dark:text-white">{totalPages}</span>
              </div>
              
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setCurrentPage(1)}
                  disabled={currentPage === 1}
                  className="px-3 py-1.5 text-sm font-medium border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {t.common.status === 'Statut' ? 'Premier' : 'First'}
                </button>
                <button
                  onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                  disabled={currentPage === 1}
                  className="px-3 py-1.5 text-sm font-medium border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-1"
                >
                  <ChevronLeftIcon className="h-4 w-4" />
                  {t.common.previous}
                </button>
                <button
                  onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                  disabled={currentPage === totalPages}
                  className="px-3 py-1.5 text-sm font-medium border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-1"
                >
                  {t.common.next}
                  <ChevronRightIcon className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setCurrentPage(totalPages)}
                  disabled={currentPage === totalPages}
                  className="px-3 py-1.5 text-sm font-medium border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {t.common.status === 'Statut' ? 'Dernier' : 'Last'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Call Details Modal */}
      {selectedCall && (
        <CallDetailsModal
          call={selectedCall}
          onClose={() => setSelectedCall(null)}
        />
      )}
    </DashboardLayout>
  )
}

// Call Details Modal
interface CallDetailsModalProps {
  call: Call
  onClose: () => void
}

function CallDetailsModal({ call, onClose }: CallDetailsModalProps) {
  const t = useTranslation()
  const [transcript, setTranscript] = useState<any>(null)
  const [loadingTranscript, setLoadingTranscript] = useState(true)
  const [callDetails, setCallDetails] = useState<CallWithDetails | null>(null)
  const [loadingDetails, setLoadingDetails] = useState(true)
  const [generatingSummary, setGeneratingSummary] = useState(false)
  const [showEmailComposer, setShowEmailComposer] = useState(false)
  const [sendingEmail, setSendingEmail] = useState(false)
  const [emailForm, setEmailForm] = useState({
    to_email: '',
    subject: `${t.common.status === 'Statut' ? 'Suivi pour l\'appel' : 'Follow-up for call'} #${call.id}`,
    body: ''
  })
  const token = useAuthStore(state => state.token)
  const wsRef = useRef<WebSocket | null>(null)

  const loadCallDetails = useCallback(async () => {
    setLoadingDetails(true)
    try {
      const response = await callsAPI.get(call.id)
      setCallDetails(response.data)
    } catch (error) {
      console.error('Failed to load call details:', error)
      toast.error(t.common.status === 'Statut' ? 'Échec du chargement des détails de l\'appel' : 'Failed to load call details')
    } finally {
      setLoadingDetails(false)
    }
  }, [call.id, t])

  const loadTranscript = useCallback(async () => {
    setLoadingTranscript(true)
    try {
      const response = await callsAPI.getTranscript(call.id)
      const { transcript: rawTranscript, transcript_json: structuredTranscript } = response.data ?? {}
      setTranscript(structuredTranscript ?? rawTranscript ?? null)
    } catch (error: any) {
      const status = error?.response?.status
      if (status === 404) {
        // No transcript stored for this call; fall back to any cached value
        setTranscript(call.transcript ?? null)
      } else {
        console.error('Failed to load transcript:', error)
        toast.error(t.common.status === 'Statut' ? 'Échec du chargement de la transcription' : 'Failed to load transcript')
      }
    } finally {
      setLoadingTranscript(false)
    }
  }, [call.id, call.transcript, t])

  useEffect(() => {
    loadCallDetails()
    loadTranscript()
    
    // Connect to WebSocket for real-time message updates
    if (token) {
      const wsUrl = `${import.meta.env.VITE_API_URL?.replace('http', 'ws') || 'ws://localhost:8000'}/api/v1/ws/calls/monitor?token=${token}`
      const ws = new WebSocket(wsUrl)
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'call_update' && data.call.id === call.id) {
            // If there's a new message, reload call details
            if (data.call.new_message) {
              loadCallDetails()
            } else {
              // Update call details with other updates
              setCallDetails(prev => prev ? { ...prev, ...data.call } : prev)
            }
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error)
        }
      }
      
      wsRef.current = ws
      
      return () => {
        ws.close()
      }
    }
  }, [loadCallDetails, loadTranscript, call.id, token])

  const handleGenerateSummary = async () => {
    setGeneratingSummary(true)
    try {
      await callsAPI.generateSummary(call.id)
      toast.success(t.common.status === 'Statut' ? 'Résumé régénéré' : 'Summary regenerated')
      await Promise.all([loadCallDetails(), loadTranscript()])
    } catch (error) {
      console.error('Failed to regenerate summary:', error)
      toast.error(t.common.status === 'Statut' ? 'Erreur lors de la régénération du résumé' : 'Error regenerating summary')
    } finally {
      setGeneratingSummary(false)
    }
  }

  const displayCall = callDetails ?? call
  const { actionRequests: modalActionRequests, others: modalOtherTags } = partitionFollowUpTags(displayCall.action_tags ?? [])
  const transcriptSource: any = transcript ?? displayCall.transcript
  const transcriptAvailable = Boolean(transcriptSource)
  const hasEmailRequest = modalActionRequests.some((tag) => tag.toLowerCase().includes('email'))

  useEffect(() => {
    setEmailForm((prev) => ({
      ...prev,
      subject: `${t.common.status === 'Statut' ? 'Suivi pour l\'appel' : 'Follow-up for call'} #${call.id}`
    }))
  }, [call.id, t])

  const handleEmailFieldChange = (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = event.target
    setEmailForm((prev) => ({
      ...prev,
      [name]: value
    }))
  }

  const handleSendEmail = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!emailForm.to_email.trim()) {
      toast.error(t.common.status === 'Statut' ? 'L\'email du destinataire est requis' : 'Recipient email is required')
      return
    }
    if (!emailForm.subject.trim()) {
      toast.error(t.common.status === 'Statut' ? 'Le sujet est requis' : 'Subject is required')
      return
    }
    if (!emailForm.body.trim()) {
      toast.error(t.common.status === 'Statut' ? 'Le corps de l\'email ne peut pas être vide' : 'Email body cannot be empty')
      return
    }

    try {
      setSendingEmail(true)
      await callsAPI.sendEmail(displayCall.id, {
        to_email: emailForm.to_email.trim(),
        subject: emailForm.subject.trim(),
        body: emailForm.body.trim(),
      })
      toast.success(t.callsPage.emailSent)
      setShowEmailComposer(false)
      setEmailForm({
        to_email: '',
        subject: `${t.common.status === 'Statut' ? 'Suivi pour l\'appel' : 'Follow-up for call'} #${call.id}`,
        body: ''
      })
      await loadCallDetails()
    } catch (error: any) {
      const message = error?.response?.data?.detail || t.callsPage.emailError
      toast.error(message)
      console.error('Failed to send follow-up email:', error)
    } finally {
      setSendingEmail(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={onClose} />

        <div className="relative bg-white dark:bg-gray-800 rounded-lg max-w-3xl w-full p-6 shadow-xl max-h-[90vh] overflow-y-auto">
          <div className="mb-6">
            <h3 className="text-2xl font-bold text-gray-900 dark:text-white">
              {t.callsPage.callDetails}
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              {t.callsPage.sessionId}: {displayCall.session_id}
            </p>
            {transcriptAvailable && (
              <button
                onClick={handleGenerateSummary}
                disabled={generatingSummary || loadingDetails}
                className="btn-primary mt-4 flex items-center"
              >
                <ClockIcon className="h-4 w-4 mr-2" />
                {generatingSummary
                  ? t.callsPage.regenerating
                  : displayCall.summary
                    ? t.callsPage.regenerateSummary
                    : t.callsPage.generateSummary}
              </button>
            )}
          </div>

          <div className="space-y-6">
            {/* Metadata */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">{t.callsPage.status}</p>
                <p className="text-lg font-medium text-gray-900 dark:text-white capitalize">
                  {displayCall.status}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">{t.callsPage.duration}</p>
                <p className="text-lg font-medium text-gray-900 dark:text-white">
                  {Math.max(0, displayCall.duration_minutes || 0).toFixed(1)} {t.callsPage.minutes}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">{t.callsPage.cost}</p>
                <p className="text-lg font-medium text-gray-900 dark:text-white">
                  ${Math.max(0, displayCall.cost || 0).toFixed(2)}
                </p>
              </div>
              {displayCall.sentiment && (
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">{t.callsPage.sentiment}</p>
                  <p className="text-lg font-medium text-gray-900 dark:text-white capitalize">
                    {displayCall.sentiment}
                  </p>
                </div>
              )}
            </div>

            {/* Follow-up tags */}
            {displayCall.action_tags && displayCall.action_tags.length > 0 && (
              <div>
                <h4 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                  {t.callsPage.followUpActions}
                </h4>
                {modalActionRequests.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-2">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200 uppercase tracking-wide">
                      {t.callsPage.actionRequired}
                    </span>
                    {modalActionRequests.map((tag, index) => (
                      <span
                        key={`modal-request-tag-${tag}-${index}`}
                        className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${getTagColor(tag)}`}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
                {modalOtherTags.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {modalOtherTags.map((tag, index) => (
                      <span
                        key={`modal-tag-${tag}-${index}`}
                        className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${getTagColor(tag)}`}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {hasEmailRequest && (
              <div className="rounded-lg border border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950/40 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h5 className="text-sm font-semibold text-amber-900 dark:text-amber-200">
                      {t.callsPage.sendEmail}
                    </h5>
                    <p className="text-xs text-amber-700 dark:text-amber-300">
                      {t.common.status === 'Statut' ? 'Complétez la demande d\'action en envoyant un email directement au client.' : 'Complete the action request by emailing the customer directly.'}
                    </p>
                  </div>
                  <button
                    onClick={() => setShowEmailComposer((prev) => !prev)}
                    className="btn-secondary btn-xs"
                  >
                    {showEmailComposer ? t.common.cancel : t.callsPage.compose}
                  </button>
                </div>

                {showEmailComposer && (
                  <form onSubmit={handleSendEmail} className="space-y-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                        {t.callsPage.to}
                      </label>
                      <input
                        type="email"
                        name="to_email"
                        value={emailForm.to_email}
                        onChange={handleEmailFieldChange}
                        placeholder="customer@example.com"
                        className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                        {t.callsPage.subject}
                      </label>
                      <input
                        type="text"
                        name="subject"
                        value={emailForm.subject}
                        onChange={handleEmailFieldChange}
                        className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                        {t.callsPage.message}
                      </label>
                      <textarea
                        name="body"
                        rows={6}
                        value={emailForm.body}
                        onChange={handleEmailFieldChange}
                        className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                        placeholder={t.common.status === 'Statut' ? 'Rédigez votre email de suivi...' : 'Draft your follow-up email...'}
                        required
                      />
                    </div>
                    <div className="flex items-center justify-end gap-2">
                      <button
                        type="button"
                        className="btn-secondary btn-sm"
                        onClick={() => setShowEmailComposer(false)}
                        disabled={sendingEmail}
                      >
                        {t.common.cancel}
                      </button>
                      <button
                        type="submit"
                        className="btn-primary btn-sm"
                        disabled={sendingEmail}
                      >
                        {sendingEmail ? t.callsPage.sending : t.callsPage.sendEmail}
                      </button>
                    </div>
                  </form>
                )}
              </div>
            )}

            {/* Action items */}
            {displayCall.action_items && displayCall.action_items.length > 0 && (
              <div>
                <h4 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                  {t.callsPage.actionItems}
                </h4>
                <ul className="list-disc list-inside space-y-1 text-gray-700 dark:text-gray-300">
                  {displayCall.action_items.map((item, index) => (
                    <li key={`modal-action-${index}`}>{item}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Summary */}
            {displayCall.summary && (
              <div>
                <h4 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                  {t.callsPage.summary}
                </h4>
                <p className="text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-900 p-4 rounded-lg">
                  {displayCall.summary}
                </p>
              </div>
            )}

            {/* Messages - Real-time conversation */}
            {displayCall.messages && displayCall.messages.length > 0 && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-lg font-semibold text-gray-900 dark:text-white">
                    {t.callsPage.messages} {displayCall.status === 'in_progress' || displayCall.status === 'summarizing' ? (
                      <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                        {t.callsPage.live}
                      </span>
                    ) : null}
                  </h4>
                </div>
                <div className="bg-gray-50 dark:bg-gray-900 p-4 rounded-lg space-y-3" style={{ maxHeight: '400px', overflowY: 'auto' }}>
                  {displayCall.messages.map((message: any, index: number) => (
                    <div
                      key={index}
                      className={`p-3 rounded-lg ${
                        message.role === 'user'
                          ? 'bg-blue-50 dark:bg-blue-900/30 ml-8'
                          : message.role === 'system'
                          ? 'bg-gray-100 dark:bg-gray-800 mr-8'
                          : 'bg-gray-50 dark:bg-gray-800 mr-8'
                      }`}
                    >
                      <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                        {message.role === 'user' ? t.callsPage.visitor : message.role === 'system' ? t.callsPage.system : t.callsPage.agent} • {message.timestamp ? new Date(message.timestamp).toLocaleTimeString() : ''}
                      </div>
                      <div className="text-sm text-gray-900 dark:text-white whitespace-pre-wrap break-words">
                        {message.content}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

          </div>

          <div className="mt-6 flex justify-end">
            <button onClick={onClose} className="btn-secondary">
              {t.callsPage.close}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
