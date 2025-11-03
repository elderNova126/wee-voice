import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authAPI } from '@/lib/api'
import toast from 'react-hot-toast'
import { MicrophoneIcon } from '@heroicons/react/24/outline'

export default function RegisterPage() {
  const navigate = useNavigate()
  
  const [formData, setFormData] = useState({
    full_name: '',
    email: '',
    password: '',
    confirmPassword: '',
  })
  const [isLoading, setIsLoading] = useState(false)
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (formData.password !== formData.confirmPassword) {
      toast.error('Les mots de passe ne correspondent pas')
      return
    }
    
    if (formData.password.length < 8) {
      toast.error('Le mot de passe doit contenir au moins 8 caractères')
      return
    }
    
    if (formData.password.length > 72) {
      toast.error('Le mot de passe ne peut pas dépasser 72 caractères')
      return
    }
    
    setIsLoading(true)
    
    try {
      await authAPI.register({
        email: formData.email,
        password: formData.password,
        full_name: formData.full_name,
      })
      
      toast.success('Compte créé avec succès! Veuillez attendre l\'approbation d\'un administrateur avant de vous connecter.')
      navigate('/login')
    } catch (error: any) {
      console.error('Registration error:', error)
      toast.error(error.response?.data?.detail || 'Erreur lors de la création du compte')
    } finally {
      setIsLoading(false)
    }
  }
  
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-purple-50 dark:from-gray-900 dark:to-gray-800 flex items-center justify-center px-6">
      <div className="max-w-md w-full">
        {/* Logo */}
        <div className="text-center mb-8">
          <Link to="/" className="inline-flex items-center space-x-2">
            <MicrophoneIcon className="w-10 h-10 text-primary-600" />
            <span className="text-3xl font-bold text-gray-900 dark:text-white">VoiceAgent</span>
          </Link>
        </div>
        
        {/* Form */}
        <div className="card">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
            Créer un compte
          </h2>
          
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Nom complet
              </label>
              <input
                type="text"
                required
                className="input"
                value={formData.full_name}
                onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Email
              </label>
              <input
                type="email"
                required
                className="input"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Mot de passe
              </label>
              <input
                type="password"
                required
                minLength={8}
                maxLength={72}
                className="input"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              />
              <p className="text-xs text-gray-500 mt-1">8-72 caractères</p>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Confirmer le mot de passe
              </label>
              <input
                type="password"
                required
                minLength={8}
                maxLength={72}
                className="input"
                value={formData.confirmPassword}
                onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
              />
            </div>
            
            <button
              type="submit"
              disabled={isLoading}
              className="btn-primary w-full"
            >
              {isLoading ? 'Création...' : 'Créer mon compte'}
            </button>
          </form>
          
          <div className="mt-6 text-center">
            <p className="text-gray-600 dark:text-gray-400">
              Déjà un compte ?{' '}
              <Link to="/login" className="text-primary-600 hover:text-primary-700 font-medium">
                Se connecter
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

