import { useState, useEffect, useRef } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { MicrophoneIcon, StopIcon, ArrowLeftIcon, SparklesIcon, GlobeAltIcon, PhoneIcon, PaperAirplaneIcon, ChatBubbleLeftRightIcon } from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { VoiceWebSocket, api, callsAPI, API_URL } from '@/lib/api'
import { useTranslation } from '@/lib/translations'
import { LoadingSpinner, AvatarPhotoSelector, VideoAvatar } from '@/components/ui'

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
  interaction_mode?: string
}

export default function PublicAgentPageWithAvatar() {
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
  const [textChatMessages, setTextChatMessages] = useState<Array<{ role: string; content: string; timestamp: string }>>([])
  const [textChatConnected, setTextChatConnected] = useState(false)
  const [textChatConnecting, setTextChatConnecting] = useState(false)
  const [isWaitingForResponse, setIsWaitingForResponse] = useState(false)
  const [selectedMode, setSelectedMode] = useState<'chat' | 'voice'>('voice')
  
  // Avatar states
  const [avatarPhotoUrl, setAvatarPhotoUrl] = useState<string | null>(null)
  const [avatarEnabled, setAvatarEnabled] = useState(false)
  const [showAvatarSelector, setShowAvatarSelector] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  
  const textChatWsRef = useRef<WebSocket | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  
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
      cleanupTextChat()
    }
  }, [agentId])

  useEffect(() => {
    if (agent) {
      if (agent.interaction_mode === 'text') {
        setSelectedMode('chat')
      } else if (agent.interaction_mode === 'voice') {
        setSelectedMode('voice')
      } else if (agent.interaction_mode === 'both') {
        setSelectedMode('voice')
      }
    }
  }, [agent])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [textChatMessages])

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

  const cleanupTextChat = () => {
    if (textChatWsRef.current) {
      textChatWsRef.current.close()
      textChatWsRef.current = null
    }
    setTextChatConnected(false)
    setTextChatConnecting(false)
    setTextChatMessages([])
  }

  const handleAvatarPhotoSelected = (photoUrl: string, photoType: 'upload' | 'sample') => {
    setAvatarPhotoUrl(photoUrl)
    setAvatarEnabled(true)
    toast.success(isFrench ? 'Avatar activé !' : 'Avatar enabled!')
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
        (event) => {
          if (event.data instanceof Blob) {
            // Audio response - trigger speaking animation
            setIsSpeaking(true)
            setTimeout(() => setIsSpeaking(false), 1000)
            
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
        (error) => {
          console.error('WebSocket error:', error)
          toast.error(t.common.status === 'Statut' ? 'Erreur de connexion' : 'Connection error')
          setIsConnecting(false)
          stopConversation()
        },
        () => {
          console.log('WebSocket closed')
          setIsConnected(false)
          setIsRecording(false)
          isRecordingRef.current = false
          setIsSpeaking(false)
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
      const int16Data = new Int16Array(audioData)
      const float32Data = new Float32Array(int16Data.length)
      
      for (let i = 0; i < int16Data.length; i++) {
        float32Data[i] = int16Data[i] / 32768.0
      }
      
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
    setIsSpeaking(false)
    
    audioQueueRef.current = []
    isPlayingRef.current = false
    nextPlayTimeRef.current = 0
    
    cleanup()
    toast.success(t.common.status === 'Statut' ? 'Conversation terminée' : 'Conversation ended')
  }

  const handleModeSwitch = (mode: 'chat' | 'voice') => {
    if (mode === 'chat' && isConnected) {
      stopConversation()
    } else if (mode === 'voice' && textChatConnected) {
      cleanupTextChat()
    }
    setSelectedMode(mode)
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <LoadingSpinner size="md" />
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
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
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
      <main className="max-w-6xl mx-auto px-6 py-12">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column - Agent Info & Avatar Selector */}
          <div className="lg:col-span-1 space-y-6">
            {/* Agent Info */}
            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-6 border border-gray-200 dark:border-gray-700">
              <div className="flex items-start gap-4 mb-4">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center flex-shrink-0 shadow-lg">
                  <MicrophoneIcon className="w-8 h-8 text-white" />
                </div>
                
                <div className="flex-1">
                  <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                    {agent.name}
                  </h1>
                  <p className="text-sm text-gray-600 dark:text-gray-300">
                    {agent.description || (t.common.status === 'Statut' ? 'Agent vocal prêt à vous aider' : 'Voice agent ready to help you')}
                  </p>
                </div>
              </div>
              
              <div className="flex flex-wrap gap-2">
                <span className="inline-flex items-center gap-1 px-3 py-1.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-xs font-medium rounded-full">
                  <GlobeAltIcon className="w-4 h-4" />
                  {isFrench ? 'Français' : agent.language === 'en-US' ? 'English' : agent.language}
                </span>
                {agent.rag_enabled && (
                  <span className="inline-flex items-center gap-1 px-3 py-1.5 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 text-xs font-medium rounded-full">
                    <SparklesIcon className="w-4 h-4" />
                    {t.common.status === 'Statut' ? 'Base de connaissances' : 'Knowledge Base'}
                  </span>
                )}
              </div>
            </div>

            {/* Avatar Selector */}
            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-6 border border-gray-200 dark:border-gray-700">
              <button
                onClick={() => setShowAvatarSelector(!showAvatarSelector)}
                className="w-full flex items-center justify-between mb-4"
              >
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  {isFrench ? '🎭 Avatar Vidéo' : '🎭 Video Avatar'}
                </h3>
                <span className="text-sm text-indigo-600 dark:text-indigo-400 font-medium">
                  {showAvatarSelector ? (isFrench ? 'Masquer' : 'Hide') : (isFrench ? 'Configurer' : 'Setup')}
                </span>
              </button>
              
              {showAvatarSelector && (
                <AvatarPhotoSelector
                  onPhotoSelected={handleAvatarPhotoSelected}
                  currentPhoto={avatarPhotoUrl}
                />
              )}
              
              {!showAvatarSelector && avatarPhotoUrl && (
                <div className="text-center">
                  <div className="w-20 h-20 rounded-full overflow-hidden border-4 border-indigo-500 shadow-lg mx-auto mb-2">
                    <img src={avatarPhotoUrl} alt="Avatar" className="w-full h-full object-cover" />
                  </div>
                  <p className="text-xs text-green-600 dark:text-green-400 font-medium">
                    ✓ {isFrench ? 'Avatar activé' : 'Avatar enabled'}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Right Column - Call Interface */}
          <div className="lg:col-span-2 space-y-6">
            {/* Mode Selector */}
            {agent.interaction_mode === 'both' && (
              <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-2 border border-gray-200 dark:border-gray-700">
                <div className="flex gap-2">
                  <button
                    onClick={() => handleModeSwitch('voice')}
                    className={`flex-1 flex items-center justify-center gap-3 px-6 py-4 rounded-xl font-semibold transition-all duration-200 ${
                      selectedMode === 'voice'
                        ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-lg'
                        : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                    }`}
                  >
                    <MicrophoneIcon className="w-5 h-5" />
                    <span>{t.common.status === 'Statut' ? 'Voix' : 'Voice'}</span>
                  </button>
                  <button
                    onClick={() => handleModeSwitch('chat')}
                    className={`flex-1 flex items-center justify-center gap-3 px-6 py-4 rounded-xl font-semibold transition-all duration-200 ${
                      selectedMode === 'chat'
                        ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-lg'
                        : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                    }`}
                  >
                    <ChatBubbleLeftRightIcon className="w-5 h-5" />
                    <span>{t.common.status === 'Statut' ? 'Chat' : 'Chat'}</span>
                  </button>
                </div>
              </div>
            )}

            {/* Video Avatar Display */}
            {avatarEnabled && avatarPhotoUrl && selectedMode === 'voice' && (
              <VideoAvatar
                photoUrl={avatarPhotoUrl}
                isActive={isConnected}
                isSpeaking={isSpeaking}
                className="w-full h-96"
              />
            )}

            {/* Voice Interface */}
            {selectedMode === 'voice' && (
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
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}

