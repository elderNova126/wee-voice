import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { authAPI } from '@/lib/api'
import toast from 'react-hot-toast'
import { MicrophoneIcon } from '@heroicons/react/24/outline'
import { useTranslation } from '@/lib/translations'

export default function LoginPage() {
  const navigate = useNavigate()
  const login = useAuthStore(state => state.login)
  const t = useTranslation()
  
  const [formData, setFormData] = useState({
    email: '',
    password: '',
  })
  const [isLoading, setIsLoading] = useState(false)
  const [showResendVerification, setShowResendVerification] = useState(false)
  const [resendingEmail, setResendingEmail] = useState(false)
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    
    try {
      const response = await authAPI.login(formData.email, formData.password)
      const { access_token } = response.data
      
      // Store token first so axios interceptor can use it
      login(access_token, { id: 0, email: '', full_name: '', subscription_tier: '' })
      
      // Then get user info (will use stored token)
      const userResponse = await authAPI.getMe()
      login(access_token, userResponse.data)
      
      toast.success(t.auth.loginSuccess)
      navigate('/dashboard')
    } catch (error: any) {
      console.error('Login error:', error)
      const errorMsg = error.response?.data?.detail || t.auth.loginError
      const errorCode = error.response?.headers?.['x-error-code'] || error.response?.data?.code
      
      // Check if email is not verified
      if (errorCode === 'EMAIL_NOT_VERIFIED' || errorMsg === 'EMAIL_NOT_VERIFIED' || errorMsg.toLowerCase().includes('not verified') || errorMsg.toLowerCase().includes('verify')) {
        setShowResendVerification(true)
        toast.error(
          'Please verify your email address before logging in.',
          { duration: 5000 }
        )
      } else if (errorMsg.toLowerCase().includes('not approved')) {
        toast.error(
          'Your account is pending admin approval. You will receive an email once approved.',
          { duration: 5000 }
        )
      } else {
        toast.error(errorMsg)
        setShowResendVerification(false)
      }
    } finally {
      setIsLoading(false)
    }
  }
  
  const handleResendVerification = async () => {
    if (!formData.email) {
      toast.error('Please enter your email address')
      return
    }
    
    setResendingEmail(true)
    try {
      await authAPI.requestVerification(formData.email)
      toast.success('Verification email sent! Check your inbox.')
      setShowResendVerification(false)
    } catch (error: any) {
      console.error('Resend verification error:', error)
      // Don't show error - always show success to prevent email enumeration
      toast.success('If an account exists, a verification email has been sent.')
      setShowResendVerification(false)
    } finally {
      setResendingEmail(false)
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
            {t.auth.login}
          </h2>
          
          <form onSubmit={handleSubmit} className="space-y-4">
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
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  {t.auth.password}
                </label>
                <Link 
                  to="/forgot-password" 
                  className="text-sm text-primary-600 hover:text-primary-700 font-medium"
                >
                  Forgot password?
                </Link>
              </div>
              <input
                type="password"
                required
                className="input"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              />
            </div>
            
            <button
              type="submit"
              disabled={isLoading}
              className="btn-primary w-full"
            >
              {isLoading ? t.auth.connecting : t.auth.connect}
            </button>
          </form>
          
          {/* Resend Verification Email */}
          {showResendVerification && (
            <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
              <p className="text-sm text-blue-800 dark:text-blue-300 mb-3">
                <strong>Email not verified.</strong> Click below to resend the verification email.
              </p>
              <button
                type="button"
                onClick={handleResendVerification}
                disabled={resendingEmail || !formData.email}
                className="btn-secondary w-full text-sm"
              >
                {resendingEmail ? 'Sending...' : 'Resend Verification Email'}
              </button>
            </div>
          )}
          
          <div className="mt-6 text-center">
            <p className="text-gray-600 dark:text-gray-400">
              {t.auth.noAccount}{' '}
              <Link to="/register" className="text-primary-600 hover:text-primary-700 font-medium">
                {t.auth.createAccount}
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

