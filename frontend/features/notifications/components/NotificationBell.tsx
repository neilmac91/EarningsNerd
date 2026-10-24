'use client'

import { queryKeys } from '@/lib/queryKeys'
import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import { BellIcon } from '@/lib/icons'
import { formatLocalDate } from '@/lib/format'
import { formatCompanyName } from '@/lib/formatCompanyName'
import {
  getNotifications,
  markNotificationsSeen,
  type NotificationList,
} from '@/features/notifications/api/notifications-api'

/**
 * In-app notification bell: shows recent SEC-filing alerts for the signed-in user with an unread
 * badge. Reads the same alerts the email scanner records (GET /me/notifications); opening the bell
 * marks them seen (POST /me/notifications/seen), which clears the badge. Rendered only when
 * authenticated (the Header gates it). `className` joins the trigger's own, as ThemeToggle's does: the
 * compact header bar gives it the 44px target its other controls keep. `open` and `onOpenChange` let a parent
 * hold the panel, as the compact bar does so that one of the panel and its menu is open at a time; without
 * them the bell holds its own.
 */
export default function NotificationBell({
  className = '',
  open: heldOpen,
  onOpenChange,
}: {
  className?: string
  open?: boolean
  onOpenChange?: (open: boolean) => void
}) {
  const [ownOpen, setOwnOpen] = useState(false)
  const open = heldOpen ?? ownOpen
  const setOpen = useCallback(
    (next: boolean) => {
      if (heldOpen === undefined) setOwnOpen(next)
      onOpenChange?.(next)
    },
    [heldOpen, onOpenChange],
  )
  const containerRef = useRef<HTMLDivElement>(null)
  const queryClient = useQueryClient()

  const { data } = useQuery({
    queryKey: queryKeys.notifications(),
    queryFn: getNotifications,
    retry: false,
    staleTime: 30_000,
    refetchInterval: 60_000,
  })

  const seen = useMutation({
    mutationFn: markNotificationsSeen,
    onSuccess: (fresh: NotificationList) => {
      queryClient.setQueryData(queryKeys.notifications(), fresh)
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
  }, [open, setOpen])

  const toggle = () => {
    const next = !open
    setOpen(next)
    // Opening with unread alerts marks them seen so the badge clears.
    if (next && unread > 0 && !seen.isPending) {
      seen.mutate()
    }
  }

  return (
    <div ref={containerRef} className="relative max-lg:static">
      <button
        type="button"
        onClick={toggle}
        aria-haspopup="true"
        aria-expanded={open}
        aria-label={unread > 0 ? `Notifications (${unread} unread)` : 'Notifications'}
        className={`relative flex h-9 w-9 items-center justify-center rounded-full text-text-secondary-light dark:text-text-secondary-dark transition-colors hover:bg-white/5 hover:text-text-primary-light dark:hover:text-text-primary-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark ${className}`}
      >
        <BellIcon className="h-5 w-5" />
        {/* The count is a number, so it rests in the ink, never on sage (D-030); the sage dot marks an
            unread row in the list below. */}
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-text-primary-light text-white dark:bg-text-primary-dark dark:text-background-dark px-1 text-data-xs font-semibold ring-2 ring-background-light dark:ring-background-dark">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {/* The panel is a column no taller than the screen under the bar: the screen's height less the header's published
          height (--site-header-h, the bar's own while the panel is open: one of the panel and the compact menu is open at
          a time, and from lg the open menu lies over the page and adds nothing to it) and the panel's own 0.5rem offset.
          The bell sits inside the bar, so the panel ends above the screen's foot by at least the bar's lower padding. The
          title and the settings link keep their height (shrink-0) and the list takes what is left, scrolling inside it;
          where the screen has room the list's own 24rem cap holds, as before. Before, only the list was capped, at 24rem
          (768px under 200% text), so with 20 alerts the panel ran past the screen's foot, where the sticky header kept its
          tail out of reach: at 1024x768 and 1440x900 under 200% text it spanned 128 to 1060px, its settings link ending
          at 1051px (E178; tests/e2e/reflow-200.spec.ts). Below lg the panel spans the screen under the bar, inset as the
          bar is (16px, 24px from sm): its box leaves the bell (static) for the header, the bar's positioned column, and
          keeps its place below the bell. A 20rem box anchored at the bell ran off the screen's left edge there, by 64px
          at 320px at the default size and at every phone width under 200% text (E176, chief design on #1565, comment
          6380050139; tests/e2e/reflow-200.spec.ts). */}
      {open && (
        <div
          role="menu"
          aria-label="Notifications"
          className="absolute right-0 z-header mt-2 flex max-h-[calc(100dvh_-_var(--site-header-h,4rem)_-_0.5rem)] w-80 origin-top-right flex-col overflow-hidden rounded-xl border border-border-light dark:border-white/10 bg-panel-light dark:bg-panel-dark shadow-e2 dark:shadow-none max-lg:inset-x-4 max-lg:w-auto max-lg:origin-top sm:max-lg:inset-x-6"
        >
          <div className="shrink-0 border-b border-border-light dark:border-white/10 px-3 py-2.5">
            <p className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">Notifications</p>
          </div>

          {items.length === 0 ? (
            <div className="px-3 py-cap-6 text-center">
              <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">No filing alerts yet</p>
              <p className="mt-1 text-xs text-text-secondary-light dark:text-text-secondary-dark">
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
                    className="flex items-start gap-2.5 rounded-lg px-3 py-2.5 transition-colors hover:bg-white/5 focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
                  >
                    <span
                      aria-hidden="true"
                      className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                        item.read ? 'bg-transparent' : 'bg-brand-strong dark:bg-brand-strong-dark'
                      }`}
                    />
                    {/* An alert's lines wrap, breaking a long token inside the row, never truncate: in the phone panel at
                        390px under 200% text a truncated line cut the date from every alert, the company name ending at
                        "·…" (E176; tests/e2e/reflow-200.spec.ts). */}
                    <span className="min-w-0">
                      <span className="block text-sm text-text-primary-light [overflow-wrap:anywhere] dark:text-text-primary-dark">
                        New <span className="font-data">{item.filing_type}</span> from{' '}
                        <span className="font-data font-semibold">{item.ticker}</span>
                      </span>
                      <span className="block text-xs text-text-secondary-light [overflow-wrap:anywhere] dark:text-text-secondary-dark">
                        {formatCompanyName(item.company_name)}
                        {item.filing_date ? ` · ${formatLocalDate(item.filing_date, 'MMM d, yyyy')}` : ''}
                      </span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}

          <div className="shrink-0 border-t border-border-light dark:border-white/10 p-1">
            <Link
              href="/dashboard/settings"
              role="menuitem"
              onClick={() => setOpen(false)}
              className="block rounded-lg px-3 py-2 text-center text-xs font-medium text-text-secondary-light dark:text-text-secondary-dark transition-colors hover:bg-white/5 hover:text-text-primary-light dark:hover:text-text-primary-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
            >
              Manage alert settings
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}
