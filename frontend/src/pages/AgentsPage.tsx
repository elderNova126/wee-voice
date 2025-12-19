import { useEffect, useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import {
  PlusIcon,
  MicrophoneIcon,
  PencilIcon,
  TrashIcon,
  PlayIcon,
  CodeBracketIcon,
  UserGroupIcon,
  UserIcon,
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
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [testingAgent, setTestingAgent] = useState<Agent | null>(null)
  const [filter, setFilter] = useState<FilterType>('all')

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

  // Filter agents based on selected filter
  const filteredAgents = agents.filter((agent) => {
    if (filter === 'my') return agent.is_owner
    if (filter === 'team') return agent.role === 'collaborator'
    return true // 'all'
  })

  const myAgents = agents.filter((a) => a.is_owner)
  const teamAgents = agents.filter((a) => a.role === 'collaborator')

  return (
    <DashboardLayout>
      <div className="mb-8 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">{t.agentsPage.title}</h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            {t.agentsPage.subtitle}
          </p>
        </div>
        <Link
          to="/dashboard/agents/new"
          className="inline-flex items-center px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium shadow-sm transition"
        >
          <PlusIcon className="h-5 w-5 mr-2" />
          {t.agentsPage.newAgent}
        </Link>
      </div>

      {/* Filter Tabs */}
      {agents.length > 0 && (
        <div className="mb-6 flex gap-2 border-b border-gray-200 dark:border-gray-700">
          <button
            onClick={() => setFilter('all')}
            className={`px-4 py-2 font-medium text-sm transition-colors border-b-2 ${
              filter === 'all'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
            }`}
          >
            All ({agents.length})
          </button>
          <button
            onClick={() => setFilter('my')}
            className={`px-4 py-2 font-medium text-sm transition-colors border-b-2 flex items-center gap-2 ${
              filter === 'my'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
            }`}
          >
            <UserIcon className="h-4 w-4" />
            My Agents ({myAgents.length})
          </button>
          {teamAgents.length > 0 && (
            <button
              onClick={() => setFilter('team')}
              className={`px-4 py-2 font-medium text-sm transition-colors border-b-2 flex items-center gap-2 ${
                filter === 'team'
                  ? 'border-purple-600 text-purple-600 dark:text-purple-400'
                  : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
              }`}
            >
              <UserGroupIcon className="h-4 w-4" />
              Team Agents ({teamAgents.length})
            </button>
          )}
        </div>
      )}

      {/* Loading Skeleton */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="bg-white dark:bg-gray-800 p-6 rounded-2xl shadow animate-pulse"
            >
              <div className="h-32 bg-gray-200 dark:bg-gray-700 rounded-xl" />
            </div>
          ))}
        </div>
      ) : filteredAgents.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 px-6 text-center bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl shadow-sm">
          <div className="bg-blue-100 dark:bg-blue-900 p-4 rounded-full mb-4">
            <MicrophoneIcon className="h-10 w-10 text-blue-600 dark:text-blue-300" />
          </div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            {filter === 'team' ? 'No Team Agents' : filter === 'my' ? 'No Agents Yet' : t.agentsPage.noAgentsYet}
          </h3>
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-400 max-w-sm">
            {filter === 'team' 
              ? 'You are not a collaborator on any agents yet.' 
              : filter === 'my'
              ? 'Create your first agent to get started.'
              : t.agentsPage.noAgentsDescription}
          </p>
          {filter !== 'team' && (
            <Link
              to="/dashboard/agents/new"
              className="mt-6 inline-flex items-center px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium transition"
            >
              <PlusIcon className="h-5 w-5 mr-2" />
              {t.agentsPage.createAgent}
            </Link>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredAgents.map((agent) => (
            <div
              key={agent.id}
              className={`relative bg-white dark:bg-gray-800 p-6 rounded-2xl shadow-sm hover:shadow-lg transition-all ${
                agent.role === 'collaborator'
                  ? 'border-2 border-purple-200 dark:border-purple-800'
                  : 'border border-gray-200 dark:border-gray-700'
              }`}
            >
              {/* Status and Role Badges */}
              <div className="absolute top-4 right-4 flex gap-2 flex-wrap justify-end max-w-[50%]">
                {agent.role === 'collaborator' && (
                  <span className="px-2.5 py-1 text-xs font-medium rounded-full bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300 flex items-center gap-1">
                    <UserGroupIcon className="h-3 w-3" />
                    {t.common.status === 'Statut' ? 'Équipe' : 'Team'}
                  </span>
                )}
                {agent.is_owner && (
                  <span className="px-2.5 py-1 text-xs font-medium rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300 flex items-center gap-1">
                    <UserIcon className="h-3 w-3" />
                    Owner
                  </span>
                )}
                <span
                  className={`px-2.5 py-1 text-xs font-medium rounded-full ${
                    agent.is_active
                      ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                      : 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
                  }`}
                >
                  {agent.is_active ? t.agentsPage.active : t.agentsPage.inactive}
                </span>
              </div>

              <div className="flex items-center mb-4">
                <div className="p-3 bg-blue-100 dark:bg-blue-900 rounded-xl">
                  {agent.interaction_mode === 'text' ? (
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="h-6 w-6 text-blue-600 dark:text-blue-300">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                  ) : agent.interaction_mode === 'both' ? (
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="h-6 w-6 text-blue-600 dark:text-blue-300">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
                    </svg>
                  ) : (
                    <MicrophoneIcon className="h-6 w-6 text-blue-600 dark:text-blue-300" />
                  )}
                </div>
                <div className="ml-3">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white truncate">
                    {agent.name}
                  </h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {agent.language === 'fr-FR' ? '🇫🇷 French' : '🇬🇧 English'} •{' '}
                    {agent.is_public ? t.agentsPage.public : t.agentsPage.private} •{' '}
                    {agent.interaction_mode === 'text' ? '💬 Text' : agent.interaction_mode === 'both' ? '🎤💬 Both' : '🎤 Voice'}
                  </p>
                </div>
              </div>

              {/* Permissions for team agents */}
              {agent.role === 'collaborator' && agent.permissions && agent.permissions.length > 0 && (
                <div className="mb-3 flex flex-wrap gap-1">
                  {agent.permissions.map((perm) => (
                    <span
                      key={perm}
                      className="px-2 py-0.5 text-xs font-medium rounded bg-purple-50 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400"
                    >
                      {perm}
                    </span>
                  ))}
                </div>
              )}

              <p className="text-sm text-gray-600 dark:text-gray-400 mb-6 line-clamp-2">
                {agent.description || t.agentsPage.noDescription}
              </p>

              <div className="flex gap-2">
                <button
                  onClick={() => handleTest(agent)}
                  className="flex-1 inline-flex justify-center items-center gap-2 rounded-lg bg-blue-50 hover:bg-blue-100 dark:bg-blue-950 dark:hover:bg-blue-900 text-blue-700 dark:text-blue-300 font-medium text-sm py-2 transition"
                >
                  <PlayIcon className="h-4 w-4" />
                  {t.agentsPage.test}
                </button>
                {(agent.is_owner || agent.permissions?.includes('edit')) && (
                  <Link
                    to={`/dashboard/agents/${agent.id}/embed`}
                    className="p-2.5 rounded-lg bg-indigo-100 hover:bg-indigo-200 dark:bg-indigo-900 dark:hover:bg-indigo-800 text-indigo-700 dark:text-indigo-300 transition"
                    title="Embed Widget"
                  >
                    <CodeBracketIcon className="h-4 w-4" />
                  </Link>
                )}
                {(agent.is_owner || agent.permissions?.includes('edit')) && (
                  <Link
                    to={`/dashboard/agents/${agent.id}/edit`}
                    className="p-2.5 rounded-lg bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 transition"
                    title={t.agentsPage.edit}
                  >
                    <PencilIcon className="h-4 w-4" />
                  </Link>
                )}
                {(agent.is_owner || agent.permissions?.includes('delete')) && (
                  <button
                    onClick={() => handleDelete(agent.id)}
                    className="p-2.5 rounded-lg bg-gray-100 hover:bg-red-100 dark:bg-gray-700 dark:hover:bg-red-900 text-red-600 transition"
                    title={t.agentsPage.delete}
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

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
// Test Agent Modal
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
    
    // Close audio contexts only if they're not already closed
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 backdrop-blur-sm">
      <div className="fixed inset-0 bg-black bg-opacity-50" />
      <div className="relative bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-w-2xl w-full p-8 z-10">
        <div className="mb-6 text-center">
          <h3 className="text-2xl font-bold text-gray-900 dark:text-white">
            Agent: {agent.name}
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            {agent.language === 'fr-FR' ? '🇫🇷 French' : '🇬🇧 English'} •{' '}
            {agent.is_public ? 'Public Agent' : 'Private Agent'}
          </p>
        </div>

        {/* Connection States */}
        <div className="flex flex-col items-center justify-center py-6">
          {isConnecting ? (
            <>
              <div className="relative mb-4">
                <div className="w-20 h-20 bg-blue-600 rounded-full flex items-center justify-center animate-pulse">
                  <MicrophoneIcon className="h-10 w-10 text-white" />
                </div>
                <div className="absolute inset-0 border-4 border-blue-600 rounded-full animate-spin border-t-transparent" />
              </div>
              <p className="text-gray-700 dark:text-gray-300 font-medium">Connecting...</p>
            </>
          ) : !isConnected ? (
            <button
              onClick={connect}
              className="inline-flex items-center px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-medium text-lg transition"
            >
              <PlayIcon className="h-5 w-5 mr-2" />
              Start
            </button>
          ) : (
            <>
              <div className="relative mb-4">
                <div
                  className={`w-20 h-20 rounded-full bg-blue-600 flex items-center justify-center ${
                    isRecording ? 'animate-pulse' : ''
                  }`}
                >
                  <MicrophoneIcon className="h-10 w-10 text-white" />
                </div>
                {isRecording && (
                  <div className="absolute inset-0 rounded-full border-4 border-blue-600 animate-ping" />
                )}
              </div>
              <p className="text-gray-900 dark:text-white font-semibold mb-4">
                Listening... Speak now
              </p>
              <button
                onClick={disconnect}
                className="px-6 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition"
              >
                Stop
              </button>
            </>
          )}
        </div>

        {/* Transcript */}
        {transcript.length > 0 && (
          <div className="mt-6 bg-gray-50 dark:bg-gray-900 rounded-xl p-4 max-h-60 overflow-y-auto">
            <h4 className="font-semibold text-gray-800 dark:text-white mb-3">Transcript</h4>
            <div className="space-y-2">
              {transcript.map((t, i) => (
                <div
                  key={i}
                  className={`text-sm ${
                    t.role === 'user'
                      ? 'text-blue-700 dark:text-blue-400'
                      : 'text-gray-800 dark:text-gray-200'
                  }`}
                >
                  <strong>{t.role === 'user' ? 'You' : 'Agent'}:</strong> {t.text}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex justify-end mt-8">
          <button
            onClick={handleClose}
            className="px-4 py-2 rounded-lg bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200 font-medium transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
