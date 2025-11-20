import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authAPI } from '@/lib/api'
import toast from 'react-hot-toast'
import { MicrophoneIcon } from '@heroicons/react/24/outline'
import { useTranslation } from '@/lib/translations'

export default function RegisterPage() {
  const navigate = useNavigate()
  const t = useTranslation()
  
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
      toast.error(t.register.passwordMismatch)
      return
    }
    
    if (formData.password.length < 8) {
      toast.error(t.register.passwordMinLength)
      return
    }
    
    if (formData.password.length > 72) {
      toast.error(t.register.passwordMaxLength)
      return
    }
    
    setIsLoading(true)
    
    try {
      await authAPI.register({
        email: formData.email,
        password: formData.password,
        full_name: formData.full_name,
      })
      
      toast.success(t.register.success)
      navigate('/login')
    } catch (error: any) {
      console.error('Registration error:', error)
      toast.error(error.response?.data?.detail || t.register.error)
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
            {t.register.title}
          </h2>
          
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                {t.register.fullName}
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
                {t.auth.email}
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
                {t.auth.password}
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
              <p className="text-xs text-gray-500 mt-1">{t.register.passwordHint}</p>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                {t.register.confirmPassword}
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
              {isLoading ? t.register.creating : t.register.createAccount}
            </button>
          </form>
          
          <div className="mt-6 text-center">
            <p className="text-gray-600 dark:text-gray-400">
              {t.register.hasAccount}{' '}
              <Link to="/login" className="text-primary-600 hover:text-primary-700 font-medium">
                {t.register.loginHere}
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

