import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { 
  ArrowLeftIcon, 
  DocumentTextIcon, 
  CloudArrowUpIcon,
  TrashIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ClockIcon
} from '@heroicons/react/24/outline'
import { api } from '../lib/api'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'

interface Document {
  id: number
  agent_id: number
  filename: string
  original_filename: string
  file_size?: number
  status: 'pending' | 'processing' | 'completed' | 'failed'
  error_message?: string
  total_pages?: number
  total_chunks: number
  source_type: 'pdf' | 'website' | 'text'
  source_url?: string
  created_at: string
  processed_at?: string
}

interface Agent {
  id: number
  name: string
  rag_enabled: boolean
}

export default function AgentDocumentsPage() {
  const { agentId } = useParams<{ agentId: string }>()
  const navigate = useNavigate()
  
  const [agent, setAgent] = useState<Agent | null>(null)
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<string>('')
  const [error, setError] = useState<string>('')
  const [websiteUrl, setWebsiteUrl] = useState('')
  const [scrapingWebsite, setScrapingWebsite] = useState(false)

  useEffect(() => {
    loadData()
  }, [agentId])

  const loadData = async () => {
    try {
      setLoading(true)
      setError('')
      
      // Load agent details
      const agentResponse = await api.get(`/agents/${agentId}`)
      setAgent(agentResponse.data)
      
      // Load documents
      const docsResponse = await api.get(`/agents/${agentId}/documents`)
      setDocuments(docsResponse.data)
      
    } catch (err: any) {
      console.error('Error loading data:', err)
      setError(err.response?.data?.detail || 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    // Validate file type
    if (!file.name.endsWith('.pdf')) {
      setError('Only PDF files are supported')
      return
    }

    // Validate file size (10MB max)
    if (file.size > 10 * 1024 * 1024) {
      setError('File size must be less than 10MB')
      return
    }

    try {
      setUploading(true)
      setError('')
      setUploadProgress('Uploading file...')

      const formData = new FormData()
      formData.append('file', file)

      const response = await api.post(`/agents/${agentId}/documents`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })

      setUploadProgress('Processing and generating embeddings...')
      
      // Reload documents after a short delay
      setTimeout(() => {
        loadData()
        setUploadProgress('')
        setUploading(false)
      }, 2000)

    } catch (err: any) {
      console.error('Error uploading document:', err)
      setError(err.response?.data?.detail || 'Failed to upload document')
      setUploading(false)
      setUploadProgress('')
    }
  }

  const handleDeleteDocument = async (documentId: number) => {
    if (!confirm('Are you sure you want to delete this document?')) return

    try {
      await api.delete(`/agents/${agentId}/documents/${documentId}`)
      await loadData()
    } catch (err: any) {
      console.error('Error deleting document:', err)
      setError(err.response?.data?.detail || 'Failed to delete document')
    }
  }

  const handleToggleRAG = async (enabled: boolean) => {
    try {
      setError('') // Clear any previous errors
      
      const formData = new FormData()
      formData.append('enabled', enabled.toString())
      
      const response = await api.put(`/agents/${agentId}/rag/toggle`, formData)
      
      console.log('RAG toggle response:', response.data)
      
      // Reload agent data from server to confirm the setting was saved
      await loadData()
      
      console.log('RAG successfully toggled to:', enabled)
    } catch (err: any) {
      console.error('Error toggling RAG:', err)
      setError(err.response?.data?.detail || 'Failed to toggle RAG')
      // Reload data even on error to show current state
      await loadData()
    }
  }

  const handleScrapeWebsite = async () => {
    if (!websiteUrl) {
      setError('Please enter a website URL')
      return
    }

    // Basic URL validation
    try {
      new URL(websiteUrl)
    } catch {
      setError('Please enter a valid URL (e.g., https://example.com)')
      return
    }

    try {
      setScrapingWebsite(true)
      setError('')
      setUploadProgress('Scraping website...')

      await api.post(`/agents/${agentId}/documents/website`, {
        url: websiteUrl
      })

      setUploadProgress('Processing and generating embeddings...')
      
      // Reload documents after a short delay
      setTimeout(() => {
        loadData()
        setUploadProgress('')
        setScrapingWebsite(false)
        setWebsiteUrl('')
      }, 2000)

    } catch (err: any) {
      console.error('Error scraping website:', err)
      setError(err.response?.data?.detail || 'Failed to scrape website')
      setScrapingWebsite(false)
      setUploadProgress('')
    }
  }

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return 'N/A'
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  const getSourceIcon = (sourceType: string) => {
    if (sourceType === 'website') {
      return '🌐'
    }
    return '📄'
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const getStatusBadge = (status: Document['status']) => {
    switch (status) {
      case 'completed':
        return <Badge variant="success">Completed</Badge>
      case 'processing':
        return <Badge variant="warning">Processing</Badge>
      case 'failed':
        return <Badge variant="error">Failed</Badge>
      default:
        return <Badge variant="default">Pending</Badge>
    }
  }

  const getStatusIcon = (status: Document['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircleIcon className="w-5 h-5 text-green-500" />
      case 'processing':
        return <ClockIcon className="w-5 h-5 text-yellow-500 animate-spin" />
      case 'failed':
        return <ExclamationTriangleIcon className="w-5 h-5 text-red-500" />
      default:
        return <ClockIcon className="w-5 h-5 text-gray-400" />
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600"></div>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <button
          onClick={() => navigate('/agents')}
          className="flex items-center text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 mb-4"
        >
          <ArrowLeftIcon className="w-4 h-4 mr-2" />
          Back to Agents
        </button>
        
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
              RAG Documents
            </h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Agent: {agent?.name}
            </p>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600 dark:text-gray-400">RAG Enabled:</span>
              <button
                onClick={() => handleToggleRAG(!agent?.rag_enabled)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  agent?.rag_enabled ? 'bg-purple-600' : 'bg-gray-300 dark:bg-gray-600'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    agent?.rag_enabled ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="mb-6 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <p className="text-red-600 dark:text-red-400">{error}</p>
        </div>
      )}

      {/* Upload Section */}
      <Card className="mb-6">
        <div className="p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Add Knowledge Sources
          </h2>
          
          {/* PDF Upload */}
          <div className="mb-6">
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
              📄 Upload PDF Document
            </h3>
            <div className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-6 text-center">
              {uploading ? (
                <div className="flex flex-col items-center">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mb-4"></div>
                  <p className="text-gray-600 dark:text-gray-400">{uploadProgress}</p>
                </div>
              ) : (
                <>
                  <CloudArrowUpIcon className="w-10 h-10 text-gray-400 mx-auto mb-3" />
                  <p className="text-gray-600 dark:text-gray-400 mb-2">
                    Click to upload or drag and drop
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-500 mb-3">
                    PDF files only, max 10MB (supports scanned PDFs)
                  </p>
                  <label className="cursor-pointer">
                    <input
                      type="file"
                      accept=".pdf"
                      onChange={handleFileUpload}
                      className="hidden"
                      disabled={uploading}
                    />
                    <Button variant="primary" disabled={uploading}>
                      Choose File
                    </Button>
                  </label>
                </>
              )}
            </div>
          </div>

          {/* Website Scraping */}
          <div>
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
              🌐 Scrape Website
            </h3>
            <div className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-6">
              {scrapingWebsite ? (
                <div className="flex flex-col items-center">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mb-4"></div>
                  <p className="text-gray-600 dark:text-gray-400">{uploadProgress}</p>
                </div>
              ) : (
                <div className="flex gap-3">
                  <input
                    type="url"
                    value={websiteUrl}
                    onChange={(e) => setWebsiteUrl(e.target.value)}
                    placeholder="https://example.com/documentation"
                    className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-600"
                    disabled={scrapingWebsite}
                  />
                  <Button 
                    variant="primary" 
                    onClick={handleScrapeWebsite}
                    disabled={scrapingWebsite || !websiteUrl}
                  >
                    Scrape
                  </Button>
                </div>
              )}
            </div>
          </div>
          
          <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
            <p className="text-sm text-blue-800 dark:text-blue-300">
              <strong>How it works:</strong> Add PDF documents or website URLs to give your agent knowledge. 
              Content will be processed, chunked, and embedded for semantic search during conversations.
            </p>
          </div>
        </div>
      </Card>

      {/* Documents List */}
      <Card>
        <div className="p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Uploaded Documents ({documents.length})
          </h2>

          {documents.length === 0 ? (
            <div className="text-center py-12">
              <DocumentTextIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600 dark:text-gray-400">
                No documents uploaded yet
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3 flex-1">
                      {getStatusIcon(doc.status)}
                      
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="font-medium text-gray-900 dark:text-white">
                            {doc.original_filename}
                          </h3>
                          {getStatusBadge(doc.status)}
                        </div>
                        
                        <div className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
                          <p className="flex items-center gap-2">
                            <span>{getSourceIcon(doc.source_type)}</span>
                            <span className="font-medium capitalize">{doc.source_type}</span>
                            {doc.source_type === 'pdf' && (
                              <span>• Size: {formatFileSize(doc.file_size)}</span>
                            )}
                            {doc.total_pages && ` • Pages: ${doc.total_pages}`}
                            {doc.status === 'completed' && ` • Chunks: ${doc.total_chunks}`}
                          </p>
                          {doc.source_url && (
                            <p className="truncate">
                              <a 
                                href={doc.source_url} 
                                target="_blank" 
                                rel="noopener noreferrer"
                                className="text-purple-600 dark:text-purple-400 hover:underline"
                              >
                                {doc.source_url}
                              </a>
                            </p>
                          )}
                          <p>Added: {formatDate(doc.created_at)}</p>
                          {doc.processed_at && (
                            <p>Processed: {formatDate(doc.processed_at)}</p>
                          )}
                          {doc.error_message && (
                            <p className="text-red-600 dark:text-red-400">
                              Error: {doc.error_message}
                            </p>
                          )}
                        </div>
                      </div>
                    </div>

                    <button
                      onClick={() => handleDeleteDocument(doc.id)}
                      className="p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                      title="Delete document"
                    >
                      <TrashIcon className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}

