import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type Language = 'fr' | 'en'

interface LanguageState {
  language: Language
  setLanguage: (language: Language) => void
}

export const useLanguageStore = create<LanguageState>()(
  persist(
    (set) => ({
      language: 'fr', // Default to French
      setLanguage: (language: Language) => {
        set({ language })
        // Update HTML lang attribute
        document.documentElement.lang = language
      },
    }),
    {
      name: 'language-storage',
      onRehydrateStorage: () => (state) => {
        // Apply language after rehydration
        if (state) {
          document.documentElement.lang = state.language
        }
      },
    }
  )
)

