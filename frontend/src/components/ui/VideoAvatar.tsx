import { useState, useEffect, useRef } from 'react'
import { VideoCameraIcon, SpeakerWaveIcon, SpeakerXMarkIcon } from '@heroicons/react/24/outline'
import { useTranslation } from '@/lib/translations'

interface VideoAvatarProps {
  photoUrl: string | null
  isActive: boolean
  isSpeaking?: boolean
  className?: string
}

export default function VideoAvatar({ photoUrl, isActive, isSpeaking = false, className = '' }: VideoAvatarProps) {
  const t = useTranslation()
  const isFrench = t.common.status === 'Statut'
  const [isLoaded, setIsLoaded] = useState(false)
  const [isMuted, setIsMuted] = useState(false)
  const videoRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (photoUrl) {
      // Simulate loading the avatar
      const timer = setTimeout(() => setIsLoaded(true), 500)
      return () => clearTimeout(timer)
    } else {
      setIsLoaded(false)
    }
  }, [photoUrl])

  if (!photoUrl) {
    return (
      <div className={`${className} flex items-center justify-center bg-gray-100 dark:bg-gray-800 rounded-2xl border-2 border-dashed border-gray-300 dark:border-gray-700`}>
        <div className="text-center p-8">
          <VideoCameraIcon className="w-16 h-16 text-gray-400 mx-auto mb-3" />
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {isFrench ? 'Aucun avatar sélectionné' : 'No avatar selected'}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className={`${className} relative overflow-hidden rounded-2xl bg-black shadow-2xl`}>
      {/* Video/Image Display */}
      <div ref={videoRef} className="relative w-full h-full">
        <img
          src={photoUrl}
          alt="Avatar"
          className={`w-full h-full object-cover transition-all duration-300 ${
            isActive ? '' : 'grayscale'
          }`}
        />
        
        {/* Speaking Animation Overlay */}
        {isActive && isSpeaking && (
          <>
            {/* Animated border when speaking */}
            <div className="absolute inset-0 border-4 border-green-500 rounded-2xl animate-pulse"></div>
            
            {/* Sound waves effect */}
            <div className="absolute bottom-4 left-4 flex items-center gap-1">
              <div className="w-1 bg-green-500 rounded-full animate-sound-wave-1" style={{ height: '12px' }}></div>
              <div className="w-1 bg-green-500 rounded-full animate-sound-wave-2" style={{ height: '20px' }}></div>
              <div className="w-1 bg-green-500 rounded-full animate-sound-wave-3" style={{ height: '16px' }}></div>
              <div className="w-1 bg-green-500 rounded-full animate-sound-wave-2" style={{ height: '24px' }}></div>
              <div className="w-1 bg-green-500 rounded-full animate-sound-wave-1" style={{ height: '14px' }}></div>
            </div>
          </>
        )}

        {/* Active Indicator */}
        {isActive && (
          <div className="absolute top-4 left-4 flex items-center gap-2 bg-green-500 text-white px-3 py-1.5 rounded-full text-xs font-semibold shadow-lg">
            <div className="w-2 h-2 bg-white rounded-full animate-pulse"></div>
            {isFrench ? 'En direct' : 'Live'}
          </div>
        )}

        {/* Mute Button */}
        {isActive && (
          <button
            onClick={() => setIsMuted(!isMuted)}
            className="absolute top-4 right-4 w-10 h-10 rounded-full bg-black/50 hover:bg-black/70 backdrop-blur-sm flex items-center justify-center transition-all duration-200 shadow-lg"
            title={isMuted ? (isFrench ? 'Activer le son' : 'Unmute') : (isFrench ? 'Couper le son' : 'Mute')}
          >
            {isMuted ? (
              <SpeakerXMarkIcon className="w-5 h-5 text-white" />
            ) : (
              <SpeakerWaveIcon className="w-5 h-5 text-white" />
            )}
          </button>
        )}

        {/* Inactive Overlay */}
        {!isActive && (
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center">
            <div className="text-center text-white">
              <VideoCameraIcon className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p className="text-sm font-medium">
                {isFrench ? 'Avatar en pause' : 'Avatar Paused'}
              </p>
            </div>
          </div>
        )}

        {/* Loading State */}
        {!isLoaded && (
          <div className="absolute inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center">
            <div className="text-center text-white">
              <div className="w-12 h-12 border-4 border-white/30 border-t-white rounded-full animate-spin mx-auto mb-3"></div>
              <p className="text-sm font-medium">
                {isFrench ? 'Chargement de l\'avatar...' : 'Loading avatar...'}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* AI-Generated Label */}
      <div className="absolute bottom-4 right-4 bg-purple-600/90 backdrop-blur-sm text-white px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1 shadow-lg">
        <span>✨</span>
        {isFrench ? 'IA' : 'AI'}
      </div>

      <style>{`
        @keyframes sound-wave-1 {
          0%, 100% { height: 12px; }
          50% { height: 24px; }
        }
        @keyframes sound-wave-2 {
          0%, 100% { height: 20px; }
          50% { height: 32px; }
        }
        @keyframes sound-wave-3 {
          0%, 100% { height: 16px; }
          50% { height: 28px; }
        }
        .animate-sound-wave-1 {
          animation: sound-wave-1 0.8s ease-in-out infinite;
        }
        .animate-sound-wave-2 {
          animation: sound-wave-2 0.8s ease-in-out infinite 0.1s;
        }
        .animate-sound-wave-3 {
          animation: sound-wave-3 0.8s ease-in-out infinite 0.2s;
        }
      `}</style>
    </div>
  )
}

