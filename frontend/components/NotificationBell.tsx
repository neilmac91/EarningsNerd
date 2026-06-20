'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import { Bell } from 'lucide-react'
import {
  getNotifications,
  markNotificationsSeen,
  type NotificationList,
} from '@/features/notifications/api/notifications-api'

function formatDate(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

/**
 * In-app notification bell: shows recent SEC-filing alerts for the signed-in user with an unread
 * badge. Reads the same alerts the email scanner records (GET /me/notifications); opening the bell
 * marks them seen (POST /me/notifications/seen), which clears the badge. Rendered only when
 * authenticated (the Header gates it).
 */
export default function NotificationBell() {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const queryClient = useQueryClient()

  const { data } = useQuery({
    queryKey: ['notifications'],
    queryFn: getNotifications,
    retry: false,
    staleTime: 30_000,
    refetchInterval: 60_000,
  })

  const seen = useMutation({
    mutationFn: markNotificationsSeen,
    onSuccess: (fresh: NotificationList) => {
      queryClient.setQueryData(['notifications'], fresh)
    },
  })

  const items = data?.items ?? []
  const unread = data?.unread_count ?? 0

  // Close on outside-click / Escape (mirrors UserMenu).
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

  const toggle = () => {
    const next = !open
    setOpen(next)
    // Opening with unread alerts marks them seen so the badge clears.
    if (next && unread > 0 && !seen.isPending) {
      seen.mutate()
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={toggle}
        aria-haspopup="true"
        aria-expanded={open}
        aria-label={unread > 0 ? `Notifications (${unread} unread)` : 'Notifications'}
        className="relative flex h-9 w-9 items-center justify-center rounded-full text-slate-300 transition-colors hover:bg-white/5 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mint-500"
      >
        <Bell className="h-5 w-5" />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-mint-500 px-1 text-[10px] font-bold text-slate-950 ring-2 ring-slate-950">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Notifications"
          className="absolute right-0 z-50 mt-2 w-80 origin-top-right overflow-hidden rounded-xl border border-white/10 bg-slate-900 shadow-xl"
        >
          <div className="border-b border-white/10 px-3 py-2.5">
            <p className="text-sm font-semibold text-white">Notifications</p>
          </div>

          {items.length === 0 ? (
            <div className="px-3 py-6 text-center">
              <p className="text-sm text-slate-300">No filing alerts yet</p>
              <p className="mt-1 text-xs text-slate-500">
                We&apos;ll notify you when a company on your watchlist files.
              </p>
            </div>
          ) : (
            <ul className="max-h-96 overflow-y-auto p-1">
              {items.map((item) => (
                <li key={item.id}>
                  <Link
                    href={`/filing/${item.filing_id}`}
                    role="menuitem"
                    onClick={() => setOpen(false)}
                    className="flex items-start gap-2.5 rounded-lg px-3 py-2.5 transition-colors hover:bg-white/5"
                  >
                    <span
                      aria-hidden="true"
                      className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                        item.read ? 'bg-transparent' : 'bg-mint-400'
                      }`}
                    />
                    <span className="min-w-0">
                      <span className="block truncate text-sm text-white">
                        <span className="font-semibold">{item.ticker}</span> filed a {item.filing_type}
                      </span>
                      <span className="block truncate text-xs text-slate-400">
                        {item.company_name}
                        {item.filing_date ? ` · ${formatDate(item.filing_date)}` : ''}
                      </span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}

          <div className="border-t border-white/10 p-1">
            <Link
              href="/dashboard/settings"
              role="menuitem"
              onClick={() => setOpen(false)}
              className="block rounded-lg px-3 py-2 text-center text-xs font-medium text-slate-400 transition-colors hover:bg-white/5 hover:text-white"
            >
              Manage alert settings
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}
