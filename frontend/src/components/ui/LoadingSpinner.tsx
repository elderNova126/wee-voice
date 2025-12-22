import { ArrowPathIcon } from '@heroicons/react/24/outline'

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

export default function LoadingSpinner({ size = 'md', className = '' }: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: 'w-12 h-12',
    md: 'w-20 h-20',
    lg: 'w-32 h-32'
  }

  const iconSizes = {
    sm: 'w-6 h-6',
    md: 'w-8 h-8',
    lg: 'w-12 h-12'
  }

  const insetSizes = {
    sm: { outer: 'inset-0', middle: 'inset-1', inner: 'inset-2' },
    md: { outer: 'inset-0', middle: 'inset-2', inner: 'inset-4' },
    lg: { outer: 'inset-0', middle: 'inset-4', inner: 'inset-8' }
  }

  const borderSizes = {
    sm: 'border-2',
    md: 'border-4',
    lg: 'border-4'
  }

  return (
    <div className={`relative ${sizeClasses[size]} ${className}`}>
      {/* Outer rotating circle */}
      <div 
        className={`absolute ${insetSizes[size].outer} ${borderSizes[size]} border-transparent border-t-blue-600 dark:border-t-blue-400 rounded-full animate-spin`} 
        style={{ animationDuration: '1s' }}
      />
      {/* Middle rotating circle (reverse) */}
      <div 
        className={`absolute ${insetSizes[size].middle} ${borderSizes[size]} border-transparent border-r-purple-600 dark:border-r-purple-400 rounded-full animate-spin`} 
        style={{ animationDirection: 'reverse', animationDuration: '1.5s' }}
      />
      {/* Inner rotating circle */}
      <div 
        className={`absolute ${insetSizes[size].inner} ${borderSizes[size]} border-transparent border-b-pink-600 dark:border-b-pink-400 rounded-full animate-spin`} 
        style={{ animationDuration: '2s' }}
      />
      {/* Center icon */}
      <div className={`absolute ${insetSizes[size].outer} flex items-center justify-center`}>
        <ArrowPathIcon className={`${iconSizes[size]} text-blue-600 dark:text-blue-400 animate-spin`} style={{ animationDuration: '0.8s' }} />
      </div>
    </div>
  )
}

