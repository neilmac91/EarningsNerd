'use client'

import { Moon, Sun } from 'lucide-react'
import { useTheme } from './ThemeProvider'
import { useEffect, useState } from 'react'

export function ThemeToggle() {
  const [mounted, setMounted] = useState(false)
  
  useEffect(() => {
    setMounted(true)
  }, [])

  // During SSR, just render a placeholder to avoid errors
  if (!mounted) {
    return (
      <div className="inline-flex items-center justify-center rounded-lg p-2 text-gray-500">
        <Sun className="h-5 w-5" />
      </div>
    )
  }

  try {
    const { theme, toggleTheme } = useTheme()

    return (
      <button
        onClick={toggleTheme}
        className="inline-flex items-center justify-center rounded-lg p-2 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-white"
        aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
      >
        {theme === 'light' ? (
          <Moon className="h-5 w-5" />
        ) : (
          <Sun className="h-5 w-5" />
        )}
      </button>
    )
  } catch (error) {
    // Fallback if theme context is not available
    return (
      <div className="inline-flex items-center justify-center rounded-lg p-2 text-gray-500">
        <Sun className="h-5 w-5" />
      </div>
    )
  }
}

