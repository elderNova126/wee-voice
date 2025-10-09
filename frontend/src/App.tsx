import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'

// Pages
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import AgentsPage from './pages/AgentsPage'
import AgentFormPage from './pages/AgentFormPage'
import CallsPage from './pages/CallsPage'
import APIKeysPage from './pages/APIKeysPage'
import DemoPage from './pages/DemoPage'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
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
      </Routes>
    </BrowserRouter>
  )
}

export default App

