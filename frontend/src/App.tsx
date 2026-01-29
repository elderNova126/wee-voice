import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'

// Pages
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import VerifyEmailPage from './pages/VerifyEmailPage'
import ForgotPasswordPage from './pages/ForgotPasswordPage'
import ResetPasswordPage from './pages/ResetPasswordPage'
import ResendVerificationPage from './pages/ResendVerificationPage'
import DashboardPage from './pages/DashboardPage'
import AgentsPage from './pages/AgentsPage'
import AgentDetailPage from './pages/AgentDetailPage'
import AgentFormPage from './pages/AgentFormPage'
import AgentDocumentsPage from './pages/AgentDocumentsPage'
import CallsPage from './pages/CallsPage'
import APIKeysPage from './pages/ApiKeysPage'
import DemoPage from './pages/DemoPage'
import PublicAgentPage from './pages/PublicAgentPage'
import ProfilePage from './pages/ProfilePage'
import SupportPage from './pages/SupportPage'
import PrivacyPolicyPage from './pages/PrivacyPolicyPage'
import TermsOfServicePage from './pages/TermsOfServicePage'
import AboutPage from './pages/AboutPage'
import DocumentationPage from './pages/DocumentationPage'
import { PhoneNumbersPage } from './pages/PhoneNumbersPage'
import { CallbacksPage } from './pages/CallbacksPage'
import { AgentEmbedPage } from './pages/AgentEmbedPage'
import AdminPage from './pages/AdminPage'
import LibrariesPage from './pages/LibrariesPage'
import SettingsPage from './pages/SettingsPage'
import UsagePage from './pages/UsagePage'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  
  return <>{children}</>
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user } = useAuthStore()
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  
  if (!user?.is_superuser) {
    return <Navigate to="/dashboard" replace />
  }
  
  return <>{children}</>
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/demo" element={<DemoPage />} />
        <Route path="/agent/:agentId" element={<PublicAgentPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/resend-verification" element={<ResendVerificationPage />} />
        <Route path="/privacy" element={<PrivacyPolicyPage />} />
        <Route path="/terms" element={<TermsOfServicePage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="/docs" element={<DocumentationPage />} />
        
        {/* Protected routes */}
        <Route path="/dashboard" element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        } />
        <Route path="/dashboard/agents" element={
          <ProtectedRoute>
            <AgentsPage />
          </ProtectedRoute>
        } />
        <Route path="/dashboard/agents/:agentId/view" element={
          <ProtectedRoute>
            <AgentDetailPage />
          </ProtectedRoute>
        } />
        <Route path="/dashboard/agents/new" element={
          <ProtectedRoute>
            <AgentFormPage />
          </ProtectedRoute>
        } />
        <Route path="/dashboard/agents/:id/edit" element={
          <ProtectedRoute>
            <AgentFormPage />
          </ProtectedRoute>
        } />
        <Route path="/dashboard/agents/:agentId/documents" element={
          <ProtectedRoute>
            <AgentDocumentsPage />
          </ProtectedRoute>
        } />
        <Route path="/dashboard/calls" element={
          <ProtectedRoute>
            <CallsPage />
          </ProtectedRoute>
        } />
        <Route path="/dashboard/settings" element={
          <ProtectedRoute>
            <SettingsPage />
          </ProtectedRoute>
        } />
        <Route path="/dashboard/usage" element={
          <ProtectedRoute>
            <UsagePage />
          </ProtectedRoute>
        } />
        <Route path="/dashboard/profile" element={
          <ProtectedRoute>
            <ProfilePage />
          </ProtectedRoute>
        } />
        <Route path="/dashboard/support" element={
          <ProtectedRoute>
            <SupportPage />
          </ProtectedRoute>
        } />
        <Route path="/dashboard/phone-numbers" element={
          <ProtectedRoute>
            <PhoneNumbersPage />
          </ProtectedRoute>
        } />
        <Route path="/dashboard/callbacks" element={
          <ProtectedRoute>
            <CallbacksPage />
          </ProtectedRoute>
        } />
        <Route path="/dashboard/agents/:agentId/embed" element={
          <ProtectedRoute>
            <AgentEmbedPage />
          </ProtectedRoute>
        } />
        <Route path="/dashboard/libraries" element={
          <ProtectedRoute>
            <LibrariesPage />
          </ProtectedRoute>
        } />
        <Route path="/dashboard/admin" element={
          <AdminRoute>
            <AdminPage />
          </AdminRoute>
        } />
        <Route path="/support" element={<SupportPage />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App

