import { useEffect, useState, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  PlusIcon,
  MicrophoneIcon,
  PencilIcon,
  TrashIcon,
  PlayIcon,
  CodeBracketIcon,
  UserGroupIcon,
  UserIcon,
  ChatBubbleLeftRightIcon,
  SparklesIcon,
  ClockIcon,
  GlobeAltIcon,
  EyeIcon,
} from '@heroicons/react/24/outline'
import DashboardLayout from '@/layouts/DashboardLayout'
import { agentsAPI, VoiceWebSocket } from '@/lib/api'
import { useAuthStore } from '@/store/authStore'
import toast from 'react-hot-toast'
import { useTranslation } from '@/lib/translations'
import TextChatTest from '@/components/TextChatTest'

interface Agent {
  id: number
  name: string
  description: string
  language: string
  is_active: boolean
  is_public: boolean
  created_at: string
  is_owner?: boolean
  role?: string
  permissions?: string[]
  interaction_mode?: string
}

type FilterType = 'all' | 'my' | 'team'

export default function AgentsPage() {
  const t = useTranslation()
  const navigate = useNavigate()
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [testingAgent, setTestingAgent] = useState<Agent | null>(null)
  const [filter, setFilter] = useState<FilterType>('all')
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    loadAgents()
  }, [])

  const loadAgents = async () => {
    try {
      const response = await agentsAPI.list()
      setAgents(response.data)
    } catch (error) {
      console.error('Failed to load agents:', error)
      toast.error(t.agentsPage.loadError)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm(t.agentsPage.deleteConfirm)) return
    try {
      await agentsAPI.delete(id)
      toast.success(t.agentsPage.deleteSuccess)
      loadAgents()
    } catch (error) {
      console.error('Failed to delete agent:', error)
      toast.error(t.agentsPage.deleteError)
    }
  }

  const handleTest = (agent: Agent) => {
    setTestingAgent(agent)
  }

  // Filter and search agents
  const filteredAgents = agents.filter((agent) => {
    // Filter by type
    if (filter === 'my' && !agent.is_owner) return false
    if (filter === 'team' && agent.role !== 'collaborator') return false
    
    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      return (
        agent.name.toLowerCase().includes(query) ||
        agent.description?.toLowerCase().includes(query) ||
        agent.language.toLowerCase().includes(query)
      )
    }
    
    return true
  })

  const myAgents = agents.filter((a) => a.is_owner)
  const teamAgents = agents.filter((a) => a.role === 'collaborator')

  const getInteractionIcon = (mode?: string) => {
    switch (mode) {
      case 'text':
        return <ChatBubbleLeftRightIcon className="h-6 w-6" />
      case 'both':
        return (
          <div className="flex items-center gap-1">
            <MicrophoneIcon className="h-5 w-5" />
            <ChatBubbleLeftRightIcon className="h-5 w-5" />
          </div>
        )
      default:
        return <MicrophoneIcon className="h-6 w-6" />
    }
  }

  const getInteractionColor = (mode?: string) => {
    switch (mode) {
      case 'text':
        return 'from-purple-500 to-pink-500'
      case 'both':
        return 'from-blue-500 to-purple-500'
      default:
        return 'from-blue-500 to-cyan-500'
    }
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const days = Math.floor(diff / (1000 * 60 * 60 * 24))
    
    if (days === 0) return 'Today'
    if (days === 1) return 'Yesterday'
    if (days < 7) return `${days} days ago`
    if (days < 30) return `${Math.floor(days / 7)} weeks ago`
    return date.toLocaleDateString()
  }

  return (
    <DashboardLayout>
      {/* Enhanced Header */}
      <div className="mb-8">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
              {t.agentsPage.title}
            </h1>
            <p className="mt-2 text-gray-600 dark:text-gray-400 text-lg">
              {t.agentsPage.subtitle}
            </p>
          </div>
          <Link
            to="/dashboard/agents/new"
            className="inline-flex items-center px-6 py-3 rounded-xl bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-semibold shadow-lg hover:shadow-xl transition-all transform hover:scale-105"
          >
            <PlusIcon className="h-5 w-5 mr-2" />
            {t.agentsPage.newAgent}
          </Link>
        </div>

        {/* Search Bar */}
        {agents.length > 0 && (
          <div className="mt-6">
            <div className="relative">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search agents by name, description, or language..."
                className="w-full px-4 py-3 pl-12 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
              />
              <SparklesIcon className="absolute left-4 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
            </div>
          </div>
        )}
      </div>

      {/* Enhanced Filter Tabs */}
      {agents.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-2">
          <button
            onClick={() => setFilter('all')}
            className={`px-5 py-2.5 font-semibold text-sm rounded-xl transition-all ${
              filter === 'all'
                ? 'bg-gradient-to-r from-blue-600 to-purple-600 text-white shadow-lg'
                : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700 hover:border-blue-500'
            }`}
          >
            All ({agents.length})
          </button>
          <button
            onClick={() => setFilter('my')}
            className={`px-5 py-2.5 font-semibold text-sm rounded-xl transition-all flex items-center gap-2 ${
              filter === 'my'
                ? 'bg-gradient-to-r from-blue-600 to-purple-600 text-white shadow-lg'
                : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700 hover:border-blue-500'
            }`}
          >
            <UserIcon className="h-4 w-4" />
            My Agents ({myAgents.length})
          </button>
          {teamAgents.length > 0 && (
            <button
              onClick={() => setFilter('team')}
              className={`px-5 py-2.5 font-semibold text-sm rounded-xl transition-all flex items-center gap-2 ${
                filter === 'team'
                  ? 'bg-gradient-to-r from-purple-600 to-pink-600 text-white shadow-lg'
                  : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700 hover:border-purple-500'
              }`}
            >
              <UserGroupIcon className="h-4 w-4" />
              Team ({teamAgents.length})
            </button>
          )}
        </div>
      )}

      {/* Enhanced Loading Skeleton */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 sm:gap-5 lg:gap-6">
          {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
            <div
              key={i}
              className="bg-white dark:bg-gray-800 p-4 sm:p-5 lg:p-6 rounded-2xl sm:rounded-3xl shadow-lg border border-gray-200 dark:border-gray-700 animate-pulse"
            >
              <div className="h-2 bg-gradient-to-r from-gray-200 to-gray-300 dark:from-gray-700 dark:to-gray-600 rounded-t-2xl mb-4" />
              <div className="h-32 sm:h-40 lg:h-48 bg-gradient-to-br from-gray-200 to-gray-300 dark:from-gray-700 dark:to-gray-600 rounded-xl mb-3 sm:mb-4" />
              <div className="h-3 sm:h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4 mb-2" />
              <div className="h-3 sm:h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2" />
            </div>
          ))}
        </div>
      ) : filteredAgents.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 px-6 text-center bg-gradient-to-br from-white to-gray-50 dark:from-gray-800 dark:to-gray-900 border-2 border-dashed border-gray-300 dark:border-gray-700 rounded-3xl">
          <div className="bg-gradient-to-br from-blue-100 to-purple-100 dark:from-blue-900 dark:to-purple-900 p-6 rounded-full mb-6">
            <MicrophoneIcon className="h-16 w-16 text-blue-600 dark:text-blue-300" />
          </div>
          <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
            {searchQuery 
              ? 'No agents found' 
              : filter === 'team' 
              ? 'No Team Agents' 
              : filter === 'my' 
              ? 'No Agents Yet' 
              : t.agentsPage.noAgentsYet}
          </h3>
          <p className="mt-2 text-gray-600 dark:text-gray-400 max-w-md">
            {searchQuery
              ? 'Try adjusting your search terms'
              : filter === 'team' 
              ? 'You are not a collaborator on any agents yet.' 
              : filter === 'my'
              ? 'Create your first agent to get started with AI-powered conversations.'
              : t.agentsPage.noAgentsDescription}
          </p>
          {filter !== 'team' && !searchQuery && (
            <Link
              to="/dashboard/agents/new"
              className="mt-6 inline-flex items-center px-6 py-3 rounded-xl bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-semibold shadow-lg hover:shadow-xl transition-all transform hover:scale-105"
            >
              <PlusIcon className="h-5 w-5 mr-2" />
              {t.agentsPage.createAgent}
            </Link>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 sm:gap-5 lg:gap-6">
          {filteredAgents.map((agent, index) => {
            // Subtle, refined color scheme aligned with project theme
            const colorSchemes = [
              { gradient: 'from-blue-600 to-indigo-600', icon: 'from-blue-500 to-indigo-500', badge: 'from-blue-600 to-indigo-600', hover: 'hover:from-blue-700 hover:to-indigo-700' },
              { gradient: 'from-indigo-600 to-purple-600', icon: 'from-indigo-500 to-purple-500', badge: 'from-indigo-600 to-purple-600', hover: 'hover:from-indigo-700 hover:to-purple-700' },
              { gradient: 'from-purple-600 to-indigo-600', icon: 'from-purple-500 to-indigo-500', badge: 'from-purple-600 to-indigo-600', hover: 'hover:from-purple-700 hover:to-indigo-700' },
            ]
            const colorScheme = colorSchemes[index % colorSchemes.length]
            
            return (
            <div
              key={agent.id}
              onClick={() => navigate(`/dashboard/agents/${agent.id}/view`)}
              className={`group relative bg-white dark:bg-gray-800 rounded-2xl sm:rounded-3xl shadow-lg hover:shadow-2xl transition-all duration-300 overflow-hidden transform hover:-translate-y-1 cursor-pointer ${
                agent.role === 'collaborator'
                  ? 'border-2 border-purple-200 dark:border-purple-800'
                  : 'border border-gray-200 dark:border-gray-700'
              }`}
            >
              {/* Subtle Gradient Header */}
              <div className={`h-1.5 sm:h-2 bg-gradient-to-r ${colorScheme.gradient} opacity-90`} />

              {/* Status and Role Badges */}
              <div className="absolute top-3 right-3 sm:top-4 sm:right-4 flex gap-1.5 sm:gap-2 flex-wrap justify-end max-w-[55%] sm:max-w-[50%] z-10">
                {agent.role === 'collaborator' && (
                  <span className="px-2 sm:px-3 py-0.5 sm:py-1 text-[10px] sm:text-xs font-semibold rounded-full bg-indigo-600 dark:bg-indigo-500 text-white shadow-sm flex items-center gap-0.5 sm:gap-1">
                    <UserGroupIcon className="h-2.5 w-2.5 sm:h-3 sm:w-3 flex-shrink-0" />
                    <span className="hidden sm:inline">Team</span>
                  </span>
                )}
                <span
                  className={`px-2 sm:px-3 py-0.5 sm:py-1 text-[10px] sm:text-xs font-semibold rounded-full shadow-sm flex items-center gap-0.5 sm:gap-1 ${
                    agent.is_public
                      ? 'bg-green-600 dark:bg-green-500 text-white'
                      : 'bg-gray-600 dark:bg-gray-500 text-white'
                  }`}
                >
                  {agent.is_public ? (
                    <>
                      <GlobeAltIcon className="h-2.5 w-2.5 sm:h-3 sm:w-3 flex-shrink-0" />
                      <span className="hidden sm:inline">{t.agentsPage.public}</span>
                    </>
                  ) : (
                    <>
                      <EyeIcon className="h-2.5 w-2.5 sm:h-3 sm:w-3 flex-shrink-0" />
                      <span className="hidden sm:inline">{t.agentsPage.private}</span>
                    </>
                  )}
                </span>
              </div>

              {/* Agent Header */}
              <div className="p-4 sm:p-5 lg:p-6 pb-3 sm:pb-4">
                <div className="flex items-start gap-3 sm:gap-4 mb-3 sm:mb-4">
                  <div className={`p-3 sm:p-4 rounded-xl sm:rounded-2xl bg-gradient-to-br ${colorScheme.icon} shadow-md flex-shrink-0`}>
                    <div className="text-white">
                      {getInteractionIcon(agent.interaction_mode)}
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg sm:text-xl font-bold text-gray-900 dark:text-white truncate mb-1">
                      {agent.name}
                    </h3>
                    <div className="flex flex-wrap items-center gap-1.5 sm:gap-2 text-[10px] sm:text-xs text-gray-500 dark:text-gray-400">
                      <span className="flex items-center gap-0.5 sm:gap-1">
                        {agent.language === 'fr-FR' ? '🇫🇷' : '🇬🇧'}
                        <span className="hidden sm:inline">{agent.language === 'fr-FR' ? 'French' : 'English'}</span>
                      </span>
                      <span className="hidden sm:inline">•</span>
                      {agent.is_owner && (
                        <>
                          <span className="flex items-center gap-0.5 sm:gap-1">
                            <UserIcon className="h-2.5 w-2.5 sm:h-3 sm:w-3" />
                            <span className="hidden sm:inline">Owner</span>
                          </span>
                          <span className="hidden sm:inline">•</span>
                        </>
                      )}
                      <span className="text-[10px] sm:text-xs">
                        {agent.interaction_mode === 'text' ? '💬' : agent.interaction_mode === 'both' ? '🎤💬' : '🎤'}
                        <span className="hidden sm:inline ml-0.5">
                          {agent.interaction_mode === 'text' ? 'Text' : agent.interaction_mode === 'both' ? 'Both' : 'Voice'}
                        </span>
                      </span>
                    </div>
                  </div>
                </div>

                {/* Description */}
                <p className="text-xs sm:text-sm text-gray-600 dark:text-gray-400 mb-3 sm:mb-4 line-clamp-2 min-h-[2rem] sm:min-h-[2.5rem]">
                  {agent.description || t.agentsPage.noDescription}
                </p>

                {/* Permissions for team agents */}
                {agent.role === 'collaborator' && agent.permissions && agent.permissions.length > 0 && (
                  <div className="mb-3 sm:mb-4 flex flex-wrap gap-1 sm:gap-1.5">
                    {agent.permissions.map((perm) => (
                      <span
                        key={perm}
                        className="px-2 sm:px-2.5 py-0.5 sm:py-1 text-[10px] sm:text-xs font-medium rounded-lg bg-indigo-50 text-indigo-700 dark:bg-indigo-900/20 dark:text-indigo-300 border border-indigo-200/50 dark:border-indigo-800/50"
                      >
                        {perm}
                      </span>
                    ))}
                  </div>
                )}

                {/* Created Date */}
                <div className="flex items-center gap-1 text-[10px] sm:text-xs text-gray-500 dark:text-gray-400 mb-3 sm:mb-4">
                  <ClockIcon className="h-3 w-3 sm:h-3.5 sm:w-3.5" />
                  <span className="hidden sm:inline">Created </span>
                  {formatDate(agent.created_at)}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="px-4 sm:px-5 lg:px-6 pb-4 sm:pb-5 lg:pb-6 pt-0 flex gap-1.5 sm:gap-2" onClick={(e) => e.stopPropagation()}>
                <button
                  onClick={(e) => { e.stopPropagation(); handleTest(agent); }}
                  className={`flex-1 inline-flex justify-center items-center gap-1.5 sm:gap-2 rounded-lg sm:rounded-xl bg-gradient-to-r ${colorScheme.badge} ${colorScheme.hover} text-white font-semibold text-xs sm:text-sm py-2 sm:py-2.5 lg:py-3 transition-all shadow-sm hover:shadow-md transform hover:scale-[1.02]`}
                >
                  <PlayIcon className="h-3.5 w-3.5 sm:h-4 sm:w-4 flex-shrink-0" />
                  <span className="hidden sm:inline">{t.agentsPage.test}</span>
                  <span className="sm:hidden">Test</span>
                </button>
                {(agent.is_owner || agent.permissions?.includes('edit')) && (
                  <>
                    <Link
                      to={`/dashboard/agents/${agent.id}/embed`}
                      onClick={(e) => e.stopPropagation()}
                      className="p-2 sm:p-2.5 lg:p-3 rounded-lg sm:rounded-xl bg-indigo-50 hover:bg-indigo-100 dark:bg-indigo-900/30 dark:hover:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300 transition-all shadow-sm hover:shadow-md"
                      title="Embed Widget"
                    >
                      <CodeBracketIcon className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
                    </Link>
                    <Link
                      to={`/dashboard/agents/${agent.id}/edit`}
                      onClick={(e) => e.stopPropagation()}
                      className="p-2 sm:p-2.5 lg:p-3 rounded-lg sm:rounded-xl bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 transition-all shadow-md hover:shadow-lg"
                      title={t.agentsPage.edit}
                    >
                      <PencilIcon className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
                    </Link>
                  </>
                )}
                {(agent.is_owner || agent.permissions?.includes('delete')) && (
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDelete(agent.id); }}
                    className="p-2 sm:p-2.5 lg:p-3 rounded-lg sm:rounded-xl bg-gray-100 hover:bg-red-100 dark:bg-gray-700 dark:hover:bg-red-900 text-red-600 dark:text-red-400 transition-all shadow-md hover:shadow-lg"
                    title={t.agentsPage.delete}
                  >
                    <TrashIcon className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
                  </button>
                )}
              </div>
            </div>
            )
          })}
        </div>
      )}

      {/* Test Modals */}
      {testingAgent && testingAgent.interaction_mode === 'text' ? (
        <TextChatTest
          agentId={testingAgent.id}
          agentName={testingAgent.name}
          onClose={() => setTestingAgent(null)}
        />
      ) : testingAgent ? (
        <TestAgentModal agent={testingAgent} onClose={() => setTestingAgent(null)} />
      ) : null}
    </DashboardLayout>
  )
}

// ======================
// Enhanced Test Agent Modal
// ======================

interface TestAgentModalProps {
  agent: Agent
  onClose: () => void
}

function TestAgentModal({ agent, onClose }: TestAgentModalProps) {
  const { token } = useAuthStore()
  const [isConnected, setIsConnected] = useState(false)
  const [isConnecting, setIsConnecting] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [transcript, setTranscript] = useState<{ role: string; text: string }[]>([])

  const wsRef = useRef<VoiceWebSocket | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const audioPlayerRef = useRef<AudioContext | null>(null)
  const isRecordingRef = useRef<boolean>(false)
  const audioQueueRef = useRef<Float32Array[]>([])
  const nextPlayTimeRef = useRef<number>(0)

  const playAudioQueue = () => {
    if (!audioPlayerRef.current || audioQueueRef.current.length === 0) return
    const audioContext = audioPlayerRef.current
    const currentTime = audioContext.currentTime
    if (nextPlayTimeRef.current < currentTime) nextPlayTimeRef.current = currentTime

    while (audioQueueRef.current.length > 0) {
      const audioData = audioQueueRef.current.shift()!
      try {
        const audioBuffer = audioContext.createBuffer(1, audioData.length, 24000)
        audioBuffer.getChannelData(0).set(audioData)
        const source = audioContext.createBufferSource()
        source.buffer = audioBuffer
        source.connect(audioContext.destination)
        source.start(nextPlayTimeRef.current)
        nextPlayTimeRef.current += audioBuffer.duration
      } catch (err) {
        console.error('Audio playback error:', err)
      }
    }
  }

  const connect = async () => {
    setIsConnecting(true)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      mediaStreamRef.current = stream
      audioQueueRef.current = []
      nextPlayTimeRef.current = 0

      audioContextRef.current = new AudioContext({ sampleRate: 16000 })
      const source = audioContextRef.current.createMediaStreamSource(stream)
      processorRef.current = audioContextRef.current.createScriptProcessor(2048, 1, 1)
      processorRef.current.onaudioprocess = (e) => {
        if (isRecordingRef.current && wsRef.current) {
          const audioData = e.inputBuffer.getChannelData(0)
          const int16Array = new Int16Array(audioData.length)
          for (let i = 0; i < audioData.length; i++) {
            const s = Math.max(-1, Math.min(1, audioData[i]))
            int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF
          }
          wsRef.current.sendAudio(int16Array.buffer)
        }
      }
      source.connect(processorRef.current)
      processorRef.current.connect(audioContextRef.current.destination)
      audioPlayerRef.current = new AudioContext({ sampleRate: 24000 })

      wsRef.current = new VoiceWebSocket(agent.id, null, token)
      wsRef.current.connect(
        (event) => {
          if (event.data instanceof Blob) {
            event.data.arrayBuffer().then((buffer) => {
              if (audioPlayerRef.current) {
                try {
                  const int16Data = new Int16Array(buffer)
                  const float32Data = new Float32Array(int16Data.length)
                  for (let i = 0; i < int16Data.length; i++) {
                    float32Data[i] = int16Data[i] / 32768.0
                  }
                  audioQueueRef.current.push(float32Data)
                  playAudioQueue()
                } catch (error) {
                  console.error('Error processing audio:', error)
                }
              }
            })
          } else if (typeof event.data === 'string') {
            const data = JSON.parse(event.data)
            if (data.type === 'session_started') {
              isRecordingRef.current = true
              setIsRecording(true)
              setIsConnected(true)
              setIsConnecting(false)
              toast.success('Connected to agent')
            } else if (data.type === 'transcript') {
              setTranscript((prev) => [...prev, { role: data.role, text: data.text }])
            } else if (data.type === 'error') {
              console.error('Backend error:', data.message)
              toast.error(data.message)
            }
          }
        },
        (err) => {
          console.error('WebSocket error:', err)
          toast.error('Connection error')
          setIsConnecting(false)
        },
        () => {
          isRecordingRef.current = false
          setIsRecording(false)
          setIsConnected(false)
        }
      )
    } catch {
      toast.error('Microphone access denied')
      setIsConnecting(false)
    }
  }

  const disconnect = () => {
    isRecordingRef.current = false
    setIsRecording(false)
    audioQueueRef.current = []
    nextPlayTimeRef.current = 0
    wsRef.current?.disconnect()
    mediaStreamRef.current?.getTracks().forEach((t) => t.stop())
    processorRef.current?.disconnect()
    
    if (audioContextRef.current?.state !== 'closed') {
      audioContextRef.current?.close()
    }
    if (audioPlayerRef.current?.state !== 'closed') {
      audioPlayerRef.current?.close()
    }
    
    setIsConnected(false)
  }

  const handleClose = () => {
    disconnect()
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 backdrop-blur-md">
      <div className="fixed inset-0 bg-black/60" onClick={handleClose} />
      <div className="relative bg-white dark:bg-gray-800 rounded-3xl shadow-2xl max-w-2xl w-full p-8 z-10 border border-gray-200 dark:border-gray-700">
        {/* Enhanced Header */}
        <div className="mb-8 text-center">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 mb-4 shadow-lg">
            <MicrophoneIcon className="h-10 w-10 text-white" />
          </div>
          <h3 className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
            {agent.name}
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-2 flex items-center justify-center gap-2">
            <span>{agent.language === 'fr-FR' ? '🇫🇷 French' : '🇬🇧 English'}</span>
            <span>•</span>
            <span>{agent.is_public ? 'Public Agent' : 'Private Agent'}</span>
          </p>
        </div>

        {/* Enhanced Connection States */}
        <div className="flex flex-col items-center justify-center py-8">
          {isConnecting ? (
            <>
              <div className="relative mb-6">
                <div className="w-24 h-24 bg-gradient-to-br from-blue-500 to-purple-500 rounded-full flex items-center justify-center animate-pulse shadow-xl">
                  <MicrophoneIcon className="h-12 w-12 text-white" />
                </div>
                <div className="absolute inset-0 border-4 border-blue-500 rounded-full animate-spin border-t-transparent" />
                <div className="absolute inset-0 border-4 border-purple-500 rounded-full animate-spin border-b-transparent" style={{ animationDirection: 'reverse', animationDuration: '1.5s' }} />
              </div>
              <p className="text-gray-700 dark:text-gray-300 font-semibold text-lg">Connecting to agent...</p>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">Please allow microphone access</p>
            </>
          ) : !isConnected ? (
            <button
              onClick={connect}
              className="inline-flex items-center px-8 py-4 rounded-2xl bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-bold text-lg shadow-xl hover:shadow-2xl transition-all transform hover:scale-105"
            >
              <PlayIcon className="h-6 w-6 mr-3" />
              Start Voice Call
            </button>
          ) : (
            <>
              <div className="relative mb-6">
                <div
                  className={`w-24 h-24 rounded-full bg-gradient-to-br from-green-500 to-emerald-500 flex items-center justify-center shadow-xl ${
                    isRecording ? 'animate-pulse' : ''
                  }`}
                >
                  <MicrophoneIcon className="h-12 w-12 text-white" />
                </div>
                {isRecording && (
                  <>
                    <div className="absolute inset-0 rounded-full border-4 border-green-500 animate-ping" />
                    <div className="absolute inset-0 rounded-full border-4 border-emerald-500 animate-ping" style={{ animationDelay: '0.5s' }} />
                  </>
                )}
              </div>
              <p className="text-gray-900 dark:text-white font-bold text-xl mb-2">
                {isRecording ? '🎤 Listening... Speak now' : 'Connected'}
              </p>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
                The agent is ready to hear you
              </p>
              <button
                onClick={disconnect}
                className="px-8 py-3 bg-gradient-to-r from-red-500 to-pink-500 hover:from-red-600 hover:to-pink-600 text-white rounded-xl font-semibold shadow-lg hover:shadow-xl transition-all transform hover:scale-105"
              >
                End Call
              </button>
            </>
          )}
        </div>

        {/* Enhanced Transcript */}
        {transcript.length > 0 && (
          <div className="mt-8 bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 rounded-2xl p-6 max-h-64 overflow-y-auto border border-gray-200 dark:border-gray-700">
            <h4 className="font-bold text-gray-800 dark:text-white mb-4 flex items-center gap-2">
              <ChatBubbleLeftRightIcon className="h-5 w-5" />
              Conversation Transcript
            </h4>
            <div className="space-y-3">
              {transcript.map((t, i) => (
                <div
                  key={i}
                  className={`p-3 rounded-xl ${
                    t.role === 'user'
                      ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-900 dark:text-blue-200 border border-blue-200 dark:border-blue-800'
                      : 'bg-white dark:bg-gray-800 text-gray-900 dark:text-white border border-gray-200 dark:border-gray-700'
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <span className={`font-bold text-xs ${t.role === 'user' ? 'text-blue-600 dark:text-blue-400' : 'text-purple-600 dark:text-purple-400'}`}>
                      {t.role === 'user' ? 'YOU' : 'AGENT'}
                    </span>
                    <span className="flex-1 text-sm">{t.text}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex justify-end mt-8 pt-6 border-t border-gray-200 dark:border-gray-700">
          <button
            onClick={handleClose}
            className="px-6 py-3 rounded-xl bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200 font-semibold transition-all"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
