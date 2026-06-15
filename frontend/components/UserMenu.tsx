'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useQueryClient } from '@tanstack/react-query'
import { LayoutDashboard, Star, Settings, LogOut, ChevronDown, MailWarning } from 'lucide-react'
import { logout } from '@/features/auth/api/auth-api'

export type MenuUser = {
  email: string
  full_name?: string | null
  email_verified?: boolean
}

function getInitials(name?: string | null, email?: string): string {
  if (name && name.trim()) {
    const parts = name.trim().split(/\s+/)
    return (parts[0][0] + (parts[1]?.[0] ?? '')).toUpperCase()
  }
  return (email?.[0] ?? '?').toUpperCase()
}

const MENU_LINKS = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/dashboard/watchlist', label: 'Watchlist', icon: Star },
  { href: '/dashboard/settings', label: 'Settings', icon: Settings },
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
        className="flex items-center gap-1.5 rounded-full transition-opacity hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mint-500"
      >
        <span className="relative inline-flex h-9 w-9 items-center justify-center rounded-full bg-mint-500/15 text-sm font-semibold text-mint-300 ring-1 ring-mint-500/30">
          {getInitials(user.full_name, user.email)}
          {unverified && (
            <span
              className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full bg-amber-400 ring-2 ring-slate-950"
              aria-hidden="true"
            />
          )}
        </span>
        <ChevronDown className="h-4 w-4 text-slate-400" />
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Account"
          className="absolute right-0 z-50 mt-2 w-60 origin-top-right rounded-xl border border-white/10 bg-slate-900 p-1 shadow-xl"
        >
          <div className="px-3 py-2.5">
            <p className="truncate text-sm font-semibold text-white">
              {user.full_name || 'Your account'}
            </p>
            <p className="truncate text-xs text-slate-400">{user.email}</p>
          </div>

          {unverified && (
            <Link
              href={`/check-email?email=${encodeURIComponent(user.email)}`}
              role="menuitem"
              onClick={() => setOpen(false)}
              className="mx-1 mb-1 flex items-center gap-2 rounded-lg bg-amber-400/10 px-2.5 py-2 text-sm font-medium text-amber-300 transition-colors hover:bg-amber-400/20"
            >
              <MailWarning className="h-4 w-4" />
              Verify your email
            </Link>
          )}

          <div className="border-t border-white/10 pt-1">
            {MENU_LINKS.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                role="menuitem"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-slate-300 transition-colors hover:bg-white/5 hover:text-white"
              >
                <Icon className="h-4 w-4 text-slate-400" />
                {label}
              </Link>
            ))}
          </div>

          <div className="mt-1 border-t border-white/10 pt-1">
            <button
              type="button"
              role="menuitem"
              onClick={handleLogout}
              className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-slate-300 transition-colors hover:bg-white/5 hover:text-white"
            >
              <LogOut className="h-4 w-4 text-slate-400" />
              Log out
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
