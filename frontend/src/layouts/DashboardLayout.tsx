import React, { ReactNode } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Menu, Transition } from '@headlessui/react'
import { Fragment, useState } from 'react'
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
  ChatBubbleLeftRightIcon,
  SunIcon,
  MoonIcon,
  ComputerDesktopIcon,
  ChevronUpIcon,
  ChevronDownIcon,
  Cog6ToothIcon,
  PuzzlePieceIcon,
  UserGroupIcon,
  BookOpenIcon,
  ClockIcon,
  DevicePhoneMobileIcon
} from '@heroicons/react/24/outline'
import { useAuthStore } from '@/store/authStore'
import { useThemeStore } from '@/store/themeStore'
import { useLanguageStore } from '@/store/languageStore'
import { useTranslation } from '@/lib/translations'
import LanguageSwitcher from '@/components/LanguageSwitcher'

interface DashboardLayoutProps {
  children: ReactNode
}

// Navigation items structure (names will be translated)
const navigationItems = [
  { key: 'dashboard', href: '/dashboard', icon: HomeIcon },
  { key: 'agents', href: '/dashboard/agents', icon: MicrophoneIcon },
  { key: 'libraries', href: '/dashboard/libraries', icon: BookOpenIcon },
  { key: 'calls', href: '/dashboard/calls', icon: ClockIcon },
  { key: 'integrations', href: '/dashboard/integrations', icon: PuzzlePieceIcon },
  { key: 'phoneNumbers', href: '/dashboard/phone-numbers', icon: DevicePhoneMobileIcon },
  { key: 'callbacks', href: '/dashboard/callbacks', icon: ChatBubbleLeftRightIcon },
  { key: 'apiKeys', href: '/dashboard/api-keys', icon: KeyIcon },
  { key: 'support', href: '/dashboard/support', icon: ChatBubbleLeftRightIcon },
]

const settingsNavigationItems = [
  { key: 'billing', href: '/dashboard/billing', icon: CreditCardIcon },
  { key: 'usage', href: '/dashboard/usage', icon: ChartBarIcon },
  { key: 'security', href: '/dashboard/security', icon: ShieldCheckIcon },
]

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()
  const { theme, setTheme } = useThemeStore()
  const { language, setLanguage } = useLanguageStore()
  const t = useTranslation()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(() => {
    // Auto-expand Settings if user is on a settings page
    return settingsNavigationItems.some(item => location.pathname === item.href)
  })

  // Initialize language on mount
  React.useEffect(() => {
    document.documentElement.lang = language
  }, [language])

  // Get navigation items with translated names
  const navigation = navigationItems.map(item => ({
    ...item,
    name: t.nav[item.key as keyof typeof t.nav] || item.key
  }))

  const settingsNavigation = settingsNavigationItems.map(item => ({
    ...item,
    name: t.nav[item.key as keyof typeof t.nav] || item.key
  }))

  // Admin navigation - only show if user is admin
  const adminNavigation = user?.is_superuser
    ? [
        { name: t.nav.admin || 'Admin', href: '/dashboard/admin', icon: HomeIcon },
      ]
    : []

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const themeOptions = [
    { name: 'Light', value: 'light' as const, icon: SunIcon },
    { name: 'Dark', value: 'dark' as const, icon: MoonIcon },
    { name: 'System', value: 'system' as const, icon: ComputerDesktopIcon },
  ]

  const isSettingsActive = settingsNavigation.some(item => location.pathname === item.href)

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 transition-colors duration-200">
      {/* Mobile sidebar */}
      <div className={`fixed inset-0 z-50 lg:hidden ${sidebarOpen ? '' : 'hidden'}`}>
        <div className="fixed inset-0 bg-black bg-opacity-50 backdrop-blur-sm transition-opacity" onClick={() => setSidebarOpen(false)} />
        <div className="fixed inset-y-0 left-0 flex w-72 flex-col bg-white dark:bg-gray-800 shadow-2xl">
          <div className="flex items-center justify-between px-6 py-5 ">
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
                    group flex items-center px-4 py-3 text-sm font-medium rounded-lg transition-all duration-200 relative
                    ${isActive
                      ? 'bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 shadow-sm'
                      : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700/50'
                    }
                  `}
                >
                  {isActive && (
                    <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-indigo-600 dark:bg-indigo-400 rounded-r-full" />
                  )}
                  <item.icon className={`mr-3 h-5 w-5 flex-shrink-0 ${isActive ? 'text-indigo-600 dark:text-indigo-400' : 'text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300'}`} />
                  <span className="truncate">{item.name}</span>
                </Link>
              )
            })}
            
            {/* Admin Navigation */}
            {adminNavigation.length > 0 && (
              <div className="pt-4 mt-4 border-t border-gray-200 dark:border-gray-700">
                <div className="px-4 mb-2">
                  <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Administration
                  </p>
                </div>
                {adminNavigation.map((item) => {
                  const isActive = location.pathname === item.href
                  return (
                    <Link
                      key={item.name}
                      to={item.href}
                      onClick={() => setSidebarOpen(false)}
                      className={`
                        group flex items-center px-4 py-3 text-sm font-medium rounded-lg transition-all duration-200 relative
                        ${isActive
                          ? 'bg-purple-50 dark:bg-purple-950/50 text-purple-600 dark:text-purple-400 shadow-sm'
                          : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700/50'
                        }
                      `}
                    >
                      {isActive && (
                        <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-purple-600 dark:bg-purple-400 rounded-r-full" />
                      )}
                      <item.icon className={`mr-3 h-5 w-5 flex-shrink-0 ${isActive ? 'text-purple-600 dark:text-purple-400' : 'text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300'}`} />
                      <span className="truncate">{item.name}</span>
                    </Link>
                  )
                })}
              </div>
            )}
            
            {/* Settings Section */}
            <div>
              <button
                onClick={() => setSettingsOpen(!settingsOpen)}
                className={`
                  group flex items-center w-full px-4 py-3 text-sm font-medium rounded-lg transition-all duration-200 relative
                  ${isSettingsActive
                    ? 'bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 shadow-sm'
                    : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700/50'
                  }
                `}
              >
                {isSettingsActive && (
                  <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-indigo-600 dark:bg-indigo-400 rounded-r-full" />
                )}
                <Cog6ToothIcon className={`mr-3 h-5 w-5 flex-shrink-0 ${isSettingsActive ? 'text-indigo-600 dark:text-indigo-400' : 'text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300'}`} />
                <span className="truncate flex-1 text-left">{t.settings.title}</span>
                {settingsOpen ? (
                  <ChevronUpIcon className="h-4 w-4 flex-shrink-0" />
                ) : (
                  <ChevronDownIcon className="h-4 w-4 flex-shrink-0" />
                )}
              </button>
              {settingsOpen && (
                <div className="mt-1 space-y-1 ml-4">
                  {settingsNavigation.map((item) => {
                    const isActive = location.pathname === item.href
                    return (
                      <Link
                        key={item.name}
                        to={item.href}
                        onClick={() => setSidebarOpen(false)}
                        className={`
                          group flex items-center px-4 py-2.5 text-sm font-medium rounded-lg transition-all duration-200 relative
                          ${isActive
                            ? 'bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400'
                            : 'text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700/50'
                          }
                        `}
                      >
                        {isActive && (
                          <div className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-indigo-600 dark:bg-indigo-400 rounded-r-full" />
                        )}
                        <item.icon className={`mr-3 h-4 w-4 flex-shrink-0 ${isActive ? 'text-indigo-600 dark:text-indigo-400' : 'text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300'}`} />
                        <span className="truncate">{item.name}</span>
                      </Link>
                    )
                  })}
                </div>
              )}
            </div>
          </nav>
          <div className="border-t border-gray-200 dark:border-gray-700 p-4 bg-gray-50/50 dark:bg-gray-900/50">
            {/* User Menu */}
            <Menu as="div" className="relative">
              <Menu.Button className="w-full bg-gradient-to-br from-white to-gray-50 dark:from-gray-800 dark:to-gray-700 hover:from-gray-50 hover:to-gray-100 dark:hover:from-gray-700 dark:hover:to-gray-600 border border-gray-200 dark:border-gray-600 rounded-xl p-3 transition-all duration-200 cursor-pointer group shadow-sm">
                <div className="flex items-center gap-3">
                  <div className="flex-shrink-0">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-semibold text-sm">
                      {user?.full_name?.charAt(0).toUpperCase()}
                    </div>
                  </div>
                  <div className="flex-1 min-w-0 text-left">
                    <p className="text-sm font-semibold text-gray-900 dark:text-white truncate">{user?.full_name}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{user?.email}</p>
                  </div>
                  <ChevronUpIcon className="h-5 w-5 text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300 transition-colors" />
                </div>
              </Menu.Button>
              <Transition
                as={Fragment}
                enter="transition ease-out duration-100"
                enterFrom="transform opacity-0 scale-95"
                enterTo="transform opacity-100 scale-100"
                leave="transition ease-in duration-75"
                leaveFrom="transform opacity-100 scale-100"
                leaveTo="transform opacity-0 scale-95"
              >
                <Menu.Items className="absolute bottom-full left-0 right-0 mb-2 origin-bottom bg-gray-50 dark:bg-gray-900 rounded-xl shadow-2xl ring-2 ring-gray-200 dark:ring-gray-700 divide-y divide-gray-200 dark:divide-gray-700 focus:outline-none overflow-hidden border border-gray-200 dark:border-gray-700">
                  {/* Profile */}
                  <div className="p-1">
                    <Menu.Item>
                      {({ active }) => (
                        <Link
                          to="/dashboard/profile"
                          onClick={() => setSidebarOpen(false)}
                          className={`${
                            active ? 'bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400' : 'text-gray-700 dark:text-gray-300'
                          } group flex items-center px-4 py-2.5 text-sm font-medium rounded-lg transition-colors`}
                        >
                          <UserCircleIcon className="mr-3 h-5 w-5" />
                          {t.common.profile}
                        </Link>
                      )}
                    </Menu.Item>
                  </div>
                  {/* Language Switcher */}
                  <div className="p-1">
                    <div className="px-4 py-2.5">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          {t.settings.language}
                        </span>
                      </div>
                      <LanguageSwitcher />
                    </div>
                  </div>
                  {/* Theme Options */}
                  <div className="p-1">
                    {themeOptions.map((option) => (
                      <Menu.Item key={option.value}>
                        {({ active }) => (
                          <button
                            onClick={() => setTheme(option.value)}
                            className={`${
                              active ? 'bg-indigo-50 dark:bg-indigo-900/20' : ''
                            } ${
                              theme === option.value ? 'text-indigo-600 dark:text-indigo-400' : 'text-gray-700 dark:text-gray-300'
                            } group flex items-center w-full px-4 py-2.5 text-sm font-medium rounded-lg transition-colors`}
                          >
                            <option.icon className="mr-3 h-5 w-5" />
                            {option.name}
                            {theme === option.value && (
                              <span className="ml-auto text-indigo-600 dark:text-indigo-400">✓</span>
                            )}
                          </button>
                        )}
                      </Menu.Item>
                    ))}
                  </div>
                  {/* Logout */}
                  <div className="p-1">
                    <Menu.Item>
                      {({ active }) => (
                        <button
                          onClick={handleLogout}
                          className={`${
                            active ? 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400' : 'text-red-600 dark:text-red-400'
                          } group flex items-center w-full px-4 py-2.5 text-sm font-medium rounded-lg transition-colors`}
                        >
                          <ArrowRightOnRectangleIcon className="mr-3 h-5 w-5" />
                          {t.common.logout}
                        </button>
                      )}
                    </Menu.Item>
                  </div>
                </Menu.Items>
              </Transition>
            </Menu>
          </div>
        </div>
      </div>

      {/* Desktop sidebar */}
      <div className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-72 lg:flex-col">
        <div className="flex flex-col flex-grow bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 shadow-sm">
          <div className="flex items-center px-6 py-5 bg-gradient-to-r from-indigo-600 to-purple-400">
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
                    group flex items-center px-4 py-3 text-sm font-medium rounded-lg transition-all duration-200 relative
                    ${isActive
                      ? 'bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 shadow-sm'
                      : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700/50'
                    }
                  `}
                >
                  {isActive && (
                    <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-indigo-600 dark:bg-indigo-400 rounded-r-full" />
                  )}
                  <item.icon className={`mr-3 h-5 w-5 flex-shrink-0 ${isActive ? 'text-indigo-600 dark:text-indigo-400' : 'text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300'}`} />
                  <span className="truncate">{item.name}</span>
                </Link>
              )
            })}
            
            {/* Admin Navigation */}
            {adminNavigation.length > 0 && (
              <div className="pt-4 mt-4 border-t border-gray-200 dark:border-gray-700">
                <div className="px-4 mb-2">
                  <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Administration
                  </p>
                </div>
                {adminNavigation.map((item) => {
                  const isActive = location.pathname === item.href
                  return (
                    <Link
                      key={item.name}
                      to={item.href}
                      className={`
                        group flex items-center px-4 py-3 text-sm font-medium rounded-lg transition-all duration-200 relative
                        ${isActive
                          ? 'bg-purple-50 dark:bg-purple-950/50 text-purple-600 dark:text-purple-400 shadow-sm'
                          : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700/50'
                        }
                      `}
                    >
                      {isActive && (
                        <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-purple-600 dark:bg-purple-400 rounded-r-full" />
                      )}
                      <item.icon className={`mr-3 h-5 w-5 flex-shrink-0 ${isActive ? 'text-purple-600 dark:text-purple-400' : 'text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300'}`} />
                      <span className="truncate">{item.name}</span>
                    </Link>
                  )
                })}
              </div>
            )}
            
            {/* Settings Section */}
            <div>
              <button
                onClick={() => setSettingsOpen(!settingsOpen)}
                className={`
                  group flex items-center w-full px-4 py-3 text-sm font-medium rounded-lg transition-all duration-200 relative
                  ${isSettingsActive
                    ? 'bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 shadow-sm'
                    : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700/50'
                  }
                `}
              >
                {isSettingsActive && (
                  <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-indigo-600 dark:bg-indigo-400 rounded-r-full" />
                )}
                <Cog6ToothIcon className={`mr-3 h-5 w-5 flex-shrink-0 ${isSettingsActive ? 'text-indigo-600 dark:text-indigo-400' : 'text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300'}`} />
                <span className="truncate flex-1 text-left">{t.settings.title}</span>
                {settingsOpen ? (
                  <ChevronUpIcon className="h-4 w-4 flex-shrink-0" />
                ) : (
                  <ChevronDownIcon className="h-4 w-4 flex-shrink-0" />
                )}
              </button>
              {settingsOpen && (
                <div className="mt-1 space-y-1 ml-4">
                  {settingsNavigation.map((item) => {
                    const isActive = location.pathname === item.href
                    return (
                      <Link
                        key={item.name}
                        to={item.href}
                        className={`
                          group flex items-center px-4 py-2.5 text-sm font-medium rounded-lg transition-all duration-200 relative
                          ${isActive
                            ? 'bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400'
                            : 'text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700/50'
                          }
                        `}
                      >
                        {isActive && (
                          <div className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-indigo-600 dark:bg-indigo-400 rounded-r-full" />
                        )}
                        <item.icon className={`mr-3 h-4 w-4 flex-shrink-0 ${isActive ? 'text-indigo-600 dark:text-indigo-400' : 'text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300'}`} />
                        <span className="truncate">{item.name}</span>
                      </Link>
                    )
                  })}
                </div>
              )}
            </div>
          </nav>
          <div className="border-t border-gray-200 dark:border-gray-700 p-4 bg-gray-50/50 dark:bg-gray-900/50">
            {/* User Menu */}
            <Menu as="div" className="relative">
              <Menu.Button className="w-full bg-gradient-to-br from-white to-gray-50 dark:from-gray-800 dark:to-gray-700 hover:from-gray-50 hover:to-gray-100 dark:hover:from-gray-700 dark:hover:to-gray-600 border border-gray-200 dark:border-gray-600 rounded-xl p-3 transition-all duration-200 cursor-pointer group shadow-sm">
                <div className="flex items-center gap-3">
                  <div className="flex-shrink-0">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-semibold text-sm">
                      {user?.full_name?.charAt(0).toUpperCase()}
                    </div>
                  </div>
                  <div className="flex-1 min-w-0 text-left">
                    <p className="text-sm font-semibold text-gray-900 dark:text-white truncate">{user?.full_name}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{user?.email}</p>
                  </div>
                  <ChevronUpIcon className="h-5 w-5 text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300 transition-colors" />
                </div>
              </Menu.Button>
              <Transition
                as={Fragment}
                enter="transition ease-out duration-100"
                enterFrom="transform opacity-0 scale-95"
                enterTo="transform opacity-100 scale-100"
                leave="transition ease-in duration-75"
                leaveFrom="transform opacity-100 scale-100"
                leaveTo="transform opacity-0 scale-95"
              >
                <Menu.Items className="absolute bottom-full left-0 right-0 mb-2 origin-bottom bg-gray-50 dark:bg-gray-900 rounded-xl shadow-2xl ring-2 ring-gray-200 dark:ring-gray-700 divide-y divide-gray-200 dark:divide-gray-700 focus:outline-none overflow-hidden border border-gray-200 dark:border-gray-700">
                  {/* Profile */}
                  <div className="p-1">
                    <Menu.Item>
                      {({ active }) => (
                        <Link
                          to="/dashboard/profile"
                          className={`${
                            active ? 'bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400' : 'text-gray-700 dark:text-gray-300'
                          } group flex items-center px-4 py-2.5 text-sm font-medium rounded-lg transition-colors`}
                        >
                          <UserCircleIcon className="mr-3 h-5 w-5" />
                          {t.common.profile}
                        </Link>
                      )}
                    </Menu.Item>
                  </div>
                  {/* Language Switcher */}
                  <div className="p-1">
                    <div className="px-4 py-2.5">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          {t.settings.language}
                        </span>
                      </div>
                      <LanguageSwitcher />
                    </div>
                  </div>
                  {/* Theme Options */}
                  <div className="p-1">
                    {themeOptions.map((option) => (
                      <Menu.Item key={option.value}>
                        {({ active }) => (
                          <button
                            onClick={() => setTheme(option.value)}
                            className={`${
                              active ? 'bg-indigo-50 dark:bg-indigo-900/20' : ''
                            } ${
                              theme === option.value ? 'text-indigo-600 dark:text-indigo-400' : 'text-gray-700 dark:text-gray-300'
                            } group flex items-center w-full px-4 py-2.5 text-sm font-medium rounded-lg transition-colors`}
                          >
                            <option.icon className="mr-3 h-5 w-5" />
                            {option.name}
                            {theme === option.value && (
                              <span className="ml-auto text-indigo-600 dark:text-indigo-400">✓</span>
                            )}
                          </button>
                        )}
                      </Menu.Item>
                    ))}
                  </div>
                  {/* Logout */}
                  <div className="p-1">
                    <Menu.Item>
                      {({ active }) => (
                        <button
                          onClick={handleLogout}
                          className={`${
                            active ? 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400' : 'text-red-600 dark:text-red-400'
                          } group flex items-center w-full px-4 py-2.5 text-sm font-medium rounded-lg transition-colors`}
                        >
                          <ArrowRightOnRectangleIcon className="mr-3 h-5 w-5" />
                          {t.common.logout}
                        </button>
                      )}
                    </Menu.Item>
                  </div>
                </Menu.Items>
              </Transition>
            </Menu>
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
        <main className="py-8 px-4 sm:px-6 lg:px-8 min-h-screen bg-white dark:bg-gray-900">
          {children}
        </main>
      </div>
    </div>
  )
}
