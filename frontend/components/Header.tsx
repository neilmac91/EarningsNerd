'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { clsx } from 'clsx'
import EarningsNerdLogo from '@/components/EarningsNerdLogo'
import { ThemeToggle } from '@/components/ThemeToggle'

const links = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/search', label: 'Search' },
  { href: '/compare', label: 'Compare' },
]

export default function Header() {
  const pathname = usePathname()

  return (
    <header className="sticky top-0 z-50 border-b border-border-light bg-background-light/80 backdrop-blur-lg dark:border-border-dark dark:bg-background-dark/80">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <div className="flex items-center">
          <Link href="/" className="flex items-center gap-2 py-4">
            <EarningsNerdLogo variant="icon" className="h-8 w-8 text-mint-500" />
            <span className="hidden text-xl font-bold text-text-primary-light dark:text-text-primary-dark sm:inline-block">
              EarningsNerd
            </span>
          </Link>
        </div>

        <nav className="hidden items-center space-x-2 md:flex">
          {links.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={clsx(
                'rounded-md px-3 py-2 text-sm font-medium transition-colors',
                pathname === href
                  ? 'bg-mint-500/10 text-mint-600 dark:text-mint-400'
                  : 'text-text-secondary-light hover:bg-panel-light hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:bg-panel-dark dark:hover:text-text-primary-dark'
              )}
            >
              {label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center space-x-2 sm:space-x-4">
          <ThemeToggle />
          <div className="hidden h-6 w-px bg-border-light dark:bg-border-dark sm:block" />
          <Link
            href="/login"
            className="hidden rounded-md px-3 py-2 text-sm font-medium text-text-secondary-light transition-colors hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:text-text-primary-dark sm:block"
          >
            Log in
          </Link>
          <Link
            href="/register"
            className="rounded-md bg-mint-500 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-mint-600 focus:outline-none focus:ring-2 focus:ring-mint-500 focus:ring-offset-2"
          >
            Sign Up
          </Link>
        </div>
      </div>
    </header>
  )
}
