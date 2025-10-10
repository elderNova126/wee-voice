import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type Theme = 'light' | 'dark' | 'system'

interface ThemeState {
  theme: Theme
  setTheme: (theme: Theme) => void
  isDark: boolean
  updateIsDark: () => void
}

// Check system preference
const getSystemTheme = (): boolean => {
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

// Apply theme to document
const applyTheme = (theme: Theme, systemIsDark: boolean) => {
  const isDark = theme === 'dark' || (theme === 'system' && systemIsDark)
  
  console.log('Applying theme:', { theme, systemIsDark, isDark, currentClasses: document.documentElement.className })
  
  if (isDark) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
  
  console.log('Theme applied. New classes:', document.documentElement.className)
  
  return isDark
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => {
      // Listen for system theme changes
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
        const currentTheme = get().theme
        if (currentTheme === 'system') {
          const isDark = applyTheme('system', e.matches)
          set({ isDark })
        }
      })

      return {
        theme: 'system',
        isDark: false,
        setTheme: (theme: Theme) => {
          const systemIsDark = getSystemTheme()
          const isDark = applyTheme(theme, systemIsDark)
          set({ theme, isDark })
        },
        updateIsDark: () => {
          const { theme } = get()
          const systemIsDark = getSystemTheme()
          const isDark = applyTheme(theme, systemIsDark)
          set({ isDark })
        },
      }
    },
    {
      name: 'theme-storage',
      partialize: (state) => ({ theme: state.theme }),
      onRehydrateStorage: () => (state) => {
        // Apply theme after rehydration
        if (state) {
          const systemIsDark = getSystemTheme()
          const isDark = applyTheme(state.theme, systemIsDark)
          // Update the isDark state after rehydration
          state.isDark = isDark
        }
      },
    }
  )
)

