import { useEffect, useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import { 
  PlusIcon,
  MicrophoneIcon,
  PencilIcon,
  TrashIcon,
  PlayIcon
} from '@heroicons/react/24/outline'
import DashboardLayout from '@/layouts/DashboardLayout'
import { agentsAPI, VoiceWebSocket } from '@/lib/api'
import { useAuthStore } from '@/store/authStore'
import toast from 'react-hot-toast'

interface Agent {
  id: number
  name: string
  description: string
  language: string
  is_active: boolean
  is_public: boolean
  created_at: string
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [testingAgent, setTestingAgent] = useState<Agent | null>(null)

  useEffect(() => {
    loadAgents()
  }, [])

  const loadAgents = async () => {
    try {
      const response = await agentsAPI.list()
      setAgents(response.data)
    } catch (error) {
      console.error('Failed to load agents:', error)
      toast.error('Failed to load agents')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this agent?')) return

    try {
      await agentsAPI.delete(id)
      toast.success('Agent deleted successfully')
      loadAgents()
    } catch (error) {
      console.error('Failed to delete agent:', error)
      toast.error('Failed to delete agent')
    }
  }

  const handleTest = (agent: Agent) => {
    setTestingAgent(agent)
  }

  return (
    <DashboardLayout>
      <div className="mb-8 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Voice Agents</h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            Create and manage your voice agents
          </p>
        </div>
        <Link to="/dashboard/agents/new" className="btn-primary">
          <PlusIcon className="h-5 w-5 mr-2" />
          New Agent
        </Link>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <div key={i} className="card animate-pulse">
              <div className="h-40 bg-gray-200 dark:bg-gray-700 rounded"></div>
            </div>
          ))}
        </div>
      ) : agents.length === 0 ? (
        <div className="card text-center py-12">
          <MicrophoneIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-semibold text-gray-900 dark:text-white">No agents</h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Get started by creating a new voice agent.
          </p>
          <div className="mt-6">
            <Link to="/dashboard/agents/new" className="btn-primary">
              <PlusIcon className="h-5 w-5 mr-2" />
              New Agent
            </Link>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {agents.map((agent) => (
            <div key={agent.id} className="card">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center">
                  <div className="p-2 bg-primary-100 dark:bg-primary-900 rounded-lg">
                    <MicrophoneIcon className="h-6 w-6 text-primary-600" />
                  </div>
                  <div className="ml-3">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                      {agent.name}
                    </h3>
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                      agent.is_active 
                        ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                        : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                    }`}>
                      {agent.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                </div>
              </div>

              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4 line-clamp-2">
                {agent.description || 'No description'}
              </p>

              <div className="flex items-center text-xs text-gray-500 dark:text-gray-400 mb-4">
                <span className="flex items-center">
                  {agent.language === 'fr-FR' ? '🇫🇷 French' : '🇬🇧 English'}
                </span>
                <span className="mx-2">•</span>
                <span>{agent.is_public ? 'Public' : 'Private'}</span>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => handleTest(agent)}
                  className="flex-1 btn-secondary text-sm py-2"
                >
                  <PlayIcon className="h-4 w-4 mr-1" />
                  Test
                </button>
                <Link
                  to={`/dashboard/agents/${agent.id}/edit`}
                  className="btn-secondary p-2"
                >
                  <PencilIcon className="h-4 w-4" />
                </Link>
                <button
                  onClick={() => handleDelete(agent.id)}
                  className="btn-secondary p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900"
                >
                  <TrashIcon className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Test Modal */}
      {testingAgent && (
        <TestAgentModal
          agent={testingAgent}
          onClose={() => setTestingAgent(null)}
        />
      )}
    </DashboardLayout>
  )
}

// Test Agent Modal Component
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

    if (nextPlayTimeRef.current < currentTime) {
      nextPlayTimeRef.current = currentTime
    }

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
      } catch (error) {
        console.error('Error scheduling audio:', error)
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
            event.data.arrayBuffer().then(buffer => {
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
              toast.success('Connected!')
            } else if (data.type === 'transcript') {
              setTranscript(prev => [...prev, { role: data.role, text: data.text }])
            } else if (data.type === 'error') {
              console.error('Backend error:', data.message)
              toast.error(data.message)
            }
          }
        },
        (error) => {
          console.error('WebSocket error:', error)
          toast.error('Connection error')
          setIsConnecting(false)
        },
        () => {
          isRecordingRef.current = false
          setIsRecording(false)
          setIsConnected(false)
        }
      )
    } catch (error) {
      console.error('Connection error:', error)
      toast.error('Microphone access denied')
      setIsConnecting(false)
    }
  }

  const disconnect = () => {
    isRecordingRef.current = false
    setIsRecording(false)

    audioQueueRef.current = []
    nextPlayTimeRef.current = 0

    if (wsRef.current) {
      wsRef.current.disconnect()
      wsRef.current = null
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop())
      mediaStreamRef.current = null
    }

    if (processorRef.current) {
      processorRef.current.disconnect()
      processorRef.current = null
    }

    if (audioContextRef.current) {
      audioContextRef.current.close()
      audioContextRef.current = null
    }

    if (audioPlayerRef.current) {
      audioPlayerRef.current.close()
      audioPlayerRef.current = null
    }

    setIsConnected(false)
  }

  const handleClose = () => {
    disconnect()
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={handleClose} />

        <div className="relative bg-white dark:bg-gray-800 rounded-lg max-w-2xl w-full p-6 shadow-xl">
          <div className="mb-6">
            <h3 className="text-2xl font-bold text-gray-900 dark:text-white">
              Test Agent: {agent.name}
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              {agent.language === 'fr-FR' ? '🇫🇷 French' : '🇬🇧 English'} Voice Agent
            </p>
          </div>

          <div className="mb-6">
            {!isConnected && !isConnecting ? (
              <div className="text-center py-8">
                <MicrophoneIcon className="h-16 w-16 text-primary-600 mx-auto mb-4" />
                <button
                  onClick={connect}
                  className="btn-primary text-lg px-8 py-3"
                >
                  <PlayIcon className="h-5 w-5 mr-2" />
                  Start Test
                </button>
              </div>
            ) : isConnecting ? (
              <div className="text-center py-8">
                <div className="relative inline-block mb-6">
                  <div className="w-20 h-20 rounded-full bg-primary-600 flex items-center justify-center animate-pulse">
                    <MicrophoneIcon className="w-10 h-10 text-white" />
                  </div>
                  <div className="absolute inset-0 rounded-full border-4 border-primary-600 animate-spin" style={{ borderTopColor: 'transparent' }}></div>
                </div>
                <p className="text-lg font-medium text-gray-900 dark:text-white">
                  Connecting...
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
                  Please wait while we establish the connection
                </p>
              </div>
            ) : (
              <div className="text-center py-8">
                <div className="relative inline-block mb-6">
                  <div className={`w-20 h-20 rounded-full bg-primary-600 flex items-center justify-center ${
                    isRecording ? 'animate-pulse' : ''
                  }`}>
                    <MicrophoneIcon className="w-10 h-10 text-white" />
                  </div>
                  {isRecording && (
                    <div className="absolute inset-0 rounded-full border-4 border-primary-600 animate-ping"></div>
                  )}
                </div>
                <p className="text-lg font-medium text-gray-900 dark:text-white mb-4">
                  Listening... Speak now
                </p>
                <button
                  onClick={disconnect}
                  className="bg-red-600 text-white px-6 py-2 rounded-lg hover:bg-red-700"
                >
                  Stop
                </button>
              </div>
            )}
          </div>

          {transcript.length > 0 && (
            <div className="mb-6">
              <h4 className="font-semibold text-gray-900 dark:text-white mb-3">Transcript</h4>
              <div className="space-y-2 max-h-60 overflow-y-auto bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                {transcript.map((item, index) => (
                  <div
                    key={index}
                    className={`text-sm ${
                      item.role === 'user' ? 'text-blue-600 dark:text-blue-400' : 'text-gray-900 dark:text-white'
                    }`}
                  >
                    <strong>{item.role === 'user' ? 'You' : 'Agent'}:</strong> {item.text}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex justify-end">
            <button
              onClick={handleClose}
              className="btn-secondary"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
