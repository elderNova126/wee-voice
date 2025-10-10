import { ReactNode } from 'react'
import { ArrowUpIcon, ArrowDownIcon } from '@heroicons/react/24/solid'

interface StatCardProps {
  title: string
  value: string | number
  icon: ReactNode
  trend?: {
    value: number
    isPositive: boolean
  }
  subtitle?: string
  iconColor?: string
  loading?: boolean
}

export const StatCard = ({ 
  title, 
  value, 
  icon, 
  trend, 
  subtitle,
  iconColor = 'from-indigo-500 to-purple-600',
  loading = false 
}: StatCardProps) => {
  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-24 animate-pulse"></div>
          <div className="w-10 h-10 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse"></div>
        </div>
        <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-32 mb-2 animate-pulse"></div>
        <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-20 animate-pulse"></div>
      </div>
    )
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 hover:shadow-md transition-shadow duration-200">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-gray-600 dark:text-gray-400">
          {title}
        </h3>
        <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${iconColor} flex items-center justify-center text-white shadow-sm`}>
          {icon}
        </div>
      </div>
      
      <div className="flex items-baseline justify-between">
        <p className="text-3xl font-bold text-gray-900 dark:text-white">
          {value}
        </p>
        
        {trend && (
          <div className={`flex items-center gap-1 text-sm font-medium ${
            trend.isPositive ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
          }`}>
            {trend.isPositive ? (
              <ArrowUpIcon className="w-4 h-4" />
            ) : (
              <ArrowDownIcon className="w-4 h-4" />
            )}
            {Math.abs(trend.value)}%
          </div>
        )}
      </div>
      
      {subtitle && (
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
          {subtitle}
        </p>
      )}
    </div>
  )
}

