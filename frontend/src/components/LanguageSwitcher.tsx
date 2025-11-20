import { GlobeAltIcon } from '@heroicons/react/24/outline'
import { useLanguageStore } from '@/store/languageStore'
import { useTranslation } from '@/lib/translations'

export default function LanguageSwitcher() {
  const { language, setLanguage } = useLanguageStore()
  const t = useTranslation()

  const languages = [
    { code: 'fr' as const, label: 'Français', flag: '🇫🇷' },
    { code: 'en' as const, label: 'English', flag: '🇬🇧' },
  ]

  return (
    <div className="relative">
      <select
        value={language}
        onChange={(e) => setLanguage(e.target.value as 'fr' | 'en')}
        className="appearance-none bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 pr-8 text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer"
        aria-label={t.settings.language}
      >
        {languages.map((lang) => (
          <option key={lang.code} value={lang.code}>
            {lang.flag} {lang.label}
          </option>
        ))}
      </select>
      <GlobeAltIcon className="absolute right-2 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
    </div>
  )
}

