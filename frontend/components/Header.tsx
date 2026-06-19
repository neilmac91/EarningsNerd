'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Menu, X, ArrowRight, LogOut, Search } from 'lucide-react'
import EarningsNerdLogo from '@/components/EarningsNerdLogo'
import UserMenu from '@/components/UserMenu'
import { getCurrentUserSafe, logout } from '@/features/auth/api/auth-api'
import { openCommandPalette } from '@/lib/commandPalette'

const NAV_LINKS = [
  { href: '/pricing', label: 'Pricing' },
  { href: '/contact', label: 'Contact' },
] as const

const MOBILE_USER_LINKS = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/dashboard/watchlist', label: 'Watchlist' },
  { href: '/dashboard/settings', label: 'Settings' },
] as const

export default function Header() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const router = useRouter()
  const queryClient = useQueryClient()

  const { data: user, isLoading } = useQuery({
    queryKey: ['current-user'],
    queryFn: getCurrentUserSafe,
    retry: false,
    staleTime: 60_000,
  })

  const handleMobileLogout = async () => {
    setMobileMenuOpen(false)
    try {
      await logout()
    } catch {
      // ignore — clear local state regardless
    }
    queryClient.setQueryData(['current-user'], null)
    queryClient.invalidateQueries({ queryKey: ['user'] })
    router.push('/')
    router.refresh()
  }

  return (
    <header className="sticky top-0 z-50 border-b border-white/[0.06] bg-slate-950/80 backdrop-blur-xl">
      {/* Subtle gradient accent line at top */}
      <div className="h-px bg-gradient-to-r from-transparent via-mint-500/50 to-transparent" aria-hidden="true" />

      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
        {/* Left: Logo */}
        <div className="flex items-center">
          <Link href="/" className="flex items-center gap-2.5">
            <EarningsNerdLogo variant="icon-only" iconClassName="h-8 w-8" mode="dark" />
            <span className="text-lg font-bold text-white">
              EarningsNerd
            </span>
          </Link>
        </div>

        {/* Center: Nav links (desktop) */}
        <nav className="hidden items-center gap-8 md:flex" aria-label="Main navigation">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-sm font-medium text-slate-300 transition-colors hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mint-500"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        {/* Right: CTAs / user menu (desktop) */}
        <div className="hidden items-center gap-3 md:flex">
          <button
            type="button"
            onClick={openCommandPalette}
            className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-400 transition-colors hover:border-white/20 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mint-500"
            aria-label="Search SEC filings"
          >
            <Search className="h-4 w-4" />
            <span>Search filings</span>
            <kbd className="ml-1 rounded border border-white/15 bg-white/5 px-1.5 py-0.5 font-mono text-[10px] text-slate-500">
              ⌘K
            </kbd>
          </button>
          {isLoading ? (
            <div className="h-9 w-9 animate-pulse rounded-full bg-white/10" aria-hidden="true" />
          ) : user ? (
            <UserMenu user={user} />
          ) : (
            <>
              <Link
                href="/login"
                className="rounded-full px-5 py-2 text-sm font-medium text-slate-300 transition-colors hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mint-500"
              >
                Log In
              </Link>
              <Link
                href="/register"
                className="inline-flex items-center gap-1.5 rounded-full bg-mint-500 px-5 py-2 text-sm font-semibold text-slate-950 shadow-glow-mint-sm transition-all hover:bg-mint-400 hover:shadow-glow-mint focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mint-500"
              >
                Get Started
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </>
          )}
        </div>

        {/* Mobile controls: search + menu */}
        <div className="flex items-center gap-1 md:hidden">
          <button
            type="button"
            onClick={openCommandPalette}
            className="inline-flex items-center justify-center rounded-lg p-2 text-slate-400 hover:text-white"
            aria-label="Search SEC filings"
          >
            <Search className="h-5 w-5" />
          </button>
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="inline-flex items-center justify-center rounded-lg p-2 text-slate-400 hover:text-white"
            aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={mobileMenuOpen}
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileMenuOpen && (
        <div className="border-t border-white/[0.06] bg-slate-950 md:hidden">
          <nav className="mx-auto max-w-7xl space-y-1 px-4 pb-4 pt-2" aria-label="Mobile navigation">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMobileMenuOpen(false)}
                className="block rounded-lg px-3 py-2.5 text-sm font-medium text-slate-300 transition-colors hover:bg-white/5 hover:text-white"
              >
                {link.label}
              </Link>
            ))}
            <div className="mt-3 flex flex-col gap-2 border-t border-white/[0.06] pt-3">
              {user ? (
                <>
                  <div className="px-3 pb-1">
                    <p className="truncate text-sm font-semibold text-white">
                      {user.full_name || 'Your account'}
                    </p>
                    <p className="truncate text-xs text-slate-400">{user.email}</p>
                  </div>
                  {user.email_verified === false && (
                    <Link
                      href={`/check-email?email=${encodeURIComponent(user.email)}`}
                      onClick={() => setMobileMenuOpen(false)}
                      className="block rounded-lg bg-amber-400/10 px-3 py-2.5 text-sm font-medium text-amber-300 transition-colors hover:bg-amber-400/20"
                    >
                      Verify your email
                    </Link>
                  )}
                  {MOBILE_USER_LINKS.map((link) => (
                    <Link
                      key={link.href}
                      href={link.href}
                      onClick={() => setMobileMenuOpen(false)}
                      className="block rounded-lg px-3 py-2.5 text-sm font-medium text-slate-300 transition-colors hover:bg-white/5 hover:text-white"
                    >
                      {link.label}
                    </Link>
                  ))}
                  <button
                    type="button"
                    onClick={handleMobileLogout}
                    className="flex items-center gap-2 rounded-lg px-3 py-2.5 text-left text-sm font-medium text-slate-300 transition-colors hover:bg-white/5 hover:text-white"
                  >
                    <LogOut className="h-4 w-4 text-slate-400" />
                    Log out
                  </button>
                </>
              ) : (
                <>
                  <Link
                    href="/login"
                    onClick={() => setMobileMenuOpen(false)}
                    className="block rounded-lg px-3 py-2.5 text-center text-sm font-medium text-slate-300 transition-colors hover:bg-white/5 hover:text-white"
                  >
                    Log In
                  </Link>
                  <Link
                    href="/register"
                    onClick={() => setMobileMenuOpen(false)}
                    className="block rounded-lg bg-mint-500 px-3 py-2.5 text-center text-sm font-semibold text-slate-950 transition-colors hover:bg-mint-400"
                  >
                    Get Started
                  </Link>
                </>
              )}
            </div>
          </nav>
        </div>
      )}
    </header>
  )
}
