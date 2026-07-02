'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useQueryClient } from '@tanstack/react-query'
import { CaretDownIcon, ChatTextIcon, GearIcon, ShieldIcon, SignOutIcon, SquaresFourIcon, StarIcon, WarningCircleIcon } from '@/lib/icons'
import { logout } from '@/features/auth/api/auth-api'

export type MenuUser = {
  email: string
  full_name?: string | null
  email_verified?: boolean
  is_admin?: boolean
}

function getInitials(name?: string | null, email?: string): string {
  if (name && name.trim()) {
    const parts = name.trim().split(/\s+/)
    return (parts[0][0] + (parts[1]?.[0] ?? '')).toUpperCase()
  }
  return (email?.[0] ?? '?').toUpperCase()
}

const MENU_LINKS = [
  { href: '/dashboard', label: 'Dashboard', icon: SquaresFourIcon },
  { href: '/dashboard/watchlist', label: 'Watchlist', icon: StarIcon },
  { href: '/dashboard/settings', label: 'Settings', icon: GearIcon },
] as const

export default function UserMenu({ user }: { user: MenuUser }) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const router = useRouter()
  const queryClient = useQueryClient()

  const unverified = user.email_verified === false

  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const handleLogout = async () => {
    setOpen(false)
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
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="true"
        aria-expanded={open}
        aria-label="Account menu"
        className="flex items-center gap-1.5 rounded-full transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
      >
        <span className="relative inline-flex h-9 w-9 items-center justify-center rounded-full bg-brand-strong/15 text-sm font-semibold text-brand-strong ring-1 ring-brand-border dark:bg-brand-dark/15 dark:text-brand-strong-dark dark:ring-brand-dark/30">
          {getInitials(user.full_name, user.email)}
          {unverified && (
            <span
              className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full bg-amber-400 ring-2 ring-slate-950"
              aria-hidden="true"
            />
          )}
        </span>
        <CaretDownIcon className="h-4 w-4 text-text-secondary-light dark:text-text-secondary-dark" />
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Account"
          className="absolute right-0 z-50 mt-2 w-60 origin-top-right rounded-xl border border-border-light dark:border-white/10 bg-panel-light dark:bg-slate-900 p-1 shadow-e2 dark:shadow-none"
        >
          <div className="px-3 py-2.5">
            <p className="truncate text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">
              {user.full_name || 'Your account'}
            </p>
            <p className="truncate text-xs text-text-secondary-light dark:text-text-secondary-dark">{user.email}</p>
          </div>

          {unverified && (
            <Link
              href={`/check-email?email=${encodeURIComponent(user.email)}`}
              role="menuitem"
              onClick={() => setOpen(false)}
              className="mx-1 mb-1 flex items-center gap-2 rounded-lg bg-amber-400/10 px-2.5 py-2 text-sm font-medium text-amber-700 dark:text-amber-300 transition-colors hover:bg-amber-400/20"
            >
              <WarningCircleIcon className="h-4 w-4" />
              Verify your email
            </Link>
          )}

          <div className="border-t border-border-light dark:border-white/10 pt-1">
            {MENU_LINKS.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                role="menuitem"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-text-secondary-light dark:text-text-secondary-dark transition-colors hover:bg-white/5 hover:text-text-primary-light dark:hover:text-text-primary-dark"
              >
                <Icon className="h-4 w-4 text-text-secondary-light dark:text-text-secondary-dark" />
                {label}
              </Link>
            ))}
          </div>

          {user.is_admin && (
            <div className="mt-1 border-t border-border-light dark:border-white/10 pt-1">
              <Link
                href="/admin/invites"
                role="menuitem"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-text-secondary-light dark:text-text-secondary-dark transition-colors hover:bg-white/5 hover:text-text-primary-light dark:hover:text-text-primary-dark"
              >
                <ShieldIcon className="h-4 w-4 text-text-secondary-light dark:text-text-secondary-dark" />
                Admin · Invites
              </Link>
              <Link
                href="/admin/feedback"
                role="menuitem"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-text-secondary-light dark:text-text-secondary-dark transition-colors hover:bg-white/5 hover:text-text-primary-light dark:hover:text-text-primary-dark"
              >
                <ChatTextIcon className="h-4 w-4 text-text-secondary-light dark:text-text-secondary-dark" />
                Admin · Feedback
              </Link>
            </div>
          )}

          <div className="mt-1 border-t border-border-light dark:border-white/10 pt-1">
            <button
              type="button"
              role="menuitem"
              onClick={handleLogout}
              className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-text-secondary-light dark:text-text-secondary-dark transition-colors hover:bg-white/5 hover:text-text-primary-light dark:hover:text-text-primary-dark"
            >
              <SignOutIcon className="h-4 w-4 text-text-secondary-light dark:text-text-secondary-dark" />
              Log out
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
