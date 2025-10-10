import { ReactNode } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import {
  HomeIcon,
  MicrophoneIcon,
  PhoneIcon,
  KeyIcon,
  UserCircleIcon,
  ArrowRightOnRectangleIcon,
  Bars3Icon,
  XMarkIcon,
  CreditCardIcon,
  ChartBarIcon,
  ShieldCheckIcon,
  ChatBubbleLeftRightIcon
} from '@heroicons/react/24/outline'
import { useAuthStore } from '@/store/authStore'
import { useState } from 'react'
import ThemeToggle from '@/components/ThemeToggle'

interface DashboardLayoutProps {
  children: ReactNode
}

const navigation = [
  { name: 'Tableau de bord', href: '/dashboard', icon: HomeIcon },
  { name: 'Agents', href: '/dashboard/agents', icon: MicrophoneIcon },
  { name: 'Appels', href: '/dashboard/calls', icon: PhoneIcon },
  { name: 'Utilisation', href: '/dashboard/usage', icon: ChartBarIcon },
  { name: 'Facturation', href: '/dashboard/billing', icon: CreditCardIcon },
  { name: 'Sécurité', href: '/dashboard/security', icon: ShieldCheckIcon },
  { name: 'Clés API', href: '/dashboard/api-keys', icon: KeyIcon },
  { name: 'Support', href: '/dashboard/support', icon: ChatBubbleLeftRightIcon },
  { name: 'Profil', href: '/dashboard/profile', icon: UserCircleIcon },
]

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors duration-200">
      {/* Mobile sidebar */}
      <div className={`fixed inset-0 z-50 lg:hidden ${sidebarOpen ? '' : 'hidden'}`}>
        <div className="fixed inset-0 bg-black bg-opacity-50 backdrop-blur-sm transition-opacity" onClick={() => setSidebarOpen(false)} />
        <div className="fixed inset-y-0 left-0 flex w-72 flex-col bg-white dark:bg-gray-800 shadow-2xl">
          <div className="flex items-center justify-between px-6 py-5 bg-gradient-to-r from-indigo-600 to-purple-600">
            <Link to="/" className="flex items-center gap-2">
              <MicrophoneIcon className="h-8 w-8 text-white" />
              <span className="text-xl font-bold text-white">VoiceAgent</span>
            </Link>
            <button onClick={() => setSidebarOpen(false)} className="text-white/80 hover:text-white transition-colors">
              <XMarkIcon className="h-6 w-6" />
            </button>
          </div>
          <nav className="flex-1 space-y-1 px-3 py-6 overflow-y-auto">
            {navigation.map((item) => {
              const isActive = location.pathname === item.href
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  onClick={() => setSidebarOpen(false)}
                  className={`
                    flex items-center px-4 py-3 text-sm font-medium rounded-xl transition-all duration-200
                    ${isActive
                      ? 'bg-gradient-to-r from-indigo-500 to-purple-600 text-white shadow-md'
                      : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700/50'
                    }
                  `}
                >
                  <item.icon className="mr-3 h-5 w-5 flex-shrink-0" />
                  <span className="truncate">{item.name}</span>
                </Link>
              )
            })}
          </nav>
          <div className="border-t border-gray-200 dark:border-gray-700 p-4 space-y-3">
            {/* Theme Toggle */}
            <div className="flex justify-center">
              <ThemeToggle />
            </div>
            
            {/* User Info Card */}
            <div className="bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-700 dark:to-gray-800 rounded-xl p-3">
              <div className="flex items-center gap-3">
                <div className="flex-shrink-0">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-semibold text-sm">
                    {user?.full_name?.charAt(0).toUpperCase()}
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-gray-900 dark:text-white truncate">{user?.full_name}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{user?.email}</p>
                </div>
              </div>
            </div>
            
            {/* Logout Button */}
            <button
              onClick={handleLogout}
              className="flex items-center justify-center w-full px-4 py-2.5 text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-xl transition-all duration-200 border border-red-200 dark:border-red-900/30"
            >
              <ArrowRightOnRectangleIcon className="mr-2 h-5 w-5" />
              Déconnexion
            </button>
          </div>
        </div>
      </div>

      {/* Desktop sidebar */}
      <div className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-72 lg:flex-col">
        <div className="flex flex-col flex-grow bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 shadow-sm">
          <div className="flex items-center px-6 py-5 bg-gradient-to-r from-indigo-600 to-purple-600">
            <Link to="/" className="flex items-center gap-2">
              <MicrophoneIcon className="h-8 w-8 text-white" />
              <span className="text-xl font-bold text-white">VoiceAgent</span>
            </Link>
          </div>
          <nav className="flex-1 space-y-1 px-3 py-6 overflow-y-auto">
            {navigation.map((item) => {
              const isActive = location.pathname === item.href
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={`
                    flex items-center px-4 py-3 text-sm font-medium rounded-xl transition-all duration-200
                    ${isActive
                      ? 'bg-gradient-to-r from-indigo-500 to-purple-600 text-white shadow-md'
                      : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700/50'
                    }
                  `}
                >
                  <item.icon className="mr-3 h-5 w-5 flex-shrink-0" />
                  <span className="truncate">{item.name}</span>
                </Link>
              )
            })}
          </nav>
          <div className="border-t border-gray-200 dark:border-gray-700 p-4 space-y-3">
            {/* Theme Toggle */}
            <div className="flex justify-center">
              <ThemeToggle />
            </div>
            
            {/* User Info Card */}
            <div className="bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-700 dark:to-gray-800 rounded-xl p-3">
              <div className="flex items-center gap-3">
                <div className="flex-shrink-0">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-semibold text-sm">
                    {user?.full_name?.charAt(0).toUpperCase()}
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-gray-900 dark:text-white truncate">{user?.full_name}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{user?.email}</p>
                </div>
              </div>
            </div>
            
            {/* Logout Button */}
            <button
              onClick={handleLogout}
              className="flex items-center justify-center w-full px-4 py-2.5 text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-xl transition-all duration-200 border border-red-200 dark:border-red-900/30"
            >
              <ArrowRightOnRectangleIcon className="mr-2 h-5 w-5" />
              Déconnexion
            </button>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="lg:pl-72">
        {/* Top bar for mobile */}
        <div className="sticky top-0 z-40 flex h-16 shrink-0 items-center gap-x-4 border-b border-gray-200 dark:border-gray-700 bg-white/80 dark:bg-gray-800/80 backdrop-blur-md px-4 shadow-sm lg:hidden">
          <button
            type="button"
            className="-m-2.5 p-2.5 text-gray-700 dark:text-gray-300 lg:hidden hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
            onClick={() => setSidebarOpen(true)}
          >
            <Bars3Icon className="h-6 w-6" />
          </button>
          <Link to="/" className="flex-1 flex items-center gap-2">
            <MicrophoneIcon className="h-6 w-6 text-indigo-600" />
            <span className="text-sm font-bold text-gray-900 dark:text-white">VoiceAgent</span>
          </Link>
        </div>

        {/* Page content */}
        <main className="py-8 px-4 sm:px-6 lg:px-8 min-h-screen">
          {children}
        </main>
      </div>
    </div>
  )
}
