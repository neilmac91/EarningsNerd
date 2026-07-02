'use client'

import { MoonIcon, SunIcon } from '@/lib/icons'
import { useContext, useEffect, useState } from 'react'
import { ThemeContext } from './ThemeProvider'

export function ThemeToggle() {
  const [mounted, setMounted] = useState(false)
  
  // Always call hooks unconditionally - before any early returns
  const context = useContext(ThemeContext)
  
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- mount-time latch: flips to client-rendered state after hydration to avoid SSR/client mismatch
    setMounted(true)
  }, [])

  // During SSR or before context is available, render placeholder
  if (!mounted || !context) {
    return (
      <div className="inline-flex items-center justify-center rounded-lg p-2 text-text-secondary-light">
        <SunIcon className="h-5 w-5" />
      </div>
    )
  }

  const { theme, toggleTheme } = context

  return (
    <button
      onClick={toggleTheme}
      className="inline-flex items-center justify-center rounded-lg p-2 text-text-secondary-light transition-colors hover:bg-brand-weak hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:bg-white/10 dark:hover:text-text-primary-dark"
      aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
    >
      {theme === 'light' ? (
        <MoonIcon className="h-5 w-5" />
      ) : (
        <SunIcon className="h-5 w-5" />
      )}
    </button>
  )
}

