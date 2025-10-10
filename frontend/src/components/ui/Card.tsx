import { ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  className?: string
  hover?: boolean
  padding?: 'none' | 'sm' | 'md' | 'lg'
}

export const Card = ({ children, className = '', hover = false, padding = 'lg' }: CardProps) => {
  const paddingClasses = {
    none: '',
    sm: 'p-4',
    md: 'p-6',
    lg: 'p-8'
  }

  return (
    <div 
      className={`
        bg-white dark:bg-gray-800 
        rounded-xl 
        shadow-sm 
        border border-gray-200 dark:border-gray-700
        ${hover ? 'hover:shadow-md transition-shadow duration-200' : ''}
        ${paddingClasses[padding]}
        ${className}
      `}
    >
      {children}
    </div>
  )
}

interface CardHeaderProps {
  title: string
  subtitle?: string
  action?: ReactNode
  icon?: ReactNode
}

export const CardHeader = ({ title, subtitle, action, icon }: CardHeaderProps) => {
  return (
    <div className="flex items-start justify-between mb-6">
      <div className="flex items-start gap-3">
        {icon && (
          <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white">
            {icon}
          </div>
        )}
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            {title}
          </h3>
          {subtitle && (
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              {subtitle}
            </p>
          )}
        </div>
      </div>
      {action && <div className="flex-shrink-0">{action}</div>}
    </div>
  )
}

export const CardContent = ({ children, className = '' }: { children: ReactNode; className?: string }) => {
  return <div className={className}>{children}</div>
}

export const CardFooter = ({ children, className = '' }: { children: ReactNode; className?: string }) => {
  return (
    <div className={`mt-6 pt-6 border-t border-gray-200 dark:border-gray-700 ${className}`}>
      {children}
    </div>
  )
}

