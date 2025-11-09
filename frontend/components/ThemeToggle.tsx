'use client'

import { Moon, Sun } from 'lucide-react'
import { useContext, useEffect, useState } from 'react'
import { ThemeContext } from './ThemeProvider'

export function ThemeToggle() {
  const [mounted, setMounted] = useState(false)
  
  // Always call hooks unconditionally - before any early returns
  const context = useContext(ThemeContext)
  
  useEffect(() => {
    setMounted(true)
  }, [])

  // During SSR or before context is available, render placeholder
  if (!mounted || !context) {
    return (
      <div className="inline-flex items-center justify-center rounded-lg p-2 text-gray-500">
        <Sun className="h-5 w-5" />
      </div>
    )
  }

  const { theme, toggleTheme } = context

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
}

