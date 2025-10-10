import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { MicrophoneIcon, StopIcon, ArrowLeftIcon } from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { VoiceWebSocket, agentsAPI } from '@/lib/api'

interface Agent {
  id: number
  name: string
  description: string
  language: string
}

export default function DemoPage() {
  const [isConnected, setIsConnected] = useState(false)
  const [isConnecting, setIsConnecting] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [transcript, setTranscript] = useState<{ role: string; text: string }[]>([])
  const [agents, setAgents] = useState<Agent[]>([])
  const [selectedLanguage, setSelectedLanguage] = useState<string>('fr-FR')
  const [agentId, setAgentId] = useState<number | null>(null)
  
  const wsRef = useRef<VoiceWebSocket | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const audioPlayerRef = useRef<AudioContext | null>(null)
  const isRecordingRef = useRef<boolean>(false) // Use ref to avoid closure issues
  const audioQueueRef = useRef<Float32Array[]>([]) // Queue for smooth audio playback
  const isPlayingRef = useRef<boolean>(false) // Track if audio is currently playing
  const nextPlayTimeRef = useRef<number>(0) // Track next scheduled play time for seamless playback
  
  useEffect(() => {
    // Load demo agents
    agentsAPI.getDemoAgent()
      .then(response => {
        const agentsList = response.data.agents || []
        setAgents(agentsList)
        
        if (agentsList.length === 0) {
          console.warn('No demo agents found')
          toast.error('No demo agents available')
          return
        }
        
        // Select French agent by default
        const frenchAgent = agentsList.find((a: Agent) => a.language.startsWith('fr'))
        if (frenchAgent) {
          setAgentId(frenchAgent.id)
          setSelectedLanguage(frenchAgent.language)
        } else if (agentsList.length > 0) {
          setAgentId(agentsList[0].id)
          setSelectedLanguage(agentsList[0].language)
        }
      })
      .catch(error => {
        console.error('Failed to load demo agents:', error)
        toast.error('Unable to load demo agents')
      })
    
    return () => {
      disconnect()
    }
  }, [])
  
  // Update agent when language changes
  useEffect(() => {
    const agent = agents.find(a => a.language === selectedLanguage)
    if (agent) {
      setAgentId(agent.id)
      // Clear transcript when switching languages
      setTranscript([])
    }
  }, [selectedLanguage, agents])
  
  // Function to play audio queue continuously with precise scheduling (no gaps)
  const playAudioQueue = () => {
    if (!audioPlayerRef.current || audioQueueRef.current.length === 0) {
      return
    }
    
    const audioContext = audioPlayerRef.current
    const currentTime = audioContext.currentTime
    
    // Initialize next play time if not set or if it's in the past
    if (nextPlayTimeRef.current < currentTime) {
      nextPlayTimeRef.current = currentTime
    }
    
    // Schedule all queued chunks
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
  
  const connect = async () => {
    if (!agentId) {
      console.error('No agent ID available')
      toast.error('Agent non disponible')
      return
    }
    
    setIsConnecting(true)
    
    try {
      // Request microphone permission
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      mediaStreamRef.current = stream
      
      // Clear audio queue and reset timing
      audioQueueRef.current = []
      isPlayingRef.current = false
      nextPlayTimeRef.current = 0
      
      // Set up audio context for recording
      audioContextRef.current = new AudioContext({ sampleRate: 16000 })
      const source = audioContextRef.current.createMediaStreamSource(stream)
      
      // Create processor for audio chunks
      processorRef.current = audioContextRef.current.createScriptProcessor(2048, 1, 1)
      
      processorRef.current.onaudioprocess = (e) => {
        if (isRecordingRef.current && wsRef.current) {
          const audioData = e.inputBuffer.getChannelData(0)
          const int16Array = new Int16Array(audioData.length)
          
          // Convert float32 to int16
          for (let i = 0; i < audioData.length; i++) {
            const s = Math.max(-1, Math.min(1, audioData[i]))
            int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF
          }
          
          wsRef.current.sendAudio(int16Array.buffer)
        }
      }
      
      source.connect(processorRef.current)
      processorRef.current.connect(audioContextRef.current.destination)
      
      // Set up audio player for responses
      audioPlayerRef.current = new AudioContext({ sampleRate: 24000 })
      
      // Connect WebSocket
      wsRef.current = new VoiceWebSocket(agentId)
      wsRef.current.connect(
        (event) => {
          if (event.data instanceof Blob) {
            // Audio response - Raw PCM data from Gemini (24kHz, 16-bit, mono)
            event.data.arrayBuffer().then(buffer => {
              if (audioPlayerRef.current) {
                try {
                  // Convert Int16 PCM to Float32
                  const int16Data = new Int16Array(buffer)
                  const float32Data = new Float32Array(int16Data.length)
                  
                  for (let i = 0; i < int16Data.length; i++) {
                    float32Data[i] = int16Data[i] / 32768.0
                  }
                  
                  // Add to queue and schedule immediately
                  audioQueueRef.current.push(float32Data)
                  playAudioQueue()
                } catch (error) {
                  console.error('Error processing audio:', error)
                }
              }
            }).catch(error => {
              console.error('Error converting audio buffer:', error)
            })
          } else if (typeof event.data === 'string') {
            const data = JSON.parse(event.data)
            
            if (data.type === 'session_started') {
              isRecordingRef.current = true
              setIsRecording(true)
              setIsConnected(true)
              setIsConnecting(false)
              toast.success('Connexion établie!')
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
          toast.error('Erreur de connexion')
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
      toast.error('Impossible d\'accéder au microphone')
      setIsConnecting(false)
    }
  }
  
  const disconnect = () => {
    isRecordingRef.current = false
    setIsRecording(false)
    
    // Clear audio queue and reset timing
    audioQueueRef.current = []
    isPlayingRef.current = false
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
  
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-5xl mx-auto px-6 py-12">
        {/* Header */}
        <div className="mb-10">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 mb-6 font-medium transition-colors"
          >
            <ArrowLeftIcon className="w-5 h-5" />
            {selectedLanguage.startsWith('fr') ? 'Retour' : 'Back'}
          </Link>
          <h1 className="text-4xl sm:text-5xl font-bold text-gray-900 dark:text-white mb-4">
            {selectedLanguage.startsWith('fr') ? 'Démo Agent Vocal' : 'Voice Agent Demo'}
          </h1>
          <p className="text-xl text-gray-600 dark:text-gray-400 mb-6">
            {selectedLanguage.startsWith('fr') 
              ? 'Testez notre agent vocal intelligent propulsé par Gemini 2.5' 
              : 'Test our intelligent voice agent powered by Gemini 2.5'}
          </p>
          
          {/* Language Selector */}
          {agents.length > 1 && (
            <div className="inline-flex items-center gap-2 bg-white dark:bg-gray-800 rounded-xl p-1.5 shadow-sm border border-gray-200 dark:border-gray-700">
              {agents.map(agent => (
                <button
                  key={agent.id}
                  onClick={() => {
                    if (!isConnected) {
                      setSelectedLanguage(agent.language)
                    } else {
                      toast.error(selectedLanguage.startsWith('fr') 
                        ? 'Déconnectez-vous d\'abord pour changer de langue' 
                        : 'Disconnect first to change language')
                    }
                  }}
                  disabled={isConnected}
                  className={`px-6 py-2.5 rounded-lg font-medium transition-all duration-200 ${
                    agent.language === selectedLanguage
                      ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-md'
                      : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                  } ${isConnected ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  {agent.language.startsWith('fr') ? '🇫🇷 Français' : '🇬🇧 English'}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Main Card */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-8 sm:p-12 mb-8">
          <div className="text-center">
            {!isConnected && !isConnecting ? (
              <div>
                <div className="w-32 h-32 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center mx-auto mb-8 shadow-lg">
                  <MicrophoneIcon className="w-16 h-16 text-white" />
                </div>
                <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-4">
                  {selectedLanguage.startsWith('fr') ? 'Prêt à commencer ?' : 'Ready to start?'}
                </h2>
                <p className="text-lg text-gray-600 dark:text-gray-400 mb-8 max-w-md mx-auto">
                  {selectedLanguage.startsWith('fr')
                    ? 'Cliquez sur le bouton ci-dessous pour démarrer une conversation vocale'
                    : 'Click the button below to start a voice conversation'}
                </p>
                <button
                  onClick={connect}
                  disabled={!agentId}
                  className="inline-flex items-center gap-2 px-8 py-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 disabled:from-gray-400 disabled:to-gray-500 text-white text-lg font-semibold rounded-xl shadow-lg hover:shadow-xl transition-all duration-200 disabled:cursor-not-allowed"
                >
                  <MicrophoneIcon className="w-6 h-6" />
                  {selectedLanguage.startsWith('fr') ? 'Démarrer la Conversation' : 'Start Conversation'}
                </button>
              </div>
            ) : isConnecting ? (
              <div>
                <div className="relative inline-block mb-8">
                  <div className="w-32 h-32 rounded-full bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center animate-pulse shadow-lg">
                    <MicrophoneIcon className="w-16 h-16 text-white" />
                  </div>
                  <div className="absolute inset-0 rounded-full border-4 border-indigo-600 animate-spin" style={{ borderTopColor: 'transparent' }}></div>
                </div>
                <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-4">
                  {selectedLanguage.startsWith('fr') ? 'Connexion en cours...' : 'Connecting...'}
                </h2>
                <p className="text-lg text-gray-600 dark:text-gray-400">
                  {selectedLanguage.startsWith('fr')
                    ? 'Veuillez patienter pendant que nous établissons la connexion'
                    : 'Please wait while we establish the connection'}
                </p>
              </div>
            ) : (
              <div>
                <div className="relative inline-block mb-8">
                  <div className={`w-32 h-32 rounded-full flex items-center justify-center shadow-lg transition-all duration-200 ${
                    isRecording ? 'bg-gradient-to-br from-red-500 to-pink-600 animate-pulse scale-110' : 'bg-gradient-to-br from-indigo-500 to-purple-600'
                  }`}>
                    <MicrophoneIcon className="w-16 h-16 text-white" />
                  </div>
                  {isRecording && (
                    <div className="absolute inset-0">
                      <div className="absolute inset-0 rounded-full border-4 border-red-500 animate-ping"></div>
                    </div>
                  )}
                </div>
                <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-4">
                  {selectedLanguage.startsWith('fr') ? 'En écoute...' : 'Listening...'}
                </h2>
                <p className="text-lg text-gray-600 dark:text-gray-400 mb-8">
                  {selectedLanguage.startsWith('fr')
                    ? 'Parlez naturellement en français'
                    : 'Speak naturally in English'}
                </p>
                <button
                  onClick={disconnect}
                  className="inline-flex items-center gap-2 px-8 py-4 bg-gradient-to-r from-red-600 to-pink-600 hover:from-red-700 hover:to-pink-700 text-white text-lg font-semibold rounded-xl shadow-lg hover:shadow-xl transition-all duration-200"
                >
                  <StopIcon className="w-6 h-6" />
                  {selectedLanguage.startsWith('fr') ? 'Arrêter' : 'Stop'}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Transcript */}
        {transcript.length > 0 && (
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-8 mb-8">
            <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-6 flex items-center gap-2">
              <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-sm">
                📝
              </span>
              {selectedLanguage.startsWith('fr') ? 'Transcription' : 'Transcript'}
            </h3>
            <div className="space-y-4 max-h-96 overflow-y-auto pr-2">
              {transcript.map((item, index) => (
                <div
                  key={index}
                  className={`p-4 rounded-xl ${
                    item.role === 'user'
                      ? 'bg-gradient-to-br from-indigo-50 to-purple-50 dark:from-indigo-900/30 dark:to-purple-900/30 border border-indigo-200 dark:border-indigo-800 ml-8'
                      : 'bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 mr-8'
                  }`}
                >
                  <div className={`text-xs font-bold uppercase tracking-wider mb-2 ${
                    item.role === 'user'
                      ? 'text-indigo-600 dark:text-indigo-400'
                      : 'text-gray-500 dark:text-gray-400'
                  }`}>
                    {item.role === 'user' 
                      ? (selectedLanguage.startsWith('fr') ? '👤 Vous' : '👤 You')
                      : '🤖 Agent'}
                  </div>
                  <div className="text-gray-900 dark:text-white leading-relaxed">
                    {item.text}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Info Box */}
        <div className="bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-2xl border border-blue-200 dark:border-blue-800 p-8">
          <h3 className="text-xl font-bold text-blue-900 dark:text-blue-300 mb-4 flex items-center gap-2">
            <span>💡</span>
            {selectedLanguage.startsWith('fr') ? 'Conseils pour une meilleure expérience' : 'Tips for a better experience'}
          </h3>
          {selectedLanguage.startsWith('fr') ? (
            <ul className="text-gray-700 dark:text-gray-300 space-y-3">
              <li className="flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500 text-white flex items-center justify-center text-xs font-bold">1</span>
                <span>Parlez clairement et naturellement pour une meilleure reconnaissance</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500 text-white flex items-center justify-center text-xs font-bold">2</span>
                <span>Posez des questions en français, l'agent comprend le contexte</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500 text-white flex items-center justify-center text-xs font-bold">3</span>
                <span>L'agent peut vous aider avec diverses tâches et questions</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500 text-white flex items-center justify-center text-xs font-bold">4</span>
                <span>Latence inférieure à 300ms pour une conversation ultra-fluide</span>
              </li>
            </ul>
          ) : (
            <ul className="text-gray-700 dark:text-gray-300 space-y-3">
              <li className="flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500 text-white flex items-center justify-center text-xs font-bold">1</span>
                <span>Speak clearly and naturally for better recognition</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500 text-white flex items-center justify-center text-xs font-bold">2</span>
                <span>Ask questions in English, the agent understands context</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500 text-white flex items-center justify-center text-xs font-bold">3</span>
                <span>The agent can help you with various tasks and questions</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500 text-white flex items-center justify-center text-xs font-bold">4</span>
                <span>Latency under 300ms for ultra-smooth conversation</span>
              </li>
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}

