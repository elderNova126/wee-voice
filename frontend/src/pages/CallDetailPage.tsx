import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { callsAPI } from '@/lib/api'
import { format } from 'date-fns'
import { fr, enUS } from 'date-fns/locale'
import toast from 'react-hot-toast'
import {
  ArrowLeftIcon,
  ClockIcon,
  CurrencyDollarIcon,
  DocumentTextIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline'
import { useTranslation } from '@/lib/translations'

export default function CallDetailPage() {
  const t = useTranslation()
  const { callId } = useParams<{ callId: string }>()
  const [activeTab, setActiveTab] = useState<'overview' | 'transcript'>('overview')
  const queryClient = useQueryClient()
  
  const { data: call, isLoading } = useQuery({
    queryKey: ['call', callId],
    queryFn: async () => {
      const response = await callsAPI.get(Number(callId))
      return response.data
    },
  })
  
  const generateSummaryMutation = useMutation({
    mutationFn: () => callsAPI.generateSummary(Number(callId)),
    onSuccess: (response) => {
      toast.success(t.callDetail.summaryGenerated)
      queryClient.invalidateQueries({ queryKey: ['call', callId] })
    },
    onError: () => {
      toast.error(t.callDetail.summaryError)
    },
  })
  
  if (isLoading) {
    return (
      <div className="text-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto"></div>
      </div>
    )
  }
  
  if (!call) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-600 dark:text-gray-400">{t.callDetail.callNotFound}</p>
      </div>
    )
  }
  
  const locale = t.common.status === 'Statut' ? fr : enUS
  
  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <Link
          to="/dashboard/calls"
          className="inline-flex items-center text-gray-600 dark:text-gray-400 hover:text-primary-600 mb-4"
        >
          <ArrowLeftIcon className="w-5 h-5 mr-2" />
          {t.callDetail.backToCalls}
        </Link>
        
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
              {t.callDetail.callDetails} #{call.id}
            </h1>
            <p className="text-gray-600 dark:text-gray-400">
              {format(new Date(call.started_at), 'PPpp', { locale })}
            </p>
          </div>
          
          {call.transcript && (
            <button
              onClick={() => generateSummaryMutation.mutate()}
              disabled={generateSummaryMutation.isPending}
              className="btn-primary flex items-center"
            >
              <SparklesIcon className="w-5 h-5 mr-2" />
              {generateSummaryMutation.isPending
                ? t.callDetail.generating
                : call.summary
                  ? t.callDetail.regenerateSummary
                  : t.callDetail.generateSummary}
            </button>
          )}
        </div>
      </div>
      
      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700 mb-6">
        <nav className="flex space-x-8">
          <button
            onClick={() => setActiveTab('overview')}
            className={`pb-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'overview'
                ? 'border-primary-600 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400'
            }`}
          >
            {t.callDetail.overview}
          </button>
          <button
            onClick={() => setActiveTab('transcript')}
            className={`pb-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'transcript'
                ? 'border-primary-600 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400'
            }`}
          >
            {t.callDetail.transcript}
          </button>
        </nav>
      </div>
      
      {/* Content */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* Stats */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="card">
              <div className="flex items-center space-x-3">
                <ClockIcon className="w-8 h-8 text-blue-600" />
                <div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">{t.callDetail.duration}</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">
                    {call.duration_minutes.toFixed(1)} {t.common.status === 'Statut' ? 'min' : 'min'}
                  </p>
                </div>
              </div>
            </div>
            
            <div className="card">
              <div className="flex items-center space-x-3">
                <CurrencyDollarIcon className="w-8 h-8 text-green-600" />
                <div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">{t.callDetail.cost}</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">
                    ${call.cost.toFixed(3)}
                  </p>
                </div>
              </div>
            </div>
            
            <div className="card">
              <div className="flex items-center space-x-3">
                <DocumentTextIcon className="w-8 h-8 text-purple-600" />
                <div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">{t.callDetail.status}</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white capitalize">
                    {call.status}
                  </p>
                </div>
              </div>
            </div>
          </div>
          
          {/* Summary */}
          {call.summary && (
            <div className="card">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                {t.callDetail.callSummary}
              </h3>
              <p className="text-gray-700 dark:text-gray-300 mb-4">
                {call.summary}
              </p>
              
              {call.sentiment && (
                <div className="flex items-center space-x-2 mb-4">
                  <span className="text-sm text-gray-600 dark:text-gray-400">{t.callDetail.sentiment}</span>
                  <span className="px-3 py-1 rounded-full text-sm font-medium bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
                    {call.sentiment}
                  </span>
                </div>
              )}
              
              {call.action_tags && call.action_tags.length > 0 && (
                <div className="mb-4">
                  <h4 className="font-medium text-gray-900 dark:text-white mb-2">
                    {t.callDetail.detectedActions}
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {call.action_tags.map((tag: string, index: number) => (
                      <span
                        key={`detail-tag-${index}`}
                        className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-100"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              
              {call.key_points && call.key_points.length > 0 && (
                <div>
                  <h4 className="font-medium text-gray-900 dark:text-white mb-2">
                    {t.callDetail.keyPoints}
                  </h4>
                  <ul className="list-disc list-inside space-y-1 text-gray-700 dark:text-gray-300">
                    {call.key_points.map((point: string, index: number) => (
                      <li key={index}>{point}</li>
                    ))}
                  </ul>
                </div>
              )}

              {call.action_items && call.action_items.length > 0 && (
                <div className="mt-4">
                  <h4 className="font-medium text-gray-900 dark:text-white mb-2">
                    {t.callDetail.actionItems}
                  </h4>
                  <ul className="list-disc list-inside space-y-1 text-gray-700 dark:text-gray-300">
                    {call.action_items.map((item: string, index: number) => (
                      <li key={`action-item-${index}`}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
          
          {/* Messages */}
          {call.messages && call.messages.length > 0 && (
            <div className="card">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                {t.callDetail.conversation}
              </h3>
              <div className="space-y-4 max-h-96 overflow-y-auto">
                {call.messages.map((message: any, index: number) => (
                  <div
                    key={index}
                    className={`p-4 rounded-lg ${
                      message.role === 'user'
                        ? 'bg-blue-50 dark:bg-blue-900 ml-8'
                        : 'bg-gray-50 dark:bg-gray-700 mr-8'
                    }`}
                  >
                    <div className="font-medium text-sm text-gray-500 dark:text-gray-400 mb-1">
                      {message.role === 'user' ? t.callDetail.user : t.callDetail.agent} •{' '}
                      {format(new Date(message.timestamp), 'HH:mm:ss')}
                    </div>
                    <div className="text-gray-900 dark:text-white">
                      {message.content}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
      
      {activeTab === 'transcript' && (
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            {t.callDetail.fullTranscript}
          </h3>
          {call.transcript ? (
            <div className="prose dark:prose-invert max-w-none">
              <pre className="whitespace-pre-wrap text-gray-700 dark:text-gray-300">
                {call.transcript}
              </pre>
            </div>
          ) : (
            <p className="text-gray-600 dark:text-gray-400">
              {t.callDetail.transcriptNotAvailable}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

