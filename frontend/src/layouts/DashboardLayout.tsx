import React, { ReactNode } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Menu, Transition } from '@headlessui/react'
import { Fragment, useState } from 'react'
import {
  HomeIcon,
  MicrophoneIcon,
  UserCircleIcon,
  ArrowRightOnRectangleIcon,
  Bars3Icon,
  XMarkIcon,
  ChatBubbleLeftRightIcon,
  SunIcon,
  MoonIcon,
  ComputerDesktopIcon,
  ChevronUpIcon,
  ChevronRightIcon,
  Cog6ToothIcon,
  BookOpenIcon,
  ClockIcon,
  DevicePhoneMobileIcon,
  MagnifyingGlassIcon,
  ShieldCheckIcon,
  ChartBarIcon
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
  { key: 'phoneNumbers', href: '/dashboard/phone-numbers', icon: DevicePhoneMobileIcon },
  { key: 'callbacks', href: '/dashboard/callbacks', icon: ChatBubbleLeftRightIcon },
  { key: 'usage', href: '/dashboard/usage', icon: ChartBarIcon },
  { key: 'support', href: '/dashboard/support', icon: ChatBubbleLeftRightIcon },
]

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()
  const { theme, setTheme } = useThemeStore()
  const { language } = useLanguageStore()
  const t = useTranslation()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    const saved = localStorage.getItem('sidebarCollapsed')
    return saved ? JSON.parse(saved) : false
  })

  // Initialize language on mount
  React.useEffect(() => {
    document.documentElement.lang = language
  }, [language])

  // Save sidebar collapsed state to localStorage
  React.useEffect(() => {
    localStorage.setItem('sidebarCollapsed', JSON.stringify(sidebarCollapsed))
  }, [sidebarCollapsed])

  const toggleSidebar = () => {
    setSidebarCollapsed(!sidebarCollapsed)
  }

  // Build breadcrumb from current path
  const buildBreadcrumb = () => {
    const path = location.pathname
    const segments = path.split('/').filter(Boolean)
    const breadcrumbs: { label: string; path: string }[] = []

    // Always start with Dashboard
    breadcrumbs.push({ label: t.nav.dashboard, path: '/dashboard' })

    if (segments.length === 1 && segments[0] === 'dashboard') {
      return breadcrumbs
    }

    // Map path segments to labels
    const pathMap: Record<string, string> = {
      'agents': t.nav.agents,
      'calls': t.nav.calls,
      'libraries': t.nav.libraries,
      'phone-numbers': t.nav.phoneNumbers,
      'callbacks': t.nav.callbacks,
      'usage': t.nav.usage,
      'support': t.nav.support,
      'settings': t.nav.settings,
      'profile': t.common.profile,
      'admin': t.nav.admin,
    }

    let currentPath = '/dashboard'
    for (let i = 1; i < segments.length; i++) {
      const segment = segments[i]
      currentPath += `/${segment}`

      // Handle special cases
      if (segment === 'new') {
        breadcrumbs.push({ label: t.common.create, path: currentPath })
      } else if (segment === 'edit' && segments[i - 1]) {
        breadcrumbs.push({ label: t.common.edit, path: currentPath })
      } else if (segment === 'documents' && segments[i - 1] === 'agents') {
        breadcrumbs.push({ label: t.common.status === 'Statut' ? 'Documents' : 'Documents', path: currentPath })
      } else if (segment === 'embed' && segments[i - 1] === 'agents') {
        breadcrumbs.push({ label: t.common.status === 'Statut' ? 'Intégration' : 'Embed', path: currentPath })
      } else if (pathMap[segment]) {
        breadcrumbs.push({ label: pathMap[segment], path: currentPath })
      } else if (!isNaN(Number(segment))) {
        // It's an ID, skip it in breadcrumb but keep the path
        continue
      } else {
        // Fallback: capitalize the segment
        breadcrumbs.push({ 
          label: segment.charAt(0).toUpperCase() + segment.slice(1).replace(/-/g, ' '), 
          path: currentPath 
        })
      }
    }

    return breadcrumbs
  }

  const breadcrumbs = buildBreadcrumb()
  const [searchQuery, setSearchQuery] = useState('')
  const [showSearchResults, setShowSearchResults] = useState(false)

  // Get navigation items with translated names
  const navigation = navigationItems.map(item => ({
    ...item,
    name: t.nav[item.key as keyof typeof t.nav] || item.key
  }))

  // Admin navigation - only show if user is admin
  const adminNavigation = user?.is_superuser
    ? [
        { name: t.nav.admin || 'Admin', href: '/dashboard/admin', icon: ShieldCheckIcon },
      ]
    : []

  // Settings navigation
  const settingsNavigation = [
    { name: t.nav.settings, href: '/dashboard/settings', icon: Cog6ToothIcon }
  ]

  // All navigation items for search (including admin and settings)
  const allNavigationItems = [
    ...navigation,
    ...adminNavigation,
    ...settingsNavigation
  ]

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const themeOptions = [
    { name: 'Light', value: 'light' as const, icon: SunIcon },
    { name: 'Dark', value: 'dark' as const, icon: MoonIcon },
    { name: 'System', value: 'system' as const, icon: ComputerDesktopIcon },
  ]

  const isSettingsActive = location.pathname.startsWith('/dashboard/settings')

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 transition-colors duration-200">
      {/* Mobile sidebar */}
      <div className={`fixed inset-0 z-50 lg:hidden ${sidebarOpen ? '' : 'hidden'}`}>
        <div className="fixed inset-0 bg-black bg-opacity-50 backdrop-blur-sm transition-opacity" onClick={() => setSidebarOpen(false)} />
        <div className="fixed inset-y-0 left-0 flex w-72 flex-col bg-white dark:bg-gray-800 shadow-2xl">
          <div className="flex items-center justify-between px-6 py-5 ">
            <Link to="/" className="flex items-center gap-2">
              <img src="/weevoice_logo.svg" alt="Weevoice" className="h-8 w-auto object-contain" />
            </Link>
            <button onClick={() => setSidebarOpen(false)} className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors">
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
            <Link
              to="/dashboard/settings"
              onClick={() => setSidebarOpen(false)}
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
              <span className="truncate flex-1 text-left">{t.nav.settings}</span>
            </Link>
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
      <div className={`hidden lg:fixed lg:inset-y-0 lg:flex lg:flex-col transition-all duration-300 ${sidebarCollapsed ? 'lg:w-20' : 'lg:w-72'}`}>
        <div className="flex flex-col flex-grow bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 shadow-sm">
          <div className={`flex items-center ${sidebarCollapsed ? 'justify-center px-2' : 'justify-between px-6'} py-5 bg-gradient-to-r from-indigo-600 to-purple-400 relative`}>
            <Link to="/" className={`flex items-center gap-2 ${sidebarCollapsed ? 'justify-center' : ''}`}>
              <img src="/weevoice_logo.svg" alt="Weevoice" className={`object-contain invert ${sidebarCollapsed ? 'h-8 w-auto max-w-12' : 'h-8 w-auto max-w-[140px]'}`} />
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
                    group flex items-center ${sidebarCollapsed ? 'justify-center px-2' : 'px-4'} py-3 text-sm font-medium rounded-lg transition-all duration-200 relative
                    ${isActive
                      ? 'bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 shadow-sm'
                      : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700/50'
                    }
                  `}
                  title={sidebarCollapsed ? item.name : undefined}
                >
                  {isActive && !sidebarCollapsed && (
                    <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-indigo-600 dark:bg-indigo-400 rounded-r-full" />
                  )}
                  <item.icon className={`${sidebarCollapsed ? '' : 'mr-3'} h-5 w-5 flex-shrink-0 ${isActive ? 'text-indigo-600 dark:text-indigo-400' : 'text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300'}`} />
                  {!sidebarCollapsed && (
                    <span className="truncate">{item.name}</span>
                  )}
                </Link>
              )
            })}
            
            {/* Admin Navigation */}
            {adminNavigation.length > 0 && (
              <div className="pt-4 mt-4 border-t border-gray-200 dark:border-gray-700">
                {!sidebarCollapsed && (
                  <div className="px-4 mb-2">
                    <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Administration
                    </p>
                  </div>
                )}
                {adminNavigation.map((item) => {
                  const isActive = location.pathname === item.href
                  return (
                    <Link
                      key={item.name}
                      to={item.href}
                      className={`
                        group flex items-center ${sidebarCollapsed ? 'justify-center px-2' : 'px-4'} py-3 text-sm font-medium rounded-lg transition-all duration-200 relative
                        ${isActive
                          ? 'bg-purple-50 dark:bg-purple-950/50 text-purple-600 dark:text-purple-400 shadow-sm'
                          : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700/50'
                        }
                      `}
                      title={sidebarCollapsed ? item.name : undefined}
                    >
                      {isActive && !sidebarCollapsed && (
                        <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-purple-600 dark:bg-purple-400 rounded-r-full" />
                      )}
                      <item.icon className={`${sidebarCollapsed ? '' : 'mr-3'} h-5 w-5 flex-shrink-0 ${isActive ? 'text-purple-600 dark:text-purple-400' : 'text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300'}`} />
                      {!sidebarCollapsed && (
                        <span className="truncate">{item.name}</span>
                      )}
                    </Link>
                  )
                })}
              </div>
            )}
            
            {/* Settings Section */}
            <Link
              to="/dashboard/settings"
              className={`
                group flex items-center w-full ${sidebarCollapsed ? 'justify-center px-2' : 'px-4'} py-3 text-sm font-medium rounded-lg transition-all duration-200 relative
                ${isSettingsActive
                  ? 'bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 shadow-sm'
                  : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700/50'
                }
              `}
              title={sidebarCollapsed ? t.nav.settings : undefined}
            >
              {isSettingsActive && !sidebarCollapsed && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-indigo-600 dark:bg-indigo-400 rounded-r-full" />
              )}
              <Cog6ToothIcon className={`${sidebarCollapsed ? '' : 'mr-3'} h-5 w-5 flex-shrink-0 ${isSettingsActive ? 'text-indigo-600 dark:text-indigo-400' : 'text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300'}`} />
              {!sidebarCollapsed && (
                <span className="truncate flex-1 text-left">{t.nav.settings}</span>
              )}
            </Link>
          </nav>
          <div className="border-t border-gray-200 dark:border-gray-700 p-4 bg-gray-50/50 dark:bg-gray-900/50">
            {/* User Menu */}
            <Menu as="div" className="relative">
              <Menu.Button className={`w-full bg-gradient-to-br from-white to-gray-50 dark:from-gray-800 dark:to-gray-700 hover:from-gray-50 hover:to-gray-100 dark:hover:from-gray-700 dark:hover:to-gray-600 border border-gray-200 dark:border-gray-600 rounded-xl ${sidebarCollapsed ? 'p-2' : 'p-3'} transition-all duration-200 cursor-pointer group shadow-sm`}>
                <div className={`flex items-center ${sidebarCollapsed ? 'justify-center' : 'gap-3'}`}>
                  <div className="flex-shrink-0">
                    <div className={`${sidebarCollapsed ? 'w-8 h-8' : 'w-10 h-10'} rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-semibold text-sm`}>
                      {user?.full_name?.charAt(0).toUpperCase()}
                    </div>
                  </div>
                  {!sidebarCollapsed && (
                    <>
                      <div className="flex-1 min-w-0 text-left">
                        <p className="text-sm font-semibold text-gray-900 dark:text-white truncate">{user?.full_name}</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{user?.email}</p>
                      </div>
                      <ChevronUpIcon className="h-5 w-5 text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300 transition-colors" />
                    </>
                  )}
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
                <Menu.Items className={`absolute bottom-full ${sidebarCollapsed ? 'left-full ml-2 w-72' : 'left-0 right-0'} mb-2 origin-bottom bg-gray-50 dark:bg-gray-900 rounded-xl shadow-2xl ring-2 ring-gray-200 dark:ring-gray-700 divide-y divide-gray-200 dark:divide-gray-700 focus:outline-none overflow-hidden border border-gray-200 dark:border-gray-700`}>
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
      <div className={`transition-all duration-300 ${sidebarCollapsed ? 'lg:pl-20' : 'lg:pl-72'}`}>
        {/* Top bar */}
        <div className="sticky top-0 z-40 flex h-16 shrink-0 items-center gap-x-4 border-b border-gray-200 dark:border-gray-700 bg-white/80 dark:bg-gray-800/80 backdrop-blur-md px-4 shadow-sm">
          {/* Left side: Sidebar toggle + Breadcrumb */}
          <div className="flex items-center gap-4 flex-1 min-w-0">
            {/* Sidebar toggle button (desktop) */}
            <button
              type="button"
              className="hidden lg:flex -m-2.5 p-2.5 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              onClick={toggleSidebar}
              aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              <Bars3Icon className="h-6 w-6" />
            </button>
            
            {/* Mobile sidebar toggle */}
            <button
              type="button"
              className="lg:hidden -m-2.5 p-2.5 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              onClick={() => setSidebarOpen(true)}
            >
              <Bars3Icon className="h-6 w-6" />
            </button>

            {/* Breadcrumb navigation */}
            <nav className="hidden md:flex items-center gap-2 text-sm min-w-0" aria-label="Breadcrumb">
              {breadcrumbs.map((crumb, index) => (
                <div key={crumb.path} className="flex items-center gap-2 min-w-0">
                  {index > 0 && (
                    <ChevronRightIcon className="h-4 w-4 text-gray-400 flex-shrink-0" />
                  )}
                  {index === breadcrumbs.length - 1 ? (
                    <span className="text-gray-900 dark:text-white font-medium truncate">
                      {crumb.label}
                    </span>
                  ) : (
                    <Link
                      to={crumb.path}
                      className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 truncate transition-colors"
                    >
                      {crumb.label}
                    </Link>
                  )}
                </div>
              ))}
            </nav>

            {/* Mobile: Show current page title */}
            <div className="md:hidden flex items-center gap-2 min-w-0">
              <Link to="/" className="flex items-center gap-2">
                <img src="/weevoice_logo.svg" alt="Weevoice" className="h-6 w-auto object-contain" />
              </Link>
              {breadcrumbs.length > 1 && (
                <>
                  <ChevronRightIcon className="h-4 w-4 text-gray-400 flex-shrink-0" />
                  <span className="text-sm text-gray-700 dark:text-gray-300 truncate">
                    {breadcrumbs[breadcrumbs.length - 1].label}
                  </span>
                </>
              )}
            </div>
          </div>

          {/* Right side: Search */}
          <div className="relative flex items-center">
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <MagnifyingGlassIcon className="h-5 w-5 text-gray-400" />
              </div>
              <input
                type="text"
                placeholder={t.common.status === 'Statut' ? 'Rechercher...' : 'Search...'}
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value)
                  setShowSearchResults(e.target.value.length > 0)
                }}
                onFocus={() => {
                  if (searchQuery.length > 0) {
                    setShowSearchResults(true)
                  }
                }}
                onBlur={() => {
                  // Delay to allow clicking on results
                  setTimeout(() => setShowSearchResults(false), 200)
                }}
                className="block w-64 pl-10 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
              />
              {searchQuery && (
                <button
                  onClick={() => {
                    setSearchQuery('')
                    setShowSearchResults(false)
                  }}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center"
                >
                  <XMarkIcon className="h-5 w-5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300" />
                </button>
              )}
            </div>

            {/* Search results dropdown */}
            {showSearchResults && searchQuery && (
              <div className="absolute top-full right-0 mt-2 w-96 bg-white dark:bg-gray-800 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 z-50 max-h-96 overflow-y-auto">
                <div className="p-4">
                  <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
                    {t.common.status === 'Statut' ? 'Résultats de recherche' : 'Search results'}
                  </p>
                  <div className="space-y-2">
                    {/* Quick navigation results */}
                    {allNavigationItems
                      .filter(item => 
                        item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                        item.href.toLowerCase().includes(searchQuery.toLowerCase())
                      )
                      .slice(0, 8)
                      .map((item) => {
                        const isActive = location.pathname === item.href
                        return (
                          <Link
                            key={item.href}
                            to={item.href}
                            onClick={() => {
                              setSearchQuery('')
                              setShowSearchResults(false)
                            }}
                            className={`flex items-center gap-3 p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors ${
                              isActive ? 'bg-indigo-50 dark:bg-indigo-950/50' : ''
                            }`}
                          >
                            <item.icon className="h-5 w-5 text-gray-400" />
                            <span className="text-sm text-gray-900 dark:text-white">{item.name}</span>
                          </Link>
                        )
                      })}
                    {allNavigationItems.filter(item => 
                      item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                      item.href.toLowerCase().includes(searchQuery.toLowerCase())
                    ).length === 0 && (
                      <p className="text-sm text-gray-500 dark:text-gray-400 py-4 text-center">
                        {t.common.status === 'Statut' ? 'Aucun résultat trouvé' : 'No results found'}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Page content */}
        <main className="py-8 px-4 sm:px-6 lg:px-8 min-h-screen bg-white dark:bg-gray-900">
          {children}
        </main>
      </div>
    </div>
  )
}