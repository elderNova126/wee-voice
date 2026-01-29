import { useState } from 'react'
import { Link } from 'react-router-dom'
import { authAPI } from '@/lib/api'
import toast from 'react-hot-toast'
import { EnvelopeIcon, CheckCircleIcon } from '@heroicons/react/24/outline'

export default function ResendVerificationPage() {
  const [email, setEmail] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    
    try {
      await authAPI.requestVerification(email)
      setSubmitted(true)
      toast.success('Verification email sent!')
    } catch (error: any) {
      console.error('Resend verification error:', error)
      // Show success anyway to prevent email enumeration
      setSubmitted(true)
    } finally {
      setIsLoading(false)
    }
  }
  
  if (submitted) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-purple-50 dark:from-gray-900 dark:to-gray-800 flex items-center justify-center px-6">
        <div className="max-w-md w-full">
          {/* Logo */}
          <div className="text-center mb-8">
            <Link to="/" className="inline-flex items-center justify-center">
              <img src="/weevoice_logo.svg" alt="Weevoice" className="h-12 w-auto object-contain" />
            </Link>
          </div>
          
          {/* Success Card */}
          <div className="card text-center">
            <div className="flex justify-center mb-4">
              <CheckCircleIcon className="w-16 h-16 text-green-500" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
              Verification Email Sent!
            </h2>
            <p className="text-gray-600 dark:text-gray-400 mb-4">
              If an account exists with <strong>{email}</strong>, a verification email has been sent.
            </p>
            
            <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4 mb-6">
              <p className="text-sm text-blue-800 dark:text-blue-300 text-left">
                <strong>📧 Next Steps:</strong>
              </p>
              <ul className="text-sm text-blue-800 dark:text-blue-300 text-left mt-2 space-y-1 list-disc list-inside">
                <li>Check your inbox for an email from WeeVoice</li>
                <li>Click the verification link (valid for 24 hours)</li>
                <li>Log in after your account is approved</li>
              </ul>
            </div>
            
            <div className="space-y-3">
              <Link 
                to="/login"
                className="btn-primary w-full block"
              >
                Back to Login
              </Link>
              <button
                onClick={() => setSubmitted(false)}
                className="btn-secondary w-full"
              >
                Send to Different Email
              </button>
            </div>
            
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-4">
              💡 Didn't receive the email? Check your spam folder.
            </p>
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
          <Link to="/" className="inline-flex items-center justify-center">
            <img src="/weevoice_logo.svg" alt="Weevoice" className="h-12 w-auto object-contain" />
          </Link>
        </div>
        
        {/* Form Card */}
        <div className="card">
          <div className="text-center mb-6">
            <div className="inline-flex items-center justify-center w-12 h-12 bg-primary-100 dark:bg-primary-900/30 rounded-full mb-4">
              <EnvelopeIcon className="w-6 h-6 text-primary-600 dark:text-primary-400" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
              Resend Verification Email
            </h2>
            <p className="text-gray-600 dark:text-gray-400 mt-2">
              Enter your email address and we'll send you a new verification link.
            </p>
          </div>
          
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Email Address
              </label>
              <input
                type="email"
                required
                className="input"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={isLoading}
              />
            </div>
            
            <button
              type="submit"
              disabled={isLoading}
              className="btn-primary w-full"
            >
              {isLoading ? 'Sending...' : 'Send Verification Email'}
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
        
        {/* Help text */}
        <div className="mt-6 text-center">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Remember your password?{' '}
            <Link to="/login" className="text-primary-600 hover:text-primary-700 font-medium">
              Log in
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}

