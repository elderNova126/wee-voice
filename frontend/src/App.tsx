import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'

// Pages
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import AgentsPage from './pages/AgentsPage'
import AgentFormPage from './pages/AgentFormPage'
import AgentDocumentsPage from './pages/AgentDocumentsPage'
import CallsPage from './pages/CallsPage'
import APIKeysPage from './pages/ApiKeysPage'
import DemoPage from './pages/DemoPage'
import PublicAgentPage from './pages/PublicAgentPage'
import BillingPage from './pages/BillingPage'
import UsagePage from './pages/UsagePage'
import SecurityPage from './pages/SecurityPage'
import ProfilePage from './pages/ProfilePage'
import SupportPage from './pages/SupportPage'
import IntegrationsPage from './pages/IntegrationsPage'
import IntegrationFormPage from './pages/IntegrationFormPage'
import { PhoneNumbersPage } from './pages/PhoneNumbersPage'
import { CallbacksPage } from './pages/CallbacksPage'
import { AgentEmbedPage } from './pages/AgentEmbedPage'
import AdminPage from './pages/AdminPage'
import LibrariesPage from './pages/LibrariesPage'

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
        <Route path="/dashboard/api-keys" element={
          <ProtectedRoute>
            <APIKeysPage />
          </ProtectedRoute>
        } />
        <Route path="/dashboard/billing" element={
          <ProtectedRoute>
            <BillingPage />
          </ProtectedRoute>
        } />
        <Route path="/dashboard/usage" element={
          <ProtectedRoute>
            <UsagePage />
          </ProtectedRoute>
        } />
        <Route path="/dashboard/security" element={
          <ProtectedRoute>
            <SecurityPage />
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
        <Route path="/dashboard/integrations" element={
          <ProtectedRoute>
            <IntegrationsPage />
          </ProtectedRoute>
        } />
        <Route path="/dashboard/integrations/new" element={
          <ProtectedRoute>
            <IntegrationFormPage />
          </ProtectedRoute>
        } />
        <Route path="/dashboard/integrations/:id/edit" element={
          <ProtectedRoute>
            <IntegrationFormPage />
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

