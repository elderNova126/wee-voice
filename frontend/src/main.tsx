import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import App from './App'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

// Initialize theme before React renders to prevent flash
const initializeTheme = () => {
  try {
    const stored = localStorage.getItem('theme-storage')
    let theme = 'system'
    
    if (stored) {
      const parsed = JSON.parse(stored)
      theme = parsed?.state?.theme || 'system'
    }
    
    const systemIsDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    const isDark = theme === 'dark' || (theme === 'system' && systemIsDark)
    
    if (isDark) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
    
    console.log('Theme initialized:', { theme, isDark, systemIsDark })
  } catch (error) {
    console.error('Failed to initialize theme:', error)
  }
}

// Initialize theme immediately
initializeTheme()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
      <Toaster 
        position="top-right"
        toastOptions={{
          duration: 3000,
          style: {
            background: 'var(--toast-bg, #fff)',
            color: 'var(--toast-color, #1f2937)',
          },
          success: {
            iconTheme: {
              primary: '#10b981',
              secondary: '#fff',
            },
          },
          error: {
            iconTheme: {
              primary: '#ef4444',
              secondary: '#fff',
            },
          },
        }}
      />
    </QueryClientProvider>
  </React.StrictMode>,
)
