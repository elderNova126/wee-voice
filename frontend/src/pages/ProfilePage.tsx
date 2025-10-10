import { useState, useEffect } from 'react'
import { profileAPI } from '@/lib/api'
import { useAuthStore } from '@/store/authStore'
import DashboardLayout from '@/layouts/DashboardLayout'
import ThemeToggle from '@/components/ThemeToggle'

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
  const [profile, setProfile] = useState<Profile | null>(null)
  const [stats, setStats] = useState<AccountStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'profile' | 'password' | 'danger'>('profile')
  
  // Profile edit
  const [editing, setEditing] = useState(false)
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [saving, setSaving] = useState(false)
  
  // Password change
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
      await profileAPI.updateProfile({
        full_name: fullName,
        email: email,
      })
      
      await loadProfileData()
      setEditing(false)
      alert('Profile updated successfully!')
    } catch (error: any) {
      console.error('Error saving profile:', error)
      alert(error.response?.data?.detail || 'Failed to update profile')
    } finally {
      setSaving(false)
    }
  }

  const handleChangePassword = async () => {
    if (newPassword.length < 8) {
      alert('Password must be at least 8 characters long')
      return
    }
    
    if (newPassword !== confirmPassword) {
      alert('Passwords do not match')
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
      alert('Password changed successfully!')
    } catch (error: any) {
      console.error('Error changing password:', error)
      alert(error.response?.data?.detail || 'Failed to change password')
    } finally {
      setChangingPassword(false)
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  }

  const formatMinutes = (minutes: number) => {
    const hours = Math.floor(minutes / 60)
    const mins = Math.floor(minutes % 60)
    if (hours > 0) {
      return `${hours}h ${mins}m`
    }
    return `${mins}m`
  }

  return (
    <DashboardLayout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Account Settings</h1>
          <p className="mt-2 text-gray-600">Manage your profile and account preferences</p>
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
              Profile
            </button>
            <button
              onClick={() => setActiveTab('password')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'password'
                  ? 'border-indigo-500 text-indigo-600 dark:text-indigo-400'
                  : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300'
              }`}
            >
              Password
            </button>
            <button
              onClick={() => setActiveTab('danger')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'danger'
                  ? 'border-red-500 text-red-600 dark:text-red-400'
                  : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300'
              }`}
            >
              Danger Zone
            </button>
          </nav>
        </div>

        {/* Profile Tab */}
        {activeTab === 'profile' && (
          <div className="space-y-6">
            {/* Account Stats */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <div className="bg-white rounded-lg shadow p-6">
                <p className="text-sm text-gray-600">Total Agents</p>
                {loading ? (
                  <div className="h-8 bg-gray-200 rounded w-16 mt-2 animate-pulse"></div>
                ) : (
                  <p className="text-3xl font-bold text-gray-900 mt-2">{stats?.total_agents || 0}</p>
                )}
              </div>
              
              <div className="bg-white rounded-lg shadow p-6">
                <p className="text-sm text-gray-600">Total Calls</p>
                {loading ? (
                  <div className="h-8 bg-gray-200 rounded w-16 mt-2 animate-pulse"></div>
                ) : (
                  <p className="text-3xl font-bold text-gray-900 mt-2">{stats?.total_calls || 0}</p>
                )}
              </div>
              
              <div className="bg-white rounded-lg shadow p-6">
                <p className="text-sm text-gray-600">Total Minutes</p>
                {loading ? (
                  <div className="h-8 bg-gray-200 rounded w-20 mt-2 animate-pulse"></div>
                ) : (
                  <p className="text-3xl font-bold text-gray-900 mt-2">
                    {formatMinutes(stats?.total_minutes || 0)}
                  </p>
                )}
              </div>
              
              <div className="bg-white rounded-lg shadow p-6">
                <p className="text-sm text-gray-600">Account Age</p>
                {loading ? (
                  <div className="h-8 bg-gray-200 rounded w-24 mt-2 animate-pulse"></div>
                ) : (
                  <p className="text-3xl font-bold text-gray-900 mt-2">{stats?.account_age_days || 0} days</p>
                )}
              </div>
            </div>

            {/* Appearance Settings */}
            <div className="bg-white dark:bg-gray-800 shadow rounded-lg p-6">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">Appearance</h2>
              <ThemeToggle showLabel />
            </div>

            {/* Profile Information */}
            <div className="bg-white dark:bg-gray-800 shadow rounded-lg p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Profile Information</h2>
                {!editing && (
                  <button
                    onClick={() => setEditing(true)}
                    className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
                  >
                    Edit
                  </button>
                )}
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                  {editing ? (
                    <input
                      type="text"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  ) : loading ? (
                    <div className="h-10 bg-gray-200 rounded w-64 animate-pulse"></div>
                  ) : (
                    <p className="text-gray-900 py-2">{profile?.full_name}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                  {editing ? (
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  ) : loading ? (
                    <div className="h-10 bg-gray-200 rounded w-80 animate-pulse"></div>
                  ) : (
                    <p className="text-gray-900 py-2">{profile?.email}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Subscription Tier</label>
                  {loading ? (
                    <div className="h-10 bg-gray-200 rounded w-40 animate-pulse"></div>
                  ) : (
                    <p className="text-gray-900 py-2 capitalize">{profile?.subscription_tier || 'Free'}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Member Since</label>
                  {loading ? (
                    <div className="h-10 bg-gray-200 rounded w-48 animate-pulse"></div>
                  ) : (
                    <p className="text-gray-900 py-2">{profile ? formatDate(profile.created_at) : '-'}</p>
                  )}
                </div>

                {editing && (
                  <div className="flex gap-3 pt-4">
                    <button
                      onClick={() => {
                        setEditing(false)
                        setFullName(profile?.full_name || '')
                        setEmail(profile?.email || '')
                      }}
                      className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
                      disabled={saving}
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleSaveProfile}
                      disabled={saving}
                      className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:bg-gray-300"
                    >
                      {saving ? 'Saving...' : 'Save Changes'}
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Password Tab */}
        {activeTab === 'password' && (
          <div className="bg-white shadow rounded-lg p-6 max-w-2xl">
            <h2 className="text-xl font-semibold mb-6">Change Password</h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Current Password</label>
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">New Password</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500"
                />
                <p className="text-xs text-gray-500 mt-1">Minimum 8 characters</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Confirm New Password</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>

              <button
                onClick={handleChangePassword}
                disabled={changingPassword || !currentPassword || !newPassword || !confirmPassword}
                className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
              >
                {changingPassword ? 'Changing Password...' : 'Change Password'}
              </button>
            </div>
          </div>
        )}

        {/* Danger Zone Tab */}
        {activeTab === 'danger' && (
          <div className="bg-white shadow rounded-lg p-6 max-w-2xl border-2 border-red-200">
            <h2 className="text-xl font-semibold text-red-600 mb-4">Danger Zone</h2>
            
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
              <h3 className="font-semibold text-red-900 mb-2">Delete Account</h3>
              <p className="text-sm text-red-800 mb-4">
                Once you delete your account, there is no going back. This action will deactivate your account 
                and remove access to all your agents, calls, and data.
              </p>
              
              <button
                onClick={() => {
                  const password = prompt('Enter your password to confirm account deletion:')
                  if (password) {
                    if (confirm('Are you absolutely sure? This action cannot be undone.')) {
                      profileAPI.deleteAccount(password)
                        .then(() => {
                          alert('Account deleted successfully. You will be logged out.')
                          // Logout user
                          useAuthStore.getState().logout()
                          window.location.href = '/login'
                        })
                        .catch((error) => {
                          alert(error.response?.data?.detail || 'Failed to delete account')
                        })
                    }
                  }
                }}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 font-semibold"
              >
                Delete Account
              </button>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}

export default ProfilePage

