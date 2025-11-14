import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import DashboardLayout from '@/layouts/DashboardLayout'
import { useTranslation } from '@/lib/translations'
import BillingContent from './settings/BillingContent'
import UsageContent from './settings/UsageContent'
import SecurityContent from './settings/SecurityContent'
import ApiKeysContent from './settings/ApiKeysContent'

type SettingsTab = 'billing' | 'usage' | 'security' | 'apiKeys'

export default function SettingsPage() {
  const t = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const [activeTab, setActiveTab] = useState<SettingsTab>(() => {
    const tab = searchParams.get('tab') as SettingsTab
    return tab && ['billing', 'usage', 'security', 'apiKeys'].includes(tab) ? tab : 'billing'
  })

  useEffect(() => {
    setSearchParams({ tab: activeTab }, { replace: true })
  }, [activeTab, setSearchParams])

  const tabs: { id: SettingsTab; label: string }[] = [
    { id: 'billing', label: t.nav.billing || 'Billing' },
    { id: 'usage', label: t.nav.usage || 'Usage' },
    { id: 'security', label: t.nav.security || 'Security' },
    { id: 'apiKeys', label: t.nav.apiKeys || 'API Keys' },
  ]

  const renderTabContent = () => {
    switch (activeTab) {
      case 'billing':
        return <BillingContent />
      case 'usage':
        return <UsageContent />
      case 'security':
        return <SecurityContent />
      case 'apiKeys':
        return <ApiKeysContent />
      default:
        return <BillingContent />
    }
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            {t.common.status === 'Statut' ? 'Paramètres' : 'Settings'}
          </h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            {t.common.status === 'Statut' ? 'Gérez votre facturation, utilisation, sécurité et clés API' : 'Manage your billing, usage, security, and API keys'}
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

