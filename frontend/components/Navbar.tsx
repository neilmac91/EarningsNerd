'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Menu, Search, X } from 'lucide-react'
import EarningsNerdLogo from '@/components/EarningsNerdLogo'
import { ThemeToggle } from '@/components/ThemeToggle'
import CompanySearch from '@/components/CompanySearch'

interface NavbarProps {
  className?: string
  showSearch?: boolean
}

export default function Navbar({ className = '', showSearch = true }: NavbarProps) {
  const router = useRouter()
  const [hasToken, setHasToken] = useState(false)
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const [isSearchOpen, setIsSearchOpen] = useState(false)

  useEffect(() => {
    const syncToken = () => {
      if (typeof window === 'undefined') return
      setHasToken(!!window.localStorage.getItem('token'))
    }
    syncToken()
    window.addEventListener('storage', syncToken)
    return () => {
      window.removeEventListener('storage', syncToken)
    }
  }, [])

  const handleLogout = () => {
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem('token')
    }
    setHasToken(false)
    router.push('/')
  }

  const navLinks = [
    { label: 'Product', href: '/#product' },
    { label: 'Workflow', href: '/#workflow' },
    { label: 'Insights', href: '/#insights' },
    { label: 'Pricing', href: '/pricing' },
  ]

  return (
    <header className={`sticky top-0 z-40 border-b border-gray-200/60 dark:border-white/5 bg-white/80 dark:bg-slate-950/80 backdrop-blur-xl ${className}`}>
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center transition-transform hover:scale-[1.02]">
          <EarningsNerdLogo variant="full" iconClassName="h-10 w-10 md:h-11 md:w-11" hideTagline />
        </Link>

        <nav className="hidden items-center space-x-8 text-sm font-medium text-gray-600 dark:text-slate-400 lg:flex">
          {navLinks.map((link) => (
            <Link key={link.href} href={link.href} className="transition-colors hover:text-gray-900 dark:hover:text-white">
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-3">
          {showSearch && (
            <button
              type="button"
              onClick={() => setIsSearchOpen((prev) => !prev)}
              className="hidden items-center gap-2 rounded-full border border-gray-200/60 dark:border-white/10 bg-white/70 dark:bg-slate-950/70 px-4 py-2 text-sm font-medium text-gray-600 dark:text-slate-300 lg:inline-flex"
              aria-label="Open company search"
            >
              <Search className="h-4 w-4" />
              Search companies
            </button>
          )}
          <ThemeToggle />
          {hasToken ? (
            <div className="hidden items-center gap-3 lg:flex">
              <Link href="/dashboard" className="text-sm font-medium text-gray-600 dark:text-slate-300 hover:text-gray-900 dark:hover:text-white">
                Dashboard
              </Link>
              <button
                type="button"
                onClick={handleLogout}
                className="text-sm font-medium text-gray-500 dark:text-slate-400 hover:text-gray-900 dark:hover:text-white"
              >
                Logout
              </button>
            </div>
          ) : (
            <div className="hidden items-center gap-3 lg:flex">
              <Link href="/login" className="text-sm font-medium text-gray-600 dark:text-slate-300 hover:text-gray-900 dark:hover:text-white">
                Log in
              </Link>
              <Link
                href="/register"
                className="inline-flex items-center rounded-full bg-gradient-to-r from-sky-500 via-indigo-500 to-purple-500 px-4 py-2 text-sm font-semibold text-white"
              >
                Start free trial
              </Link>
            </div>
          )}
          <button
            type="button"
            onClick={() => setIsMenuOpen(true)}
            className="inline-flex items-center justify-center rounded-full border border-gray-200/60 dark:border-white/10 bg-white/70 dark:bg-slate-950/70 p-2 text-gray-700 dark:text-slate-200 lg:hidden"
            aria-label="Open navigation menu"
          >
            <Menu className="h-5 w-5" />
          </button>
        </div>
      </div>

      {showSearch && isSearchOpen && (
        <div className="border-t border-gray-200/60 dark:border-white/10 bg-white/90 dark:bg-slate-950/90">
          <div className="mx-auto max-w-4xl px-6 py-4">
            <div className="rounded-2xl border border-gray-200/60 dark:border-white/10 bg-white dark:bg-slate-950 p-4 shadow-lg">
              <CompanySearch />
            </div>
          </div>
        </div>
      )}

      {isMenuOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true">
          <div
            className="absolute inset-0 bg-slate-950/40 backdrop-blur-sm"
            onClick={() => setIsMenuOpen(false)}
          />
          <div className="absolute right-4 top-4 w-[calc(100%-2rem)] max-w-sm rounded-3xl border border-gray-200/60 dark:border-white/10 bg-white dark:bg-slate-950 p-6 shadow-2xl">
            <div className="flex items-center justify-between">
              <EarningsNerdLogo variant="full" iconClassName="h-9 w-9" hideTagline />
              <button
                type="button"
                onClick={() => setIsMenuOpen(false)}
                className="inline-flex items-center justify-center rounded-full border border-gray-200/60 dark:border-white/10 p-2 text-gray-600 dark:text-slate-300"
                aria-label="Close navigation menu"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-6 space-y-4 text-sm font-medium text-gray-700 dark:text-slate-200">
              {navLinks.map((link) => (
                <Link key={link.href} href={link.href} onClick={() => setIsMenuOpen(false)} className="block">
                  {link.label}
                </Link>
              ))}
            </div>

            {showSearch && (
              <div className="mt-6 rounded-2xl border border-gray-200/60 dark:border-white/10 bg-white dark:bg-slate-950 p-4 shadow-sm">
                <CompanySearch />
              </div>
            )}

            <div className="mt-6 space-y-3">
              {hasToken ? (
                <>
                  <Link
                    href="/dashboard"
                    onClick={() => setIsMenuOpen(false)}
                    className="block rounded-full border border-gray-200/60 dark:border-white/10 px-4 py-2 text-center text-sm font-semibold text-gray-700 dark:text-slate-200"
                  >
                    Dashboard
                  </Link>
                  <button
                    type="button"
                    onClick={() => {
                      handleLogout()
                      setIsMenuOpen(false)
                    }}
                    className="block w-full rounded-full border border-gray-200/60 dark:border-white/10 px-4 py-2 text-center text-sm font-semibold text-gray-600 dark:text-slate-300"
                  >
                    Logout
                  </button>
                </>
              ) : (
                <>
                  <Link
                    href="/login"
                    onClick={() => setIsMenuOpen(false)}
                    className="block rounded-full border border-gray-200/60 dark:border-white/10 px-4 py-2 text-center text-sm font-semibold text-gray-700 dark:text-slate-200"
                  >
                    Log in
                  </Link>
                  <Link
                    href="/register"
                    onClick={() => setIsMenuOpen(false)}
                    className="block rounded-full bg-gradient-to-r from-sky-500 via-indigo-500 to-purple-500 px-4 py-2 text-center text-sm font-semibold text-white"
                  >
                    Start free trial
                  </Link>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </header>
  )
}
