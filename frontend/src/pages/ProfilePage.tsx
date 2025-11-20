import { useState, useEffect } from 'react'
import { profileAPI } from '@/lib/api'
import { useAuthStore } from '@/store/authStore'
import DashboardLayout from '@/layouts/DashboardLayout'
import ThemeToggle from '@/components/ThemeToggle'
import { useTranslation } from '@/lib/translations'
import toast from 'react-hot-toast'

interface Profile {
  id: number
  email: string
  full_name: string
  subscription_tier: string
  credit_balance: number
  total_minutes_used: number
  monthly_minutes_used: number
  is_active: boolean
  created_at: string
  updated_at: string
}

interface AccountStats {
  total_agents: number
  total_calls: number
  total_minutes: number
  total_cost: number
  account_age_days: number
}

const ProfilePage = () => {
  const t = useTranslation()
  const [profile, setProfile] = useState<Profile | null>(null)
  const [stats, setStats] = useState<AccountStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'profile' | 'danger'>('profile')

  const [editing, setEditing] = useState(false)
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [saving, setSaving] = useState(false)

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [changingPassword, setChangingPassword] = useState(false)

  const user = useAuthStore((state) => state.user)

  useEffect(() => {
    loadProfileData()
  }, [])

  const loadProfileData = async () => {
    try {
      setLoading(true)
      const [profileRes, statsRes] = await Promise.all([
        profileAPI.getProfile(),
        profileAPI.getStats(),
      ])
      setProfile(profileRes.data)
      setStats(statsRes.data)
      setFullName(profileRes.data.full_name)
      setEmail(profileRes.data.email)
    } catch (error) {
      console.error('Error loading profile:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSaveProfile = async () => {
    try {
      setSaving(true)
      await profileAPI.updateProfile({ full_name: fullName, email: email })
      await loadProfileData()
      setEditing(false)
      toast.success(t.profile.updateSuccess)
    } catch (error: any) {
      console.error('Error saving profile:', error)
      toast.error(error.response?.data?.detail || t.profile.updateError)
    } finally {
      setSaving(false)
    }
  }

  const handleChangePassword = async () => {
    if (newPassword.length < 8) {
      toast.error(t.register.passwordMinLength)
      return
    }
    if (newPassword !== confirmPassword) {
      toast.error(t.register.passwordMismatch)
      return
    }

    try {
      setChangingPassword(true)
      await profileAPI.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      })
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      toast.success(t.profile.passwordChanged)
    } catch (error: any) {
      console.error('Error changing password:', error)
      toast.error(error.response?.data?.detail || t.profile.passwordError)
    } finally {
      setChangingPassword(false)
    }
  }

  const formatDate = (dateString: string) =>
    new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })

  const formatMinutes = (minutes: number) => {
    const hours = Math.floor(minutes / 60)
    const mins = Math.floor(minutes % 60)
    return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`
  }

  return (
    <DashboardLayout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">{t.profile.title}</h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            {t.profile.subtitle}
          </p>
        </div>

        {/* Tabs */}
        <div className="border-b border-gray-200 mb-6">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab('profile')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'profile'
                  ? 'border-indigo-500 text-indigo-600 dark:text-indigo-400'
                  : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300'
              }`}
            >
              {t.profile.title}
            </button>

            <button
              onClick={() => setActiveTab('danger')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'danger'
                  ? 'border-red-500 text-red-600 dark:text-red-400'
                  : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300'
              }`}
            >
              {t.common.status === 'Statut' ? 'Zone de danger' : 'Danger Zone'}
            </button>
          </nav>
        </div>

        {/* Profile Tab */}
        {activeTab === 'profile' && (
          <div className="space-y-6">
            {/* Account Stats */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {[
                { label: t.dashboard.totalAgents, value: stats?.total_agents || 0 },
                { label: t.dashboard.totalCalls, value: stats?.total_calls || 0 },
                { label: t.usage.minutes, value: formatMinutes(stats?.total_minutes || 0) },
                { label: t.common.status === 'Statut' ? 'Âge du compte' : 'Account Age', value: `${stats?.account_age_days || 0} ${t.common.status === 'Statut' ? 'jours' : 'days'}` },
              ].map((stat, idx) => (
                <div key={idx} className="bg-white dark:bg-gray-900 rounded-xl shadow p-6">
                  <p className="text-sm text-gray-600 dark:text-gray-400">{stat.label}</p>
                  {loading ? (
                    <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-20 mt-2 animate-pulse"></div>
                  ) : (
                    <p className="text-3xl font-semibold text-gray-900 dark:text-gray-100 mt-2">
                      {stat.value}
                    </p>
                  )}
                </div>
              ))}
            </div>

            {/* Appearance Settings */}
            <div className="bg-white dark:bg-gray-900 shadow rounded-xl p-6">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                {t.settings.theme}
              </h2>
              <ThemeToggle showLabel />
            </div>

            {/* Profile Information */}
            <div className="max-w-3xl mx-auto bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl shadow-sm overflow-hidden">
              <div className="flex items-center justify-between px-6 py-5 border-b border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-950/50">
                <div>
                  <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                    {t.profile.personalInfo}
                  </h2>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {t.common.status === 'Statut' ? 'Gérez vos informations personnelles' : 'Manage your personal details'}
                  </p>
                </div>
                {!editing && (
                  <button
                    onClick={() => setEditing(true)}
                    className="px-4 py-2 text-sm font-medium text-indigo-600 hover:text-indigo-700 border border-indigo-100 dark:border-indigo-800 rounded-lg hover:bg-indigo-50 dark:hover:bg-indigo-900/40 transition-all"
                  >
                    {t.common.edit}
                  </button>
                )}
              </div>

              <div className="px-6 py-8 space-y-6">
                {/* Full Name */}
                <div>
                  <label className="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">
                    {t.register.fullName}
                  </label>
                  {editing ? (
                    <input
                      type="text"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      className="w-full px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition"
                    />
                  ) : (
                    <p className="text-gray-900 dark:text-gray-100 font-medium">
                      {profile?.full_name}
                    </p>
                  )}
                </div>

                {/* Email */}
                <div>
                  <label className="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">
                    {t.auth.email}
                  </label>
                  {editing ? (
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition"
                    />
                  ) : (
                    <p className="text-gray-900 dark:text-gray-100 font-medium">{profile?.email}</p>
                  )}
                </div>

                {/* Subscription Info */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">
                      {t.billing.currentPlan}
                    </label>
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 capitalize">
                      {profile?.subscription_tier || 'Free'}
                    </span>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">
                      {t.common.status === 'Statut' ? 'Membre depuis' : 'Member Since'}
                    </label>
                    <p className="text-gray-900 dark:text-gray-100 font-medium">
                      {profile ? formatDate(profile.created_at) : '-'}
                    </p>
                  </div>
                </div>
              </div>

              {/* Profile Save Buttons */}
              {editing && (
                <div className="flex justify-end gap-3 px-6 py-5 border-t border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-950/50">
                  <button
                    onClick={() => {
                      setEditing(false)
                      setFullName(profile?.full_name || '')
                      setEmail(profile?.email || '')
                    }}
                    disabled={saving}
                    className="px-5 py-2.5 text-sm font-medium border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-200 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-all"
                  >
                    {t.common.cancel}
                  </button>
                  <button
                    onClick={handleSaveProfile}
                    disabled={saving}
                    className="px-5 py-2.5 text-sm font-medium bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-400 text-white rounded-lg shadow-sm transition-all"
                  >
                    {saving ? (t.common.status === 'Statut' ? 'Enregistrement...' : 'Saving...') : t.common.save}
                  </button>
                </div>
              )}
            </div>

            {/* 🔐 Password Change Section */}
            <div className="max-w-3xl mx-auto bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl shadow-sm p-6 mt-6">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
                {t.profile.changePassword}
              </h2>
              <div className="space-y-4">
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  placeholder={t.profile.currentPassword}
                  className="w-full px-4 py-2.5 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-indigo-500"
                />
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder={`${t.profile.newPassword} (${t.common.status === 'Statut' ? 'min 8 caractères' : 'min 8 characters'})`}
                  className="w-full px-4 py-2.5 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-indigo-500"
                />
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder={t.profile.confirmNewPassword}
                  className="w-full px-4 py-2.5 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-indigo-500"
                />
                <div className="flex justify-end">
                  <button
                    onClick={handleChangePassword}
                    disabled={changingPassword || !currentPassword || !newPassword || !confirmPassword}
                    className="px-5 py-2.5 text-sm font-medium bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-400 text-white rounded-lg shadow-sm transition-all"
                  >
                    {changingPassword ? (t.common.status === 'Statut' ? 'Modification...' : 'Changing...') : (t.common.status === 'Statut' ? 'Mettre à jour le mot de passe' : 'Update Password')}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Danger Zone Tab */}
        {activeTab === 'danger' && (
          <div className="bg-white dark:bg-gray-900 shadow rounded-xl p-6 max-w-2xl border-2 border-red-200 dark:border-red-800">
            <h2 className="text-xl font-semibold text-red-600 mb-4">{t.common.status === 'Statut' ? 'Zone de danger' : 'Danger Zone'}</h2>
            <div className="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-4">
              <h3 className="font-semibold text-red-900 dark:text-red-200 mb-2">
                {t.common.status === 'Statut' ? 'Supprimer le compte' : 'Delete Account'}
              </h3>
              <p className="text-sm text-red-800 dark:text-red-300 mb-4">
                {t.common.status === 'Statut' ? 'Une fois votre compte supprimé, il ne peut pas être récupéré. Cela supprimera définitivement toutes vos données, agents et activités.' : 'Once you delete your account, it cannot be recovered. This will permanently remove all your data, agents, and activity.'}
              </p>
              <button
                onClick={() => {
                  const password = prompt(t.common.status === 'Statut' ? 'Entrez votre mot de passe pour confirmer la suppression du compte :' : 'Enter your password to confirm account deletion:')
                  if (password && confirm(t.common.status === 'Statut' ? 'Êtes-vous absolument sûr ? Cette action ne peut pas être annulée.' : 'Are you absolutely sure? This action cannot be undone.')) {
                    profileAPI.deleteAccount(password)
                      .then(() => {
                        toast.success(t.common.status === 'Statut' ? 'Compte supprimé avec succès. Déconnexion...' : 'Account deleted successfully. Logging out...')
                        useAuthStore.getState().logout()
                        window.location.href = '/login'
                      })
                      .catch((error) => {
                        toast.error(error.response?.data?.detail || (t.common.status === 'Statut' ? 'Échec de la suppression du compte' : 'Failed to delete account'))
                      })
                  }
                }}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 font-semibold"
              >
                {t.common.status === 'Statut' ? 'Supprimer le compte' : 'Delete Account'}
              </button>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}

export default ProfilePage
