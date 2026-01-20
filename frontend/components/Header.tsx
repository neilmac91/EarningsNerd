'use client'

import Link from 'next/link'
import EarningsNerdLogo from '@/components/EarningsNerdLogo'
import { ThemeToggle } from '@/components/ThemeToggle'

export default function Header() {
  return (
    <header className="sticky top-0 z-50 border-b border-border-light bg-background-light/80 backdrop-blur-lg dark:border-border-dark dark:bg-background-dark/80">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <div className="flex items-center">
          <Link href="/" className="flex items-center gap-2 py-4" aria-label="EarningsNerd">
            <EarningsNerdLogo variant="icon-only" iconClassName="h-8 w-8" />
            <span className="hidden text-xl font-bold text-text-primary-light dark:text-text-primary-dark sm:inline-block">
              EarningsNerd
            </span>
          </Link>
        </div>

        <div className="flex items-center space-x-2 sm:space-x-4">
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
