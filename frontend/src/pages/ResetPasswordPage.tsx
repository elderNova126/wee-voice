import { useState } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'
import { authAPI } from '@/lib/api'
import toast from 'react-hot-toast'
import { MicrophoneIcon, KeyIcon, CheckCircleIcon, XCircleIcon } from '@heroicons/react/24/outline'

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token')
  
  const [formData, setFormData] = useState({
    password: '',
    confirmPassword: '',
  })
  const [isLoading, setIsLoading] = useState(false)
  const [success, setSuccess] = useState(false)
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!token) {
      toast.error('Invalid reset link')
      return
    }
    
    if (formData.password !== formData.confirmPassword) {
      toast.error('Passwords do not match')
      return
    }
    
    if (formData.password.length < 8) {
      toast.error('Password must be at least 8 characters long')
      return
    }
    
    if (formData.password.length > 72) {
      toast.error('Password cannot be longer than 72 characters')
      return
    }
    
    setIsLoading(true)
    
    try {
      await authAPI.resetPassword(token, formData.password)
      setSuccess(true)
      toast.success('Password reset successfully!')
      
      // Redirect to login after 2 seconds
      setTimeout(() => {
        navigate('/login?reset=success')
      }, 2000)
    } catch (error: any) {
      console.error('Reset password error:', error)
      toast.error(error.response?.data?.detail || 'Failed to reset password. The link may have expired.')
    } finally {
      setIsLoading(false)
    }
  }
  
  if (!token) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-purple-50 dark:from-gray-900 dark:to-gray-800 flex items-center justify-center px-6">
        <div className="max-w-md w-full">
          <div className="text-center mb-8">
            <Link to="/" className="inline-flex items-center space-x-2">
              <MicrophoneIcon className="w-10 h-10 text-primary-600" />
              <span className="text-3xl font-bold text-gray-900 dark:text-white">VoiceAgent</span>
            </Link>
          </div>
          
          <div className="card text-center">
            <div className="flex justify-center mb-4">
              <XCircleIcon className="w-16 h-16 text-red-500" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
              Invalid Reset Link
            </h2>
            <p className="text-gray-600 dark:text-gray-400 mb-6">
              This password reset link is invalid or has expired.
            </p>
            <Link to="/forgot-password" className="btn-primary inline-block">
              Request New Link
            </Link>
          </div>
        </div>
      </div>
    )
  }
  
  if (success) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-purple-50 dark:from-gray-900 dark:to-gray-800 flex items-center justify-center px-6">
        <div className="max-w-md w-full">
          <div className="text-center mb-8">
            <Link to="/" className="inline-flex items-center space-x-2">
              <MicrophoneIcon className="w-10 h-10 text-primary-600" />
              <span className="text-3xl font-bold text-gray-900 dark:text-white">VoiceAgent</span>
            </Link>
          </div>
          
          <div className="card text-center">
            <div className="flex justify-center mb-4">
              <CheckCircleIcon className="w-16 h-16 text-green-500" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
              Password Reset Successfully!
            </h2>
            <p className="text-gray-600 dark:text-gray-400 mb-4">
              Your password has been changed. You can now log in with your new password.
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
              Redirecting to login page...
            </p>
            <Link to="/login" className="btn-primary inline-block">
              Go to Login
            </Link>
          </div>
        </div>
      </div>
    )
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
        
        {/* Form Card */}
        <div className="card">
          <div className="text-center mb-6">
            <div className="inline-flex items-center justify-center w-12 h-12 bg-primary-100 dark:bg-primary-900/30 rounded-full mb-4">
              <KeyIcon className="w-6 h-6 text-primary-600 dark:text-primary-400" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
              Reset Your Password
            </h2>
            <p className="text-gray-600 dark:text-gray-400 mt-2">
              Enter your new password below.
            </p>
          </div>
          
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                New Password
              </label>
              <input
                type="password"
                required
                minLength={8}
                maxLength={72}
                className="input"
                placeholder="Enter new password"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                disabled={isLoading}
              />
              <p className="text-xs text-gray-500 mt-1">Minimum 8 characters, maximum 72 characters</p>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Confirm New Password
              </label>
              <input
                type="password"
                required
                minLength={8}
                maxLength={72}
                className="input"
                placeholder="Confirm new password"
                value={formData.confirmPassword}
                onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                disabled={isLoading}
              />
            </div>
            
            {/* Password strength tips */}
            <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3">
              <p className="text-xs text-blue-800 dark:text-blue-300 font-medium mb-1">
                🔒 Password Tips:
              </p>
              <ul className="text-xs text-blue-800 dark:text-blue-300 space-y-1 list-disc list-inside">
                <li>Use a mix of letters, numbers, and symbols</li>
                <li>Avoid common words or patterns</li>
                <li>Don't reuse passwords from other sites</li>
              </ul>
            </div>
            
            <button
              type="submit"
              disabled={isLoading}
              className="btn-primary w-full"
            >
              {isLoading ? 'Resetting Password...' : 'Reset Password'}
            </button>
          </form>
          
          <div className="mt-6 text-center">
            <Link 
              to="/login" 
              className="text-sm text-gray-600 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400"
            >
              ← Back to Login
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}

