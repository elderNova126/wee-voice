import { useState, useRef } from 'react'
import { PhotoIcon, CheckCircleIcon, XMarkIcon } from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { useTranslation } from '@/lib/translations'

interface AvatarPhotoSelectorProps {
  onPhotoSelected: (photoUrl: string, photoType: 'upload' | 'sample') => void
  currentPhoto?: string | null
  className?: string
}

const SAMPLE_AVATARS = [
  {
    id: 'avatar1',
    url: 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=400&h=400&fit=crop',
    name: 'Professional Woman'
  },
  {
    id: 'avatar2',
    url: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&h=400&fit=crop',
    name: 'Professional Man'
  },
  {
    id: 'avatar3',
    url: 'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=400&h=400&fit=crop',
    name: 'Business Woman'
  },
  {
    id: 'avatar4',
    url: 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=400&h=400&fit=crop',
    name: 'Business Man'
  },
  {
    id: 'avatar5',
    url: 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=400&h=400&fit=crop',
    name: 'Young Professional'
  },
  {
    id: 'avatar6',
    url: 'https://images.unsplash.com/photo-1519345182560-3f2917c472ef?w=400&h=400&fit=crop',
    name: 'Friendly Face'
  }
]

export default function AvatarPhotoSelector({ onPhotoSelected, currentPhoto, className = '' }: AvatarPhotoSelectorProps) {
  const t = useTranslation()
  const isFrench = t.common.status === 'Statut'
  const [selectedPhoto, setSelectedPhoto] = useState<string | null>(currentPhoto || null)
  const [uploadedPhoto, setUploadedPhoto] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleSampleSelect = (photoUrl: string) => {
    setSelectedPhoto(photoUrl)
    setUploadedPhoto(null)
    onPhotoSelected(photoUrl, 'sample')
    toast.success(isFrench ? 'Photo sélectionnée !' : 'Photo selected!')
  }

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    // Validate file type
    if (!file.type.startsWith('image/')) {
      toast.error(isFrench ? 'Veuillez sélectionner une image' : 'Please select an image file')
      return
    }

    // Validate file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      toast.error(isFrench ? 'L\'image ne doit pas dépasser 5 Mo' : 'Image must be less than 5MB')
      return
    }

    setIsUploading(true)

    try {
      // Convert to base64 for preview and storage
      const reader = new FileReader()
      reader.onload = (e) => {
        const result = e.target?.result as string
        setUploadedPhoto(result)
        setSelectedPhoto(result)
        onPhotoSelected(result, 'upload')
        toast.success(isFrench ? 'Photo téléchargée avec succès !' : 'Photo uploaded successfully!')
      }
      reader.onerror = () => {
        toast.error(isFrench ? 'Erreur lors du téléchargement' : 'Error uploading photo')
      }
      reader.readAsDataURL(file)
    } catch (error) {
      console.error('Error uploading photo:', error)
      toast.error(isFrench ? 'Erreur lors du téléchargement' : 'Error uploading photo')
    } finally {
      setIsUploading(false)
    }
  }

  const clearSelection = () => {
    setSelectedPhoto(null)
    setUploadedPhoto(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  return (
    <div className={`${className}`}>
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2 flex items-center gap-2">
          <PhotoIcon className="w-6 h-6 text-indigo-600" />
          {isFrench ? 'Sélectionnez votre avatar vidéo' : 'Select Your Video Avatar'}
        </h3>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          {isFrench 
            ? 'Choisissez une photo qui sera animée pendant l\'appel. Vous pouvez utiliser votre propre photo ou choisir parmi nos exemples.'
            : 'Choose a photo that will be animated during the call. You can use your own photo or select from our samples.'}
        </p>
      </div>

      {/* Upload Section */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
          {isFrench ? 'Télécharger votre photo' : 'Upload Your Photo'}
        </label>
        <div className="flex items-center gap-4">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handleFileUpload}
            className="hidden"
            id="avatar-upload"
          />
          <label
            htmlFor="avatar-upload"
            className={`flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-semibold rounded-xl shadow-lg hover:shadow-xl transition-all duration-200 cursor-pointer ${
              isUploading ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            <PhotoIcon className="w-5 h-5" />
            {isUploading 
              ? (isFrench ? 'Téléchargement...' : 'Uploading...')
              : (isFrench ? 'Télécharger une photo' : 'Upload Photo')}
          </label>
          
          {uploadedPhoto && (
            <div className="flex items-center gap-2">
              <div className="relative w-16 h-16 rounded-lg overflow-hidden border-2 border-green-500 shadow-lg">
                <img src={uploadedPhoto} alt="Uploaded" className="w-full h-full object-cover" />
                <div className="absolute inset-0 bg-green-500 bg-opacity-20 flex items-center justify-center">
                  <CheckCircleIcon className="w-6 h-6 text-green-600" />
                </div>
              </div>
              <button
                onClick={clearSelection}
                className="p-2 rounded-lg bg-red-100 hover:bg-red-200 dark:bg-red-900/30 dark:hover:bg-red-900/50 text-red-600 dark:text-red-400 transition-colors"
                title={isFrench ? 'Supprimer' : 'Remove'}
              >
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>
          )}
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
          {isFrench 
            ? 'Format supporté : JPG, PNG, GIF. Taille max : 5 Mo'
            : 'Supported formats: JPG, PNG, GIF. Max size: 5MB'}
        </p>
      </div>

      {/* Sample Photos Section */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
          {isFrench ? 'Ou choisissez parmi nos exemples' : 'Or Choose from Sample Photos'}
        </label>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          {SAMPLE_AVATARS.map((avatar) => (
            <button
              key={avatar.id}
              onClick={() => handleSampleSelect(avatar.url)}
              className={`relative group aspect-square rounded-xl overflow-hidden border-2 transition-all duration-200 shadow-md hover:shadow-xl ${
                selectedPhoto === avatar.url && !uploadedPhoto
                  ? 'border-indigo-600 ring-2 ring-indigo-600 ring-offset-2 dark:ring-offset-gray-900'
                  : 'border-gray-200 dark:border-gray-700 hover:border-indigo-400'
              }`}
            >
              <img
                src={avatar.url}
                alt={avatar.name}
                className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-300"
              />
              {selectedPhoto === avatar.url && !uploadedPhoto && (
                <div className="absolute inset-0 bg-indigo-600 bg-opacity-30 flex items-center justify-center">
                  <div className="w-10 h-10 rounded-full bg-indigo-600 flex items-center justify-center shadow-lg">
                    <CheckCircleIcon className="w-7 h-7 text-white" />
                  </div>
                </div>
              )}
              <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent p-2 opacity-0 group-hover:opacity-100 transition-opacity">
                <p className="text-white text-xs font-medium text-center">{avatar.name}</p>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Selected Photo Preview */}
      {selectedPhoto && (
        <div className="mt-6 p-4 bg-gradient-to-r from-indigo-50 to-purple-50 dark:from-indigo-900/20 dark:to-purple-900/20 rounded-xl border border-indigo-200 dark:border-indigo-800">
          <div className="flex items-center gap-4">
            <div className="w-20 h-20 rounded-full overflow-hidden border-4 border-white dark:border-gray-800 shadow-lg flex-shrink-0">
              <img src={selectedPhoto} alt="Selected avatar" className="w-full h-full object-cover" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-semibold text-indigo-900 dark:text-indigo-300 mb-1">
                {isFrench ? '✨ Avatar sélectionné' : '✨ Avatar Selected'}
              </p>
              <p className="text-xs text-indigo-700 dark:text-indigo-400">
                {uploadedPhoto 
                  ? (isFrench ? 'Votre photo sera animée pendant l\'appel' : 'Your photo will be animated during the call')
                  : (isFrench ? 'Cette photo sera animée pendant l\'appel' : 'This photo will be animated during the call')}
              </p>
            </div>
            <CheckCircleIcon className="w-8 h-8 text-green-500 flex-shrink-0" />
          </div>
        </div>
      )}

      {!selectedPhoto && (
        <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-xl border border-blue-200 dark:border-blue-800">
          <p className="text-sm text-blue-900 dark:text-blue-300 text-center">
            {isFrench 
              ? '👆 Sélectionnez une photo ci-dessus pour activer l\'avatar vidéo'
              : '👆 Select a photo above to enable video avatar'}
          </p>
        </div>
      )}
    </div>
  )
}

