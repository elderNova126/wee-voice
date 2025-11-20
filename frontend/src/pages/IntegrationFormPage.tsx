import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { ArrowLeftIcon } from '@heroicons/react/24/outline'
import DashboardLayout from '@/layouts/DashboardLayout'
import { integrationsAPI } from '@/lib/api'
import toast from 'react-hot-toast'
import { useTranslation } from '@/lib/translations'

interface IntegrationFormData {
  name: string
  description: string
  integration_type: string
  provider: string
  config: Record<string, any>
}

interface IntegrationTypes {
  types: string[]
  providers: string[]
  type_provider_mapping: Record<string, string[]>
}

const CONFIG_TEMPLATES: Record<string, Record<string, any>> = {
  google_calendar: {
    access_token: '',
    refresh_token: '',
    calendar_id: 'primary',
  },
  outlook_calendar: {
    access_token: '',
    tenant_id: '',
  },
  gmail: {
    access_token: '',
    refresh_token: '',
  },
  smtp: {
    smtp_host: '',
    smtp_port: 587,
    username: '',
    password: '',
    from_email: '',
  },
  hubspot: {
    api_key: '',
    portal_id: '',
  },
  salesforce: {
    access_token: '',
    instance_url: '',
  },
  postgresql: {
    host: '',
    port: 5432,
    database: '',
    user: '',
    password: '',
  },
  quickbooks: {
    access_token: '',
    company_id: '',
  },
  xero: {
    access_token: '',
    tenant_id: '',
  },
  webhook: {
    webhook_url: '',
    headers: {},
  },
  rest_api: {
    base_url: '',
    api_key: '',
  },
}

export default function IntegrationFormPage() {
  const t = useTranslation()
  const { id } = useParams()
  const navigate = useNavigate()
  const isEdit = Boolean(id)

  const [formData, setFormData] = useState<IntegrationFormData>({
    name: '',
    description: '',
    integration_type: '',
    provider: '',
    config: {},
  })

  const [typesData, setTypesData] = useState<IntegrationTypes | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadingIntegration, setLoadingIntegration] = useState(isEdit)
  const [availableProviders, setAvailableProviders] = useState<string[]>([])

  useEffect(() => {
    loadTypes()
  }, [])

  useEffect(() => {
    if (formData.integration_type && typesData) {
      const providers = typesData.type_provider_mapping[formData.integration_type] || []
      setAvailableProviders(providers)
      if (!providers.includes(formData.provider)) {
        setFormData((prev) => ({ ...prev, provider: '', config: {} }))
      } else if (formData.provider && !formData.config || Object.keys(formData.config).length === 0) {
        setFormData((prev) => ({
          ...prev,
          config: { ...CONFIG_TEMPLATES[formData.provider] || {} },
        }))
      }
    }
  }, [formData.integration_type, typesData])

  const loadTypes = async () => {
    try {
      const response = await integrationsAPI.getTypes()
      setTypesData(response.data)
    } catch (error) {
      console.error('Failed to load integration types:', error)
    }
  }

  const loadIntegration = useCallback(async (integrationId: number) => {
    try {
      const { data: integration } = await integrationsAPI.get(integrationId)
      setFormData({
        name: integration.name,
        description: integration.description || '',
        integration_type: integration.integration_type,
        provider: integration.provider,
        config: integration.config || {},
      })
    } catch (err) {
      toast.error(t.integrations.loadIntegrationError)
      navigate('/dashboard/integrations')
    } finally {
      setLoadingIntegration(false)
    }
  }, [navigate, t])

  useEffect(() => {
    if (isEdit && id) loadIntegration(parseInt(id))
  }, [isEdit, id, loadIntegration])

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    const { name, value, type } = e.target
    if (name.startsWith('config.')) {
      const configKey = name.replace('config.', '')
      setFormData((prev) => ({
        ...prev,
        config: {
          ...prev.config,
          [configKey]: type === 'number' ? parseFloat(value) || 0 : value,
        },
      }))
    } else {
      setFormData((prev) => ({ ...prev, [name]: value }))
    }
  }

  const handleConfigChange = (key: string, value: any) => {
    setFormData((prev) => ({
      ...prev,
      config: {
        ...prev.config,
        [key]: value,
      },
    }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      if (isEdit && id) {
        await integrationsAPI.update(Number(id), formData)
        toast.success(t.integrations.updateSuccess)
      } else {
        await integrationsAPI.create(formData)
        toast.success(t.integrations.createSuccess)
      }
      navigate('/dashboard/integrations')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t.integrations.saveError)
    } finally {
      setLoading(false)
    }
  }

  const renderConfigFields = () => {
    if (!formData.provider) return null

    const template = CONFIG_TEMPLATES[formData.provider] || {}
    const config = formData.config || {}

    return (
      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{t.integrations.configuration}</h3>
        {Object.keys(template).map((key) => {
          const isPassword = key.toLowerCase().includes('password') || key.toLowerCase().includes('token')
          const value = config[key] || ''
          
          if (key === 'headers' && typeof template[key] === 'object') {
            return (
              <div key={key} className="space-y-2">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  {t.integrations.headersJson}
                </label>
                <textarea
                  name={`config.${key}`}
                  value={JSON.stringify(config[key] || {}, null, 2)}
                  onChange={(e) => {
                    try {
                      const parsed = JSON.parse(e.target.value)
                      handleConfigChange(key, parsed)
                    } catch {
                      // Invalid JSON, ignore
                    }
                  }}
                  rows={4}
                  className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white font-mono text-sm"
                  placeholder='{"Authorization": "Bearer token"}'
                />
              </div>
            )
          }

          return (
            <div key={key}>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                {typeof template[key] === 'number' && (t.common.status === 'Statut' ? ' (Nombre)' : ' (Number)')}
              </label>
              <input
                type={isPassword ? 'password' : typeof template[key] === 'number' ? 'number' : 'text'}
                name={`config.${key}`}
                value={value}
                onChange={handleChange}
                className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                placeholder={key}
                required={key === 'access_token' || key === 'api_key' || key === 'smtp_host'}
              />
            </div>
          )
        })}
        <p className="text-sm text-gray-500 dark:text-gray-400">
          {t.integrations.credentialsWarning}
        </p>
      </div>
    )
  }

  if (loadingIntegration || !typesData) {
    return (
      <DashboardLayout>
        <div className="animate-pulse max-w-3xl space-y-6">
          <div className="h-8 w-1/3 rounded bg-gray-200 dark:bg-gray-700"></div>
          <div className="h-64 rounded bg-gray-200 dark:bg-gray-700"></div>
        </div>
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout>
      <div className="max-w-3xl">
        <Link
          to="/dashboard/integrations"
          className="inline-flex items-center text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white mb-6"
        >
          <ArrowLeftIcon className="h-4 w-4 mr-1" />
          {t.integrations.backToIntegrations}
        </Link>

        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-8">
          {isEdit ? t.integrations.editIntegrationTitle : t.integrations.newIntegrationTitle}
        </h1>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              {t.integrations.name}
            </label>
            <input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleChange}
              required
              className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              placeholder={t.integrations.namePlaceholder}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              {t.integrations.description}
            </label>
            <textarea
              name="description"
              value={formData.description}
              onChange={handleChange}
              rows={3}
              className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              placeholder={t.integrations.descriptionPlaceholder}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              {t.integrations.integrationType}
            </label>
            <select
              name="integration_type"
              value={formData.integration_type}
              onChange={handleChange}
              required
              className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
            >
              <option value="">{t.integrations.selectType}</option>
              {typesData.types.map((type) => (
                <option key={type} value={type}>
                  {type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                </option>
              ))}
            </select>
          </div>

          {formData.integration_type && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t.integrations.provider}
              </label>
              <select
                name="provider"
                value={formData.provider}
                onChange={handleChange}
                required
                className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              >
                <option value="">{t.integrations.selectProvider}</option>
                {availableProviders.map((provider) => (
                  <option key={provider} value={provider}>
                    {provider.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </option>
                ))}
              </select>
            </div>
          )}

          {renderConfigFields()}

          <div className="flex gap-4 pt-6">
            <button
              type="submit"
              disabled={loading}
              className="flex-1 px-6 py-3 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium transition disabled:opacity-50"
            >
              {loading ? t.integrations.saving : isEdit ? t.integrations.updateIntegration : t.integrations.createIntegrationButton}
            </button>
            <Link
              to="/dashboard/integrations"
              className="px-6 py-3 rounded-lg bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200 font-medium transition"
            >
              {t.common.cancel}
            </Link>
          </div>
        </form>
      </div>
    </DashboardLayout>
  )
}


