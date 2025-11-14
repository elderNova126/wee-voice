import { useState, useEffect, useRef } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { MicrophoneIcon, StopIcon, ArrowLeftIcon, SparklesIcon, GlobeAltIcon, PhoneIcon, PaperAirplaneIcon } from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { VoiceWebSocket, api, callsAPI } from '@/lib/api'
import { useTranslation } from '@/lib/translations'

interface Agent {
  id: number
  name: string
  description: string | null
  language: string
  rag_enabled: boolean
  is_public: boolean
  is_active: boolean
  phone_number?: string | null
  phone_number_status?: string | null
}

export default function PublicAgentPage() {
  const t = useTranslation()
  const { agentId } = useParams<{ agentId: string }>()
  const navigate = useNavigate()
  
  const [agent, setAgent] = useState<Agent | null>(null)
  const [loading, setLoading] = useState(true)
  const [isConnected, setIsConnected] = useState(false)
  const [isConnecting, setIsConnecting] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [transcript, setTranscript] = useState<{ role: string; text: string }[]>([])
  const [callId, setCallId] = useState<number | null>(null)
  const [messageInput, setMessageInput] = useState('')
  const [sendingMessage, setSendingMessage] = useState(false)
  
  const wsRef = useRef<VoiceWebSocket | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const audioPlayerRef = useRef<AudioContext | null>(null)
  const isRecordingRef = useRef<boolean>(false)
  const audioQueueRef = useRef<Float32Array[]>([])
  const isPlayingRef = useRef<boolean>(false)
  const nextPlayTimeRef = useRef<number>(0)
  const isFrench = t.common.status === 'Statut'

  useEffect(() => {
    loadAgent()
    return () => {
      cleanup()
    }
  }, [agentId])

  const loadAgent = async () => {
    try {
      setLoading(true)
      const response = await api.get('/agents/public/list')
      const publicAgents = response.data
      const selectedAgent = publicAgents.find((a: Agent) => a.id === parseInt(agentId || '0'))
      
      if (!selectedAgent) {
        toast.error(t.publicAgent.agentNotFound)
        navigate('/')
        return
      }
      
      if (!selectedAgent.is_active) {
        toast.error(t.publicAgent.agentInactive)
        navigate('/')
        return
      }
      
      setAgent(selectedAgent)
    } catch (error) {
      console.error('Error loading agent:', error)
      toast.error(t.publicAgent.loadError)
      navigate('/')
    } finally {
      setLoading(false)
    }
  }

  const cleanup = () => {
    if (wsRef.current) {
      wsRef.current.disconnect()
      wsRef.current = null
    }
    if (audioContextRef.current) {
      audioContextRef.current.close()
      audioContextRef.current = null
    }
    if (audioPlayerRef.current) {
      audioPlayerRef.current.close()
      audioPlayerRef.current = null
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop())
      mediaStreamRef.current = null
    }
  }

  const initializeAudio = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000
        } 
      })
      mediaStreamRef.current = stream

      const audioContext = new AudioContext({ sampleRate: 16000 })
      audioContextRef.current = audioContext

      const source = audioContext.createMediaStreamSource(stream)
      const processor = audioContext.createScriptProcessor(2048, 1, 1)
      processorRef.current = processor

      processor.onaudioprocess = (e) => {
        if (!isRecordingRef.current || !wsRef.current) return
        
        const inputData = e.inputBuffer.getChannelData(0)
        const pcm16 = new Int16Array(inputData.length)
        for (let i = 0; i < inputData.length; i++) {
          const s = Math.max(-1, Math.min(1, inputData[i]))
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF
        }
        wsRef.current.sendAudio(pcm16.buffer)
      }

      source.connect(processor)
      processor.connect(audioContext.destination)

      const audioPlayer = new AudioContext({ sampleRate: 24000 })
      audioPlayerRef.current = audioPlayer
      nextPlayTimeRef.current = audioPlayer.currentTime

      return true
    } catch (error) {
      console.error('Error initializing audio:', error)
      toast.error(t.common.status === 'Statut' ? 'Impossible d\'accéder au microphone' : 'Could not access microphone')
      return false
    }
  }

  const startConversation = async () => {
    if (!agent) return
    
    try {
      setIsConnecting(true)
      
      const audioReady = await initializeAudio()
      if (!audioReady) {
        setIsConnecting(false)
        return
      }

      const ws = new VoiceWebSocket(agent.id)
      wsRef.current = ws

      ws.connect(
        // onMessage callback
        (event) => {
          if (event.data instanceof Blob) {
            // Audio response
            event.data.arrayBuffer().then(buffer => {
              playAudio(buffer)
            }).catch(error => {
              console.error('Error converting audio buffer:', error)
            })
          } else if (typeof event.data === 'string') {
            const data = JSON.parse(event.data)
            
            if (data.type === 'session_started') {
              console.log('Session started:', data)
              setIsConnected(true)
              setIsConnecting(false)
              setIsRecording(true)
              isRecordingRef.current = true
              if (data.call_id) {
                setCallId(data.call_id)
              }
              toast.success(t.common.status === 'Statut' ? 'Connecté ! Vous pouvez commencer à parler...' : 'Connected! Start speaking...')
            } else if (data.type === 'transcript') {
              setTranscript(prev => [...prev, { role: data.role, text: data.text }])
            } else if (data.type === 'error') {
              console.error('Backend error:', data.message)
              toast.error(data.message)
            }
          }
        },
        // onError callback
        (error) => {
          console.error('WebSocket error:', error)
          toast.error(t.common.status === 'Statut' ? 'Erreur de connexion' : 'Connection error')
          setIsConnecting(false)
          stopConversation()
        },
        // onClose callback
        () => {
          console.log('WebSocket closed')
          setIsConnected(false)
          setIsRecording(false)
          isRecordingRef.current = false
        }
      )
    } catch (error) {
      console.error('Error starting conversation:', error)
      toast.error(t.common.status === 'Statut' ? 'Impossible de démarrer la conversation' : 'Failed to start conversation')
      setIsConnecting(false)
      cleanup()
    }
  }

  const playAudio = (audioData: ArrayBuffer) => {
    if (!audioPlayerRef.current) return

    try {
      // Convert Int16 PCM to Float32
      const int16Data = new Int16Array(audioData)
      const float32Data = new Float32Array(int16Data.length)
      
      for (let i = 0; i < int16Data.length; i++) {
        float32Data[i] = int16Data[i] / 32768.0
      }
      
      // Add to queue and schedule immediately
      audioQueueRef.current.push(float32Data)
      processAudioQueue()
    } catch (error) {
      console.error('Error processing audio:', error)
    }
  }

  const processAudioQueue = () => {
    if (!audioPlayerRef.current || audioQueueRef.current.length === 0) {
      return
    }
    
    const audioContext = audioPlayerRef.current
    const currentTime = audioContext.currentTime
    
    // Initialize next play time if not set or if it's in the past
    if (nextPlayTimeRef.current < currentTime) {
      nextPlayTimeRef.current = currentTime
    }
    
    // Schedule all queued chunks with precise timing to avoid gaps/noise
    while (audioQueueRef.current.length > 0) {
      const audioData = audioQueueRef.current.shift()!
      
      try {
        // Create audio buffer
        const audioBuffer = audioContext.createBuffer(1, audioData.length, 24000)
        audioBuffer.getChannelData(0).set(audioData)
        
        // Create source
        const source = audioContext.createBufferSource()
        source.buffer = audioBuffer
        source.connect(audioContext.destination)
        
        // Schedule to start exactly when the previous chunk ends
        source.start(nextPlayTimeRef.current)
        
        // Update next play time (add duration of this chunk)
        nextPlayTimeRef.current += audioBuffer.duration
      } catch (error) {
        console.error('Error scheduling audio chunk:', error)
      }
    }
  }

  const stopConversation = () => {
    isRecordingRef.current = false
    setIsRecording(false)
    setIsConnected(false)
    setTranscript([])
    setCallId(null)
    setMessageInput('')
    
    // Clear audio queue and reset timing
    audioQueueRef.current = []
    isPlayingRef.current = false
    nextPlayTimeRef.current = 0
    
    cleanup()
    toast.success(t.common.status === 'Statut' ? 'Conversation terminée' : 'Conversation ended')
  }

  const sendMessage = async () => {
    if (!callId || !messageInput.trim()) return
    
    try {
      setSendingMessage(true)
      await callsAPI.sendMessage(callId, messageInput.trim())
      setMessageInput('')
      toast.success(t.common.status === 'Statut' ? 'Message envoyé' : 'Message sent')
    } catch (error: any) {
      console.error('Error sending message:', error)
      toast.error(error?.response?.data?.detail || (t.common.status === 'Statut' ? 'Erreur lors de l\'envoi du message' : 'Failed to send message'))
    } finally {
      setSendingMessage(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
      </div>
    )
  }

  if (!agent) {
    return null
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link
            to="/"
            className="flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors"
          >
            <ArrowLeftIcon className="w-5 h-5" />
            <span className="font-medium">{t.common.status === 'Statut' ? 'Retour à l\'accueil' : 'Back to Home'}</span>
          </Link>
          
          <div className="flex items-center gap-2">
            <MicrophoneIcon className="w-8 h-8 text-indigo-600" />
            <span className="text-xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
              VoiceAgent
            </span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-6 py-12">
        {/* Agent Info */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-8 mb-8 border border-gray-200 dark:border-gray-700">
          <div className="flex items-start gap-6">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center flex-shrink-0 shadow-lg">
              <MicrophoneIcon className="w-10 h-10 text-white" />
            </div>
            
            <div className="flex-1">
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-3">
                {agent.name}
              </h1>
              <p className="text-lg text-gray-600 dark:text-gray-300 mb-4">
                {agent.description || (t.common.status === 'Statut' ? 'Agent vocal prêt à vous aider' : 'Voice agent ready to help you')}
              </p>
              
              <div className="flex flex-wrap gap-2">
                <span className="inline-flex items-center gap-1 px-3 py-1.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-sm font-medium rounded-full">
                  <GlobeAltIcon className="w-4 h-4" />
                  {isFrench ? 'Français' : agent.language === 'en-US' ? 'English' : agent.language}
                </span>
                {agent.rag_enabled && (
                  <span className="inline-flex items-center gap-1 px-3 py-1.5 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 text-sm font-medium rounded-full">
                    <SparklesIcon className="w-4 h-4" />
                    {t.common.status === 'Statut' ? 'Base de connaissances activée' : 'Knowledge Base Enabled'}
                  </span>
                )}
              </div>

              {agent.phone_number && (
                <div className="flex flex-wrap items-center gap-3 mt-4">
                  <a
                    href={`tel:${agent.phone_number}`}
                    className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 text-white text-sm font-semibold rounded-lg shadow-md hover:shadow-lg transition-all duration-200"
                  >
                    <PhoneIcon className="w-4 h-4" />
                    {t.common.status === 'Statut' ? 'Appeler par téléphone' : 'Call by phone'}
                  </a>
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    {agent.phone_number}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Voice Interface */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-8 border border-gray-200 dark:border-gray-700">
          <div className="text-center">
            {!isConnected && !isConnecting && (
              <>
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                  {t.common.status === 'Statut' ? 'Prêt à démarrer ?' : 'Ready to Start?'}
                </h2>
                <p className="text-gray-600 dark:text-gray-400 mb-8">
                  {t.common.status === 'Statut'
                    ? `Cliquez sur le bouton ci-dessous pour parler avec ${agent.name}`
                    : `Click the button below to start talking with ${agent.name}`}
                </p>
                <button
                  onClick={startConversation}
                  className="inline-flex items-center gap-3 px-8 py-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white text-lg font-semibold rounded-xl shadow-lg hover:shadow-xl transition-all duration-200"
                >
                  <MicrophoneIcon className="w-6 h-6" />
                  {t.publicAgent.connect}
                </button>
              </>
            )}

            {isConnecting && (
              <>
                <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-indigo-600 mx-auto mb-4"></div>
                <p className="text-lg text-gray-600 dark:text-gray-400">
                  {t.publicAgent.connecting} {agent.name}...
                </p>
              </>
            )}

            {isConnected && (
              <>
                <div className="relative inline-block mb-8">
                  <div className="w-32 h-32 rounded-full bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center">
                    {isRecording ? (
                      <div className="relative">
                        <div className="absolute inset-0 bg-white rounded-full animate-ping opacity-75"></div>
                        <MicrophoneIcon className="w-16 h-16 text-white relative z-10" />
                      </div>
                    ) : (
                      <MicrophoneIcon className="w-16 h-16 text-white" />
                    )}
                  </div>
                </div>
                
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                  {isRecording
                    ? t.publicAgent.recording
                    : t.publicAgent.connect}
                </h2>
                <p className="text-gray-600 dark:text-gray-400 mb-8">
                  {isRecording
                    ? (t.common.status === 'Statut' ? 'Parlez naturellement – l\'agent vous écoute' : 'Speak naturally – the agent is listening')
                    : (t.common.status === 'Statut' ? 'Traitement en cours...' : 'Processing...')}
                </p>

                {/* Message Input */}
                <div className="mb-6 max-w-md mx-auto">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={messageInput}
                      onChange={(e) => setMessageInput(e.target.value)}
                      onKeyPress={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault()
                          sendMessage()
                        }
                      }}
                      placeholder={t.publicAgent.messagePlaceholder}
                      className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      disabled={sendingMessage}
                    />
                    <button
                      onClick={sendMessage}
                      disabled={!messageInput.trim() || sendingMessage}
                      className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
                    >
                      <PaperAirplaneIcon className="w-5 h-5" />
                    </button>
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-2 text-center">
                    {t.common.status === 'Statut' ? 'Vous pouvez aussi envoyer un message texte' : 'You can also send a text message'}
                  </p>
                </div>

                <button
                  onClick={stopConversation}
                  className="inline-flex items-center gap-3 px-8 py-4 bg-red-600 hover:bg-red-700 text-white text-lg font-semibold rounded-xl shadow-lg hover:shadow-xl transition-all duration-200"
                >
                  <StopIcon className="w-6 h-6" />
                  {t.publicAgent.disconnect}
                </button>
              </>
            )}
          </div>

          {/* Tips */}
          {!isConnected && !isConnecting && (
            <div className="mt-8 pt-8 border-t border-gray-200 dark:border-gray-700">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">
                {t.common.status === 'Statut' ? 'Conseils pour une meilleure expérience :' : 'Tips for best experience:'}
              </h3>
              <ul className="space-y-2 text-sm text-gray-600 dark:text-gray-400">
                <li className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-indigo-600"></div>
                  {t.common.status === 'Statut' ? 'Choisissez un environnement calme' : 'Use a quiet environment'}
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-indigo-600"></div>
                  {t.common.status === 'Statut' ? 'Parlez clairement et naturellement' : 'Speak clearly and naturally'}
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-indigo-600"></div>
                  {t.common.status === 'Statut' ? 'Autorisez l\'accès au micro lorsqu\'on vous le demande' : 'Allow microphone access when prompted'}
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-indigo-600"></div>
                  {t.common.status === 'Statut' ? 'Fonctionne mieux avec les navigateurs Chrome ou Edge' : 'Works best with Chrome or Edge browsers'}
                </li>
              </ul>
            </div>
          )}
        </div>

        {/* Transcript */}
        {transcript.length > 0 && (
          <div className="mt-8 bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-8 border border-gray-200 dark:border-gray-700">
            <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
              {t.callDetail.conversation}
            </h3>
            <div className="space-y-4">
              {transcript.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] px-4 py-3 rounded-2xl ${
                      msg.role === 'user'
                        ? 'bg-indigo-600 text-white'
                        : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white'
                    }`}
                  >
                    <p className="text-sm font-medium mb-1 opacity-75">
                      {msg.role === 'user' ? (t.common.status === 'Statut' ? 'Vous' : 'You') : agent.name}
                    </p>
                    <p>{msg.text}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

