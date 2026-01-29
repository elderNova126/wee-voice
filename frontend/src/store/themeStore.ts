import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type Theme = 'light' | 'dark'

interface ThemeState {
  theme: Theme
  setTheme: (theme: Theme) => void
  isDark: boolean
  updateIsDark: () => void
}

// Apply theme to document
const applyTheme = (theme: Theme) => {
  const isDark = theme === 'dark'
  if (isDark) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
  return isDark
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      theme: 'light',
      isDark: false,
      setTheme: (theme: Theme) => {
        const isDark = applyTheme(theme)
        set({ theme, isDark })
      },
      updateIsDark: () => {
        const { theme } = get()
        const isDark = applyTheme(theme)
        set({ isDark })
      },
    }),
    {
      name: 'theme-storage',
      partialize: (state) => ({ theme: state.theme }),
      onRehydrateStorage: () => (state) => {
        if (state) {
          // Migrate old 'system' preference to light or dark
          const resolved: Theme = state.theme === 'system'
            ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
            : state.theme
          state.theme = resolved
          state.isDark = applyTheme(resolved)
        }
      },
    }
  )
)

