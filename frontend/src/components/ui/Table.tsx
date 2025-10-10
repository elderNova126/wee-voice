import { ReactNode } from 'react'

interface TableProps {
  children: ReactNode
  className?: string
}

export const Table = ({ children, className = '' }: TableProps) => {
  return (
    <div className="overflow-x-auto">
      <table className={`min-w-full divide-y divide-gray-200 dark:divide-gray-700 ${className}`}>
        {children}
      </table>
    </div>
  )
}

export const TableHead = ({ children }: { children: ReactNode }) => {
  return (
    <thead className="bg-gray-50 dark:bg-gray-900">
      {children}
    </thead>
  )
}

export const TableBody = ({ children }: { children: ReactNode }) => {
  return (
    <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
      {children}
    </tbody>
  )
}

export const TableRow = ({ children, onClick, className = '' }: { children: ReactNode; onClick?: () => void; className?: string }) => {
  return (
    <tr 
      onClick={onClick}
      className={`
        ${onClick ? 'cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50' : ''}
        transition-colors duration-150
        ${className}
      `}
    >
      {children}
    </tr>
  )
}

export const TableHeader = ({ children, className = '' }: { children: ReactNode; className?: string }) => {
  return (
    <th 
      className={`
        px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider
        ${className}
      `}
    >
      {children}
    </th>
  )
}

export const TableCell = ({ children, className = '' }: { children: ReactNode; className?: string }) => {
  return (
    <td className={`px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white ${className}`}>
      {children}
    </td>
  )
}

