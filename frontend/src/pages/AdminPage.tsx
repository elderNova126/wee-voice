import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import DashboardLayout from '@/layouts/DashboardLayout'
import { useTranslation } from '@/lib/translations'
import AdminOverviewContent from './admin/AdminOverviewContent'
import AdminUsersContent from './admin/AdminUsersContent'
import AdminAgentsContent from './admin/AdminAgentsContent'
import AdminSupportContent from './admin/AdminSupportContent'

type AdminTab = 'overview' | 'users' | 'agents' | 'support'

export default function AdminPage() {
  const t = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const [activeTab, setActiveTab] = useState<AdminTab>(() => {
    const tab = searchParams.get('tab') as AdminTab
    return tab && ['overview', 'users', 'agents', 'support'].includes(tab) ? tab : 'overview'
  })

  useEffect(() => {
    setSearchParams({ tab: activeTab }, { replace: true })
  }, [activeTab, setSearchParams])

  const tabs: { id: AdminTab; label: string }[] = [
    { id: 'overview', label: t.admin.overview },
    { id: 'users', label: t.admin.users },
    { id: 'agents', label: t.admin.agents },
    { id: 'support', label: t.admin.support },
  ]

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return <AdminOverviewContent />
      case 'users':
        return <AdminUsersContent />
      case 'agents':
        return <AdminAgentsContent />
      case 'support':
        return <AdminSupportContent />
      default:
        return <AdminOverviewContent />
    }
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            {t.common.status === 'Statut' ? 'Administration' : 'Administration'}
          </h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            {t.common.status === 'Statut' ? 'Gérez la plateforme, les utilisateurs, les agents et le support' : 'Manage the platform, users, agents, and support'}
          </p>
        </div>

        {/* Tabs */}
        <div className="border-b border-gray-200 dark:border-gray-700">
          <nav className="-mb-px flex space-x-8" aria-label="Tabs">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`
                  whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition-colors
                  ${
                    activeTab === tab.id
                      ? 'border-indigo-500 text-indigo-600 dark:text-indigo-400'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
                  }
                `}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Tab Content */}
        <div className="mt-6">
          {renderTabContent()}
        </div>
      </div>
    </DashboardLayout>
  )
}

