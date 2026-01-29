import { useEffect, useState } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'
import { authAPI } from '@/lib/api'
import { CheckCircleIcon, XCircleIcon } from '@heroicons/react/24/outline'

export default function VerifyEmailPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState('')
  
  useEffect(() => {
    const token = searchParams.get('token')
    
    if (!token) {
      setStatus('error')
      setMessage('Invalid verification link. Please check your email and try again.')
      return
    }
    
    verifyEmail(token)
  }, [searchParams])
  
  const verifyEmail = async (token: string) => {
    try {
      const response = await authAPI.verifyEmail(token)
      setStatus('success')
      setMessage(response.data.message || 'Email verified successfully!')
      
      // Redirect to login after 3 seconds
      setTimeout(() => {
        navigate('/login?verified=true')
      }, 3000)
    } catch (error: any) {
      setStatus('error')
      setMessage(error.response?.data?.detail || 'Verification failed. The link may have expired.')
    }
  }
  
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-purple-50 dark:from-gray-900 dark:to-gray-800 flex items-center justify-center px-6">
      <div className="max-w-md w-full">
        {/* Logo */}
        <div className="text-center mb-8">
          <Link to="/" className="inline-flex items-center justify-center">
            <img src="/weevoice_logo.svg" alt="Weevoice" className="h-12 w-auto object-contain" />
          </Link>
        </div>
        
        {/* Status Card */}
        <div className="card text-center">
          {status === 'loading' && (
            <>
              <div className="flex justify-center mb-4">
                <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-primary-600"></div>
              </div>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                Verifying Your Email
              </h2>
              <p className="text-gray-600 dark:text-gray-400">
                Please wait while we verify your email address...
              </p>
            </>
          )}
          
          {status === 'success' && (
            <>
              <div className="flex justify-center mb-4">
                <CheckCircleIcon className="w-16 h-16 text-green-500" />
              </div>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                Email Verified!
              </h2>
              <p className="text-gray-600 dark:text-gray-400 mb-4">
                {message}
              </p>
              <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4 mb-4">
                <p className="text-sm text-blue-800 dark:text-blue-300">
                  📝 <strong>Next Step:</strong> Your account is pending admin approval. 
                  You'll receive an email once your account is approved.
                </p>
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Redirecting to login page in 3 seconds...
              </p>
              <Link 
                to="/login"
                className="btn-primary inline-block mt-4"
              >
                Go to Login
              </Link>
            </>
          )}
          
          {status === 'error' && (
            <>
              <div className="flex justify-center mb-4">
                <XCircleIcon className="w-16 h-16 text-red-500" />
              </div>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                Verification Failed
              </h2>
              <p className="text-gray-600 dark:text-gray-400 mb-6">
                {message}
              </p>
              
              <div className="space-y-3">
                <Link 
                  to="/resend-verification"
                  className="btn-primary w-full block"
                >
                  Resend Verification Email
                </Link>
                <Link 
                  to="/login"
                  className="btn-secondary w-full block"
                >
                  Back to Login
                </Link>
              </div>
            </>
          )}
        </div>
        
        {/* Help text */}
        <div className="mt-6 text-center">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Need help?{' '}
            <Link to="/support" className="text-primary-600 hover:text-primary-700 font-medium">
              Contact Support
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}

